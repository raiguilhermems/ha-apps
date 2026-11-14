"""Aplicação FastAPI: lançamentos, recorrentes, parcelados, tags e projeção."""

from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path
import shutil

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from sqlmodel import Session, SQLModel, select

from contextvars import ContextVar
from fastapi.responses import RedirectResponse as _RedirectResponse

_prefixo: ContextVar[str] = ContextVar("prefixo", default="")


class RedirectResponse(_RedirectResponse):
    """Redireciona respeitando o caminho do ingress do Home Assistant."""

    def __init__(self, url, status_code=307, headers=None, background=None):
        if url.startswith("/"):
            url = _prefixo.get() + url
        super().__init__(url, status_code=status_code, headers=headers, background=background)
from fastapi.templating import Jinja2Templates

from app.db import DB_PATH, engine, get_session, init_db
from app.models import Account, InstallmentPlan, RecurringRule, Tag, Transaction, TransactionTag
from app.services.debts import delete_plan
from app.services.edit import update_rule, update_transaction
from app.services.parcelados import create_plan, generate_installments, schedule_summaries
from app.services.projections import projection
from app.services.recurring import create_rule, delete_rule, generate_all, rule_month_status, set_active
from app.services.summary import card_account_ids, monthly_summary, overdue_items
from app.services.tags import (
    get_or_create_tag,
    parse_tags,
    set_tags,
    tag_text,
    tags_by_tx,
    transactions_with_tag,
)
from app.services.util import add_months, current_month, fmt_brl, mes_curto, month_bounds, parse_brl
from app.services.charts import parcelas_mensal, receitas_despesas_mensal
from app.services.settings import get_setting, set_setting

@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="Finanças", lifespan=lifespan)
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")
templates.env.filters["brl"] = fmt_brl
templates.env.filters["mes"] = mes_curto

templates.env.globals["base"] = lambda: _prefixo.get()


@app.middleware("http")
async def ingress_prefixo(request: Request, call_next):
    token = _prefixo.set(request.headers.get("x-ingress-path", "").rstrip("/"))
    try:
        return await call_next(request)
    finally:
        _prefixo.reset(token)


def _parse_third(value: str, amount_cents: int, kind: str) -> int | None:
    """Terceiros só existe em despesa, e não pode passar do valor do lançamento."""
    if kind != "despesa" or not value.strip():
        return None
    third = parse_brl(value)
    if third < 0 or third > amount_cents:
        raise HTTPException(status_code=400, detail="Terceiros deve estar entre 0 e o valor do lançamento")
    return third or None


def _third_text(tx: Transaction) -> str:
    if not tx.third_party_cents:
        return ""
    return f"{tx.third_party_cents / 100:.2f}".replace(".", ",")


def _delete_tx(session: Session, tx: Transaction) -> None:
    for link in session.exec(
        select(TransactionTag).where(TransactionTag.transaction_id == tx.id)
    ).all():
        session.delete(link)
    session.delete(tx)


@app.get("/")
def home(request: Request, mes: str | None = None, session: Session = Depends(get_session)):
    generate_all(session)
    generate_installments(session)
    ref = mes or current_month()
    start, end = month_bounds(ref)
    cards = card_account_ids(session)

    txs = session.exec(
        select(Transaction)
        .where(Transaction.due_date >= start, Transaction.due_date < end)
        .order_by(Transaction.due_date)
    ).all()
    txs = [t for t in txs if t.account_id not in cards]
    horizonte = int(get_setting(session, "projecao_meses"))

    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "ref": ref,
            "prev": add_months(ref, -1),
            "next": add_months(ref, 1),
            "today": date.today(),
            "s": monthly_summary(session, ref),
            "txs": txs,
            "tag_map": tags_by_tx(session, [t.id for t in txs]),
            "atrasados": overdue_items(session),
            "proj": projection(session, ref, horizonte),
            "horizonte": horizonte,
            "grafico": receitas_despesas_mensal(session, ref),
        },
    )


@app.post("/lancamentos")
def create_transaction(
    description: str = Form(...),
    amount: str = Form(...),
    due_date: date = Form(...),
    kind: str = Form("despesa"),
    third_party: str = Form(""),
    tags: str = Form(""),
    session: Session = Depends(get_session),
):
    amount_cents = parse_brl(amount)
    tx = Transaction(
        description=description,
        amount_cents=amount_cents,
        due_date=due_date,
        kind=kind,
        is_recurring=False,
        status="pendente",
        third_party_cents=_parse_third(third_party, amount_cents, kind),
    )
    session.add(tx)
    session.flush()
    set_tags(session, tx, parse_tags(tags))
    session.commit()
    return RedirectResponse(f"/?mes={due_date:%Y-%m}", status_code=303)


@app.get("/lancamentos/{tx_id}/editar")
def edit_transaction_page(tx_id: int, request: Request, session: Session = Depends(get_session)):
    tx = session.get(Transaction, tx_id)
    if tx is None:
        raise HTTPException(status_code=404, detail="Lançamento não encontrado")
    return templates.TemplateResponse(
        request,
        "editar_lancamento.html",
        {"tx": tx, "tags_text": tag_text(session, tx.id), "third_text": _third_text(tx)},
    )


@app.post("/lancamentos/{tx_id}/editar")
def edit_transaction(
    tx_id: int,
    description: str = Form(...),
    amount: str = Form(...),
    due_date: date = Form(...),
    kind: str = Form("despesa"),
    third_party: str = Form(""),
    tags: str = Form(""),
    session: Session = Depends(get_session),
):
    tx = session.get(Transaction, tx_id)
    if tx is None:
        raise HTTPException(status_code=404, detail="Lançamento não encontrado")
    amount_cents = parse_brl(amount)
    update_transaction(session, tx, description, amount_cents, due_date, kind)
    tx.third_party_cents = _parse_third(third_party, amount_cents, kind)
    session.add(tx)
    set_tags(session, tx, parse_tags(tags))
    session.commit()
    return RedirectResponse(f"/?mes={due_date:%Y-%m}", status_code=303)


@app.post("/transacoes/{tx_id}/pagar")
def toggle_paid(tx_id: int, mes: str = Form(...), session: Session = Depends(get_session)):
    tx = session.get(Transaction, tx_id)
    if tx is None:
        raise HTTPException(status_code=404, detail="Lançamento não encontrado")
    if tx.status == "pendente":
        tx.status = "pago"
        tx.paid_date = date.today()
    else:
        tx.status = "pendente"
        tx.paid_date = None
    session.add(tx)
    session.commit()
    return RedirectResponse(f"/?mes={mes}", status_code=303)


@app.post("/transacoes/{tx_id}/excluir")
def delete_transaction(tx_id: int, mes: str = Form(...), session: Session = Depends(get_session)):
    tx = session.get(Transaction, tx_id)
    if tx is None:
        raise HTTPException(status_code=404, detail="Lançamento não encontrado")
    _delete_tx(session, tx)
    session.commit()
    return RedirectResponse(f"/?mes={mes}", status_code=303)


# ---------- Parcelados ----------

@app.get("/parcelados")
def parcelados_page(request: Request, session: Session = Depends(get_session)):
    data = schedule_summaries(session)
    cards = session.exec(select(Account).where(Account.type == "cartao")).all()
    return templates.TemplateResponse(
        request,
        "parcelados.html",
        {
            "plans": data["plans"],
            "saldo_total": data["saldo_total"],
            "cards": cards,
            "ref": current_month(),
            "graficos": parcelas_mensal(session),
        },
    )


@app.post("/parcelados")
def create_installment(
    description: str = Form(...),
    payment_method: str = Form(...),
    card_name: str = Form(""),
    amount: str = Form(...),
    total: int = Form(...),
    current_n: int = Form(...),
    current_ref: str = Form(...),
    due_day: int = Form(...),
    session: Session = Depends(get_session),
):
    if payment_method not in ("cartao", "boleto", "carne", "financiamento", "outro"):
        raise HTTPException(status_code=400, detail="Forma de pagamento inválida")
    if payment_method == "cartao" and not card_name.strip():
        raise HTTPException(status_code=400, detail="Informe o cartão")
    if total < 1 or not 1 <= current_n <= total:
        raise HTTPException(status_code=400, detail="Parcela atual deve estar entre 1 e o total de parcelas")
    if not 1 <= due_day <= 31:
        raise HTTPException(status_code=400, detail="Dia do vencimento deve estar entre 1 e 31")
    try:
        int(current_ref[:4]); int(current_ref[5:7])
    except ValueError:
        raise HTTPException(status_code=400, detail="Mês da parcela inválido")

    create_plan(
        session,
        description,
        payment_method,
        card_name,
        parse_brl(amount),
        total,
        current_n,
        current_ref,
        due_day,
    )
    session.commit()
    generate_installments(session)
    return RedirectResponse("/parcelados", status_code=303)


@app.post("/parcelados/tx/{tx_id}/pagar")
def toggle_installment_paid(tx_id: int, session: Session = Depends(get_session)):
    tx = session.get(Transaction, tx_id)
    if tx is None or tx.installment_plan_id is None:
        raise HTTPException(status_code=404, detail="Parcela não encontrada")
    if tx.status == "pendente":
        tx.status = "pago"
        tx.paid_date = date.today()
    else:
        tx.status = "pendente"
        tx.paid_date = None
    session.add(tx)
    session.commit()
    return RedirectResponse("/parcelados", status_code=303)


@app.post("/parcelados/{plan_id}/excluir")
def delete_installment(plan_id: int, session: Session = Depends(get_session)):
    plan = session.get(InstallmentPlan, plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Parcelamento não encontrado")
    delete_plan(session, plan)
    session.commit()
    return RedirectResponse("/parcelados", status_code=303)


# ---------- Tags ----------

@app.get("/tags")
def tags_page(request: Request, session: Session = Depends(get_session)):
    tags = session.exec(select(Tag).order_by(Tag.name)).all()
    return templates.TemplateResponse(request, "tags.html", {"tags": tags})


@app.post("/tags")
def create_tag(
    name: str = Form(...),
    excludes: bool = Form(False),
    session: Session = Depends(get_session),
):
    names = parse_tags(name)
    if not names:
        raise HTTPException(status_code=400, detail="Informe um nome para a tag")
    tag = get_or_create_tag(session, names[0])
    tag.excludes_from_total = excludes
    session.add(tag)
    session.commit()
    return RedirectResponse("/tags", status_code=303)


@app.post("/tags/{tag_id}/atualizar")
def update_tag(
    tag_id: int,
    name: str = Form(...),
    excludes: bool = Form(False),
    session: Session = Depends(get_session),
):
    tag = session.get(Tag, tag_id)
    if tag is None:
        raise HTTPException(status_code=404, detail="Tag não encontrada")
    names = parse_tags(name)
    if not names:
        raise HTTPException(status_code=400, detail="Informe um nome para a tag")
    clash = session.exec(select(Tag).where(Tag.name == names[0], Tag.id != tag.id)).first()
    if clash:
        raise HTTPException(status_code=400, detail="Já existe uma tag com esse nome")
    tag.name = names[0]
    tag.excludes_from_total = excludes
    session.add(tag)
    session.commit()
    return RedirectResponse("/tags", status_code=303)


@app.post("/tags/{tag_id}/excluir")
def delete_tag(tag_id: int, session: Session = Depends(get_session)):
    tag = session.get(Tag, tag_id)
    if tag is None:
        raise HTTPException(status_code=404, detail="Tag não encontrada")
    for link in session.exec(select(TransactionTag).where(TransactionTag.tag_id == tag.id)).all():
        session.delete(link)
    session.delete(tag)
    session.commit()
    return RedirectResponse("/tags", status_code=303)


@app.get("/tags/{tag_id}")
def tag_report(tag_id: int, request: Request, mes: str | None = None, session: Session = Depends(get_session)):
    tag = session.get(Tag, tag_id)
    if tag is None:
        raise HTTPException(status_code=404, detail="Tag não encontrada")
    ref = mes or current_month()
    start, end = month_bounds(ref)
    rows = []
    receitas = 0
    despesas = 0
    for t in transactions_with_tag(session, tag.id, start, end):
        acc = session.get(Account, t.account_id) if t.account_id else None
        rows.append({"tx": t, "conta": acc.name if acc else "—"})
        if t.kind == "receita":
            receitas += t.amount_cents
        elif t.kind == "despesa":
            despesas += t.amount_cents
    return templates.TemplateResponse(
        request,
        "tag_detalhe.html",
        {
            "tag": tag,
            "ref": ref,
            "prev": add_months(ref, -1),
            "next": add_months(ref, 1),
            "rows": rows,
            "receitas": receitas,
            "despesas": despesas,
        },
    )


# ---------- Recorrentes ----------

@app.get("/recorrentes")
def recorrentes_page(request: Request, mes: str | None = None, session: Session = Depends(get_session)):
    ref = mes or current_month()
    rules = session.exec(select(RecurringRule).order_by(RecurringRule.description)).all()
    rows = []
    for r in rules:
        card = session.get(Account, r.account_id) if r.account_id else None
        rows.append({"rule": r, "cartao": card.name if card else "—"})
    cards = session.exec(select(Account).where(Account.type == "cartao")).all()
    return templates.TemplateResponse(
        request,
        "recorrentes.html",
        {
            "ref": ref,
            "prev": add_months(ref, -1),
            "next": add_months(ref, 1),
            "rows": rows,
            "cards": cards,
            "verif": rule_month_status(session, ref),
            "today": date.today(),
        },
    )


@app.post("/recorrentes")
def create_recurring(
    description: str = Form(...),
    amount: str = Form(...),
    day: int = Form(...),
    kind: str = Form("despesa"),
    card_name: str = Form(""),
    variable: bool = Form(False),
    session: Session = Depends(get_session),
):
    if not 1 <= day <= 31:
        raise HTTPException(status_code=400, detail="Dia do mês deve estar entre 1 e 31")
    create_rule(session, description, parse_brl(amount), day, kind, card_name, variable)
    session.commit()
    generate_all(session)
    return RedirectResponse("/recorrentes", status_code=303)


@app.get("/recorrentes/{rule_id}/editar")
def edit_recurring_page(rule_id: int, request: Request, session: Session = Depends(get_session)):
    rule = session.get(RecurringRule, rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="Recorrência não encontrada")
    card = session.get(Account, rule.account_id) if rule.account_id else None
    cards = session.exec(select(Account).where(Account.type == "cartao")).all()
    return templates.TemplateResponse(
        request,
        "editar_recorrente.html",
        {"rule": rule, "card_name": card.name if card else "", "cards": cards},
    )


@app.post("/recorrentes/{rule_id}/editar")
def edit_recurring(
    rule_id: int,
    description: str = Form(...),
    amount: str = Form(...),
    day: int = Form(...),
    kind: str = Form("despesa"),
    card_name: str = Form(""),
    variable: bool = Form(False),
    session: Session = Depends(get_session),
):
    rule = session.get(RecurringRule, rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="Recorrência não encontrada")
    if not 1 <= day <= 31:
        raise HTTPException(status_code=400, detail="Dia do mês deve estar entre 1 e 31")
    update_rule(session, rule, description, parse_brl(amount), day, kind, card_name, variable)
    session.commit()
    return RedirectResponse("/recorrentes", status_code=303)


@app.post("/recorrentes/{rule_id}/ativar")
def toggle_rule(rule_id: int, session: Session = Depends(get_session)):
    rule = session.get(RecurringRule, rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="Recorrência não encontrada")
    set_active(session, rule, not rule.active)
    session.commit()
    generate_all(session)
    return RedirectResponse("/recorrentes", status_code=303)


@app.post("/recorrentes/{rule_id}/excluir")
def delete_recurring(rule_id: int, session: Session = Depends(get_session)):
    rule = session.get(RecurringRule, rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="Recorrência não encontrada")
    delete_rule(session, rule)
    session.commit()
    return RedirectResponse("/recorrentes", status_code=303)

@app.get("/configuracoes")
def configuracoes_page(request: Request, session: Session = Depends(get_session)):
    tamanho = DB_PATH.stat().st_size / 1024 / 1024 if DB_PATH.exists() else 0
    return templates.TemplateResponse(
        request,
        "configuracoes.html",
        {
            "horizonte": int(get_setting(session, "projecao_meses")),
            "tamanho_mb": f"{tamanho:.2f}".replace(".", ","),
        },
    )


@app.get("/configuracoes/backup")
def baixar_backup():
    nome = f"financas-backup-{date.today():%Y-%m-%d}.db"
    return FileResponse(DB_PATH, filename=nome, media_type="application/octet-stream")


@app.post("/configuracoes/importar")
async def importar_backup(arquivo: UploadFile = File(...)):
    conteudo = await arquivo.read()
    if not conteudo.startswith(b"SQLite format 3\x00"):
        raise HTTPException(status_code=400, detail="O arquivo não é um banco SQLite válido")
    engine.dispose()
    if DB_PATH.exists():
        shutil.copyfile(DB_PATH, DB_PATH.with_name("finance-antes-da-importacao.db"))
    DB_PATH.write_bytes(conteudo)
    init_db()
    return RedirectResponse("/configuracoes", status_code=303)


@app.post("/configuracoes/apagar")
def apagar_dados(confirmacao: str = Form(...), session: Session = Depends(get_session)):
    if confirmacao.strip() != "APAGAR":
        raise HTTPException(status_code=400, detail="Digite APAGAR para confirmar")
    for table in reversed(SQLModel.metadata.sorted_tables):
        if table.name == "setting":
            continue
        session.execute(table.delete())
    session.commit()
    return RedirectResponse("/configuracoes", status_code=303)


@app.post("/configuracoes/projecao")
def salvar_projecao(meses: int = Form(...), session: Session = Depends(get_session)):
    if not 1 <= meses <= 12:
        raise HTTPException(status_code=400, detail="Use de 1 a 12 meses")
    set_setting(session, "projecao_meses", str(meses))
    return RedirectResponse("/configuracoes", status_code=303)

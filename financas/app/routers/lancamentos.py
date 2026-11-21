"""Início e lançamentos: criar, editar, pagar e excluir."""

from datetime import date
from urllib.parse import quote

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from sqlmodel import Session, select

from app.db import get_session
from app.models import Transaction, TransactionTag
from app.services.charts import receitas_despesas_mensal
from app.services.edit import update_transaction
from app.services.recurring import generate_all
from app.services.settings import get_int_setting
from app.services.parcelados import generate_installments
from app.services.summary import card_account_ids, monthly_summary, overdue_items
from app.services.tags import (
    parse_tags,
    set_tags,
    tag_text,
    tags_by_tx,
    tags_com_id_by_tx,
    validar_categorias_livres,
)
from app.services.util import add_months, current_month, month_bounds, parse_brl
from app.web import RedirectResponse, templates

router = APIRouter()


def _parse_third(value: str, amount_cents: int, kind: str) -> int | None:
    """Terceiros só existe em despesa, e não pode passar do valor do lançamento."""
    if kind != "despesa" or not value.strip():
        return None
    third = parse_brl(value)
    if third < 0 or third > amount_cents:
        raise ValueError("Terceiros deve estar entre 0 e o valor do lançamento.")
    return third or None


def _third_text(tx: Transaction) -> str:
    if not tx.third_party_cents:
        return ""
    return f"{tx.third_party_cents / 100:.2f}".replace(".", ",")


def _validar_tags(session: Session, tags: str, tx_id: int | None = None) -> None:
    validar_categorias_livres(session, tags, tx_id=tx_id)


def _volta_com_erro(url: str, mensagem: str) -> RedirectResponse:
    """Volta para a tela com a mensagem de erro. Nada é gravado."""
    separador = "&" if "?" in url else "?"
    return RedirectResponse(f"{url}{separador}erro={quote(mensagem)}", status_code=303)


def _delete_tx(session: Session, tx: Transaction) -> None:
    for link in session.exec(
        select(TransactionTag).where(TransactionTag.transaction_id == tx.id)
    ).all():
        session.delete(link)
    session.delete(tx)


@router.get("/")
def home(
    request: Request,
    mes: str | None = None,
    erro: str | None = None,
    session: Session = Depends(get_session),
):
    generate_all(session)
    generate_installments(session)
    ref = mes or current_month()
    start, end = month_bounds(ref)
    cards = card_account_ids(session)
    antes = get_int_setting(session, "grafico_antes", 1, 24)
    depois = get_int_setting(session, "grafico_depois", 0, 12)

    txs = session.exec(
        select(Transaction)
        .where(Transaction.due_date >= start, Transaction.due_date < end)
        .order_by(Transaction.due_date)
    ).all()
    txs = [t for t in txs if t.account_id not in cards]
    txs.sort(key=lambda t: {"receita": 0, "despesa": 1}.get(t.kind, 2))

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
            "tag_map": tags_com_id_by_tx(session, [t.id for t in txs]),
            "atrasados": overdue_items(session),
            "antes": antes,
            "grafico": receitas_despesas_mensal(session, ref, antes, depois),
            "erro": erro,
        },
    )


@router.post("/lancamentos")
def create_transaction(
    description: str = Form(...),
    amount: str = Form(...),
    due_date: date = Form(...),
    kind: str = Form("despesa"),
    third_party: str = Form(""),
    tags: str = Form(""),
    session: Session = Depends(get_session),
):
    try:
        _validar_tags(session, tags)
        amount_cents = parse_brl(amount)
        terceiros = _parse_third(third_party, amount_cents, kind)
    except ValueError as e:
        session.rollback()
        return _volta_com_erro(f"/?mes={due_date:%Y-%m}", str(e))
    tx = Transaction(
        description=description,
        amount_cents=amount_cents,
        due_date=due_date,
        kind=kind,
        status="pendente",
        third_party_cents=terceiros,
    )
    session.add(tx)
    session.flush()
    set_tags(session, tx, parse_tags(tags))
    session.commit()
    return RedirectResponse(f"/?mes={due_date:%Y-%m}", status_code=303)


@router.get("/lancamentos/{tx_id}/editar")
def edit_transaction_page(
    tx_id: int,
    request: Request,
    erro: str | None = None,
    session: Session = Depends(get_session),
):
    tx = session.get(Transaction, tx_id)
    if tx is None:
        raise HTTPException(status_code=404, detail="Lançamento não encontrado")
    return templates.TemplateResponse(
        request,
        "editar_lancamento.html",
        {
            "tx": tx,
            "tags_text": tag_text(session, tx.id),
            "third_text": _third_text(tx),
            "erro": erro,
        },
    )


@router.post("/lancamentos/{tx_id}/editar")
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
    try:
        _validar_tags(session, tags, tx_id)
        amount_cents = parse_brl(amount)
        terceiros = _parse_third(third_party, amount_cents, kind)
    except ValueError as e:
        session.rollback()
        return _volta_com_erro(f"/lancamentos/{tx_id}/editar", str(e))
    update_transaction(session, tx, description, amount_cents, due_date, kind)
    tx.third_party_cents = terceiros
    session.add(tx)
    set_tags(session, tx, parse_tags(tags))
    session.commit()
    return RedirectResponse(f"/?mes={due_date:%Y-%m}", status_code=303)


@router.post("/transacoes/{tx_id}/pagar")
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


@router.post("/transacoes/{tx_id}/excluir")
def delete_transaction(tx_id: int, mes: str = Form(...), session: Session = Depends(get_session)):
    tx = session.get(Transaction, tx_id)
    if tx is None:
        raise HTTPException(status_code=404, detail="Lançamento não encontrado")
    _delete_tx(session, tx)
    session.commit()
    return RedirectResponse(f"/?mes={mes}", status_code=303)

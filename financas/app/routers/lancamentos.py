"""Início e lançamentos: criar, editar, pagar e excluir."""

from datetime import date
from urllib.parse import quote

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from sqlmodel import Session, select

from app.db import get_session
from app.models import Account, FaturaCartao, Transaction, TransactionTag
from app.services.cartoes import alternar_pagamento, fatura_de_transacao
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
    tags_com_id_by_tx,
    validar_categorias_livres,
)
from app.services.util import add_months, current_month, mes_curto, month_bounds, parse_brl
from app.web import RedirectResponse, templates

router = APIRouter()

MSG_FATURA = "Este lançamento é da fatura de um cartão. Edite ou exclua pela tela Cartões."


def _volta_com_erro(url: str, mensagem: str) -> RedirectResponse:
    """Volta para a tela com a mensagem de erro. Nada é gravado."""
    separador = "&" if "?" in url else "?"
    return RedirectResponse(f"{url}{separador}erro={quote(mensagem)}", status_code=303)


def _validar_tags(session: Session, tags: str, tx_id: int | None = None) -> None:
    validar_categorias_livres(session, tags, tx_id=tx_id)


def _delete_tx(session: Session, tx: Transaction) -> None:
    for link in session.exec(
        select(TransactionTag).where(TransactionTag.transaction_id == tx.id)
    ).all():
        session.delete(link)
    session.delete(tx)


def _mapa_faturas(session: Session) -> dict[int, str]:
    """Lançamentos que são fatura (despesa ou reembolso de terceiro) -> nome do cartão."""
    mapa: dict[int, str] = {}
    for f in session.exec(select(FaturaCartao)).all():
        conta = session.get(Account, f.account_id)
        nome = f"{conta.name if conta else ''} - {mes_curto(f.referencia)}"
        mapa[f.tx_despesa_id] = nome
        if f.tx_receita_id:
            mapa[f.tx_receita_id] = nome
        for t in session.exec(select(Transaction).where(Transaction.fatura_id == f.id)).all():
            mapa[t.id] = nome
    return mapa


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
    def grupo(t):
        if t.reembolso:
            return "reembolso"
        return t.kind

    # Receitas, depois o que é a receber de terceiros (laranja), depois despesas
    ordem = {"receita": 0, "reembolso": 1, "despesa": 2}
    txs.sort(key=lambda t: ordem.get(grupo(t), 3))
    reembolsos_total = sum(t.amount_cents for t in txs if t.reembolso and t.kind == "receita")

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
            "reembolsos_total": reembolsos_total,
            "tag_map": tags_com_id_by_tx(session, [t.id for t in txs]),
            "fatura_map": _mapa_faturas(session),
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
    tags: str = Form(""),
    session: Session = Depends(get_session),
):
    try:
        _validar_tags(session, tags)
        amount_cents = parse_brl(amount)
    except ValueError as e:
        session.rollback()
        return _volta_com_erro(f"/?mes={due_date:%Y-%m}", str(e))
    tx = Transaction(
        description=description,
        amount_cents=amount_cents,
        due_date=due_date,
        kind=kind,
        status="pendente",
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
    if fatura_de_transacao(session, tx) is not None:
        return _volta_com_erro(f"/?mes={tx.due_date:%Y-%m}", MSG_FATURA)
    return templates.TemplateResponse(
        request,
        "editar_lancamento.html",
        {
            "tx": tx,
            "tags_text": tag_text(session, tx.id),
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
    tags: str = Form(""),
    session: Session = Depends(get_session),
):
    tx = session.get(Transaction, tx_id)
    if tx is None:
        raise HTTPException(status_code=404, detail="Lançamento não encontrado")
    if fatura_de_transacao(session, tx) is not None:
        return _volta_com_erro(f"/?mes={tx.due_date:%Y-%m}", MSG_FATURA)
    try:
        _validar_tags(session, tags, tx_id)
        amount_cents = parse_brl(amount)
    except ValueError as e:
        session.rollback()
        return _volta_com_erro(f"/lancamentos/{tx_id}/editar", str(e))
    update_transaction(session, tx, description, amount_cents, due_date, kind)
    session.add(tx)
    set_tags(session, tx, parse_tags(tags))
    session.commit()
    return RedirectResponse(f"/?mes={due_date:%Y-%m}", status_code=303)


@router.post("/transacoes/{tx_id}/pagar")
def toggle_paid(
    tx_id: int,
    mes: str = Form(...),
    voltar: str = Form(""),
    session: Session = Depends(get_session),
):
    tx = session.get(Transaction, tx_id)
    if tx is None:
        raise HTTPException(status_code=404, detail="Lançamento não encontrado")
    alternar_pagamento(session, tx)
    session.commit()
    if voltar == "cartoes":
        return RedirectResponse(f"/cartoes?mes={quote(mes)}", status_code=303)
    return RedirectResponse(f"/?mes={mes}", status_code=303)


@router.post("/transacoes/{tx_id}/excluir")
def delete_transaction(tx_id: int, mes: str = Form(...), session: Session = Depends(get_session)):
    tx = session.get(Transaction, tx_id)
    if tx is None:
        raise HTTPException(status_code=404, detail="Lançamento não encontrado")
    if fatura_de_transacao(session, tx) is not None:
        return _volta_com_erro(f"/?mes={mes}", MSG_FATURA)
    _delete_tx(session, tx)
    session.commit()
    return RedirectResponse(f"/?mes={mes}", status_code=303)

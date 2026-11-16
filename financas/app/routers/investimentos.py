"""Investimentos: caixinhas com valor atual, histórico e gráfico de evolução."""

from datetime import date
from urllib.parse import quote

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from sqlmodel import Session

from app.db import get_session
from app.models import Investimento
from app.services.investimentos import (
    TIPOS,
    atualizar_valor,
    criar,
    editar,
    evolucao_total,
    excluir,
    historico_com_variacao,
    listar,
    total,
)
from app.services.util import parse_brl
from app.web import RedirectResponse, templates

router = APIRouter()


def _get(session: Session, inv_id: int) -> Investimento:
    inv = session.get(Investimento, inv_id)
    if inv is None:
        raise HTTPException(status_code=404, detail="Caixinha não encontrada")
    return inv


def _data(texto: str) -> date | None:
    texto = texto.strip()
    if not texto:
        return None
    try:
        return date.fromisoformat(texto)
    except ValueError:
        raise ValueError("Data inválida")


def _erro(destino: str, mensagem: str) -> RedirectResponse:
    return RedirectResponse(f"{destino}?erro={quote(mensagem)}", status_code=303)


@router.get("/investimentos")
def investimentos_page(request: Request, erro: str | None = None, session: Session = Depends(get_session)):
    return templates.TemplateResponse(
        request,
        "investimentos.html",
        {
            "invs": listar(session),
            "tipos": TIPOS,
            "total": total(session),
            "erro": erro,
            "grafico": evolucao_total(session),
            "hoje": date.today().isoformat(),
        },
    )


@router.post("/investimentos")
def criar_investimento(
    nome: str = Form(...),
    tipo: str = Form("outro"),
    valor: str = Form(...),
    session: Session = Depends(get_session),
):
    try:
        criar(session, nome, tipo, parse_brl(valor))
    except (ValueError, ArithmeticError) as e:
        session.rollback()
        return _erro("/investimentos", str(e))
    session.commit()
    return RedirectResponse("/investimentos", status_code=303)


@router.get("/investimentos/{inv_id}")
def investimento_page(
    inv_id: int,
    request: Request,
    erro: str | None = None,
    session: Session = Depends(get_session),
):
    inv = _get(session, inv_id)
    hist = historico_com_variacao(session, inv.id)
    variacao_total = hist[-1]["valor"] - hist[0]["valor"] if hist else 0
    return templates.TemplateResponse(
        request,
        "investimento_detalhe.html",
        {
            "inv": inv,
            "tipos": TIPOS,
            "hist": hist,
            "variacao_total": variacao_total,
            "erro": erro,
            "hoje": date.today().isoformat(),
            "grafico": {
                "labels": [h["data"].strftime("%d/%m/%Y") for h in hist],
                "valores": [h["valor"] / 100 for h in hist],
            },
        },
    )


@router.post("/investimentos/{inv_id}/valor")
def atualizar_valor_investimento(
    inv_id: int,
    valor: str = Form(...),
    data: str = Form(""),
    volta: str = Form(""),
    session: Session = Depends(get_session),
):
    inv = _get(session, inv_id)
    destino = f"/investimentos/{inv.id}" if volta == "detalhe" else "/investimentos"
    try:
        atualizar_valor(session, inv, parse_brl(valor), _data(data))
    except (ValueError, ArithmeticError) as e:
        session.rollback()
        return _erro(destino, str(e))
    session.commit()
    return RedirectResponse(destino, status_code=303)


@router.post("/investimentos/{inv_id}/editar")
def editar_investimento(
    inv_id: int,
    nome: str = Form(...),
    tipo: str = Form("outro"),
    session: Session = Depends(get_session),
):
    inv = _get(session, inv_id)
    try:
        editar(session, inv, nome, tipo)
    except ValueError as e:
        session.rollback()
        return _erro(f"/investimentos/{inv.id}", str(e))
    session.commit()
    return RedirectResponse(f"/investimentos/{inv.id}", status_code=303)


@router.post("/investimentos/{inv_id}/excluir")
def excluir_investimento(inv_id: int, session: Session = Depends(get_session)):
    inv = _get(session, inv_id)
    excluir(session, inv)
    session.commit()
    return RedirectResponse("/investimentos", status_code=303)

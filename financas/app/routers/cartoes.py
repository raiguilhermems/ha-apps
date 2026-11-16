"""Cartões: cadastro, edição e exclusão."""

from urllib.parse import quote

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from sqlmodel import Session

from app.db import get_session
from app.models import Account
from app.services.cartoes import atualizar, criar, excluir, listar, vinculos
from app.web import RedirectResponse, templates

router = APIRouter()


def _dia(texto: str) -> int | None:
    texto = texto.strip()
    if not texto:
        return None
    try:
        return int(texto)
    except ValueError:
        raise ValueError("Dia de pagamento deve ser um número")


def _erro(mensagem: str) -> RedirectResponse:
    return RedirectResponse(f"/cartoes?erro={quote(mensagem)}", status_code=303)


def _cartao(session: Session, cartao_id: int) -> Account:
    cartao = session.get(Account, cartao_id)
    if cartao is None or cartao.type != "cartao":
        raise HTTPException(status_code=404, detail="Cartão não encontrado")
    return cartao


@router.get("/cartoes")
def cartoes_page(request: Request, erro: str | None = None, session: Session = Depends(get_session)):
    cartoes = listar(session)
    return templates.TemplateResponse(
        request,
        "cartoes.html",
        {
            "cartoes": cartoes,
            "erro": erro,
            "vinculos": {c.id: vinculos(session, c) for c in cartoes},
        },
    )


@router.post("/cartoes")
def criar_cartao(nome: str = Form(...), dia: str = Form(""), session: Session = Depends(get_session)):
    try:
        criar(session, nome, _dia(dia))
    except ValueError as e:
        session.rollback()
        return _erro(str(e))
    session.commit()
    return RedirectResponse("/cartoes", status_code=303)


@router.post("/cartoes/{cartao_id}/atualizar")
def atualizar_cartao(
    cartao_id: int,
    nome: str = Form(...),
    dia: str = Form(""),
    session: Session = Depends(get_session),
):
    cartao = _cartao(session, cartao_id)
    try:
        atualizar(session, cartao, nome, _dia(dia))
    except ValueError as e:
        session.rollback()
        return _erro(str(e))
    session.commit()
    return RedirectResponse("/cartoes", status_code=303)


@router.post("/cartoes/{cartao_id}/excluir")
def excluir_cartao(cartao_id: int, session: Session = Depends(get_session)):
    cartao = _cartao(session, cartao_id)
    try:
        excluir(session, cartao)
    except ValueError as e:
        session.rollback()
        return _erro(str(e))
    session.commit()
    return RedirectResponse("/cartoes", status_code=303)

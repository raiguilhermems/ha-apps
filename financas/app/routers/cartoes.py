"""Cartões: cadastro, fatura mensal e exclusão da fatura."""

from urllib.parse import quote

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from sqlmodel import Session, select

from app.db import get_session
from app.models import Account, FaturaItem, Tag, Transaction
from app.services.cartoes import (
    MES_RE,
    aplicar_edicoes,
    atualizar,
    buscar_fatura,
    criar,
    excluir,
    excluir_fatura,
    listar,
    lancar_fatura,
    resumo_fatura,
    vinculos,
)
from app.services.util import current_month, parse_brl
from app.web import RedirectResponse, templates

router = APIRouter()


def _dia(texto: str, rotulo: str) -> int | None:
    texto = texto.strip()
    if not texto:
        return None
    try:
        return int(texto)
    except ValueError:
        raise ValueError(f"{rotulo} deve ser um número")


def _fechamento(texto: str) -> int:
    dia = _dia(texto, "Fechamento")
    if dia is None:
        raise ValueError("Informe o dia de fechamento da fatura (de 1 a 31)")
    return dia


def _valor(texto: str, rotulo: str) -> int:
    texto = texto.strip()
    if not texto:
        return 0
    try:
        return parse_brl(texto)
    except ValueError:
        raise ValueError(f"{rotulo} inválido. Use o formato 1.234,56")


def _url(mes: str | None, **params: str) -> str:
    partes = [f"{k}={quote(v)}" for k, v in params.items() if v]
    if mes:
        partes.insert(0, f"mes={quote(mes)}")
    return "/cartoes" + ("?" + "&".join(partes) if partes else "")


def _cartao(session: Session, cartao_id: int) -> Account:
    cartao = session.get(Account, cartao_id)
    if cartao is None or cartao.type != "cartao":
        raise HTTPException(status_code=404, detail="Cartão não encontrado")
    return cartao


@router.get("/cartoes")
def cartoes_page(
    request: Request,
    mes: str | None = None,
    erro: str | None = None,
    ok: str | None = None,
    session: Session = Depends(get_session),
):
    ref = mes if mes and MES_RE.fullmatch(mes) else current_month()
    cartoes = listar(session)
    return templates.TemplateResponse(
        request,
        "cartoes.html",
        {
            "ref": ref,
            "cartoes": cartoes,
            "resumos": [resumo_fatura(session, c, ref) for c in cartoes],
            "vinculos": {c.id: vinculos(session, c) for c in cartoes},
            "erro": erro,
            "ok": ok,
        },
    )


@router.post("/cartoes")
def criar_cartao(
    nome: str = Form(...),
    dia: str = Form(""),
    fechamento: str = Form(""),
    session: Session = Depends(get_session),
):
    try:
        criar(session, nome, _dia(dia, "Vencimento"), _fechamento(fechamento))
    except ValueError as e:
        session.rollback()
        return RedirectResponse(_url(None, erro=str(e)), status_code=303)
    session.commit()
    return RedirectResponse(_url(None, ok="criado"), status_code=303)


@router.post("/cartoes/{cartao_id}/atualizar")
def atualizar_cartao(
    cartao_id: int,
    nome: str = Form(...),
    dia: str = Form(""),
    fechamento: str = Form(""),
    session: Session = Depends(get_session),
):
    cartao = _cartao(session, cartao_id)
    try:
        atualizar(session, cartao, nome, _dia(dia, "Vencimento"), _fechamento(fechamento))
    except ValueError as e:
        session.rollback()
        return RedirectResponse(_url(None, erro=str(e)), status_code=303)
    session.commit()
    return RedirectResponse(_url(None, ok="salvo"), status_code=303)


@router.post("/cartoes/{cartao_id}/excluir")
def excluir_cartao(cartao_id: int, session: Session = Depends(get_session)):
    cartao = _cartao(session, cartao_id)
    try:
        excluir(session, cartao)
    except ValueError as e:
        session.rollback()
        return RedirectResponse(_url(None, erro=str(e)), status_code=303)
    session.commit()
    return RedirectResponse(_url(None, ok="excluido"), status_code=303)


@router.post("/cartoes/{cartao_id}/fatura")
def salvar_fatura(
    cartao_id: int,
    mes: str = Form(...),
    total: str = Form(""),
    terceiro: str = Form(""),
    pessoa: str = Form(""),
    session: Session = Depends(get_session),
):
    cartao = _cartao(session, cartao_id)
    try:
        lancar_fatura(
            session,
            cartao,
            mes,
            _valor(total, "Total da fatura"),
            _valor(terceiro, "Pago por terceiro"),
            pessoa,
        )
    except ValueError as e:
        session.rollback()
        return RedirectResponse(_url(mes, erro=str(e)), status_code=303)
    session.commit()
    return RedirectResponse(_url(mes, ok="fatura"), status_code=303)


@router.post("/cartoes/{cartao_id}/fatura/excluir")
def excluir_fatura_cartao(
    cartao_id: int,
    mes: str = Form(...),
    session: Session = Depends(get_session),
):
    cartao = _cartao(session, cartao_id)
    fatura = buscar_fatura(session, cartao.id, mes)
    if fatura is None:
        return RedirectResponse(_url(mes, erro="Esta fatura não está lançada"), status_code=303)
    try:
        excluir_fatura(session, fatura)
    except ValueError as e:
        session.rollback()
        return RedirectResponse(_url(mes, erro=str(e)), status_code=303)
    session.commit()
    return RedirectResponse(_url(mes, ok="fatura_excluida"), status_code=303)


def _fatura_do_mes(session: Session, cartao: Account, mes: str):
    fatura = buscar_fatura(session, cartao.id, mes)
    if fatura is None:
        raise ValueError("Esta fatura não está lançada")
    return fatura


@router.get("/cartoes/{cartao_id}/fatura/editar")
def editar_fatura_page(
    request: Request,
    cartao_id: int,
    mes: str,
    erro: str | None = None,
    session: Session = Depends(get_session),
):
    cartao = _cartao(session, cartao_id)
    fatura = buscar_fatura(session, cartao.id, mes) if MES_RE.fullmatch(mes) else None
    if fatura is None:
        return RedirectResponse(_url(mes, erro="Esta fatura não está lançada"), status_code=303)
    itens = session.exec(
        select(FaturaItem).where(FaturaItem.fatura_id == fatura.id).order_by(FaturaItem.id)
    ).all()
    despesa = session.get(Transaction, fatura.tx_despesa_id)
    pessoas = [t.name for t in session.exec(select(Tag).where(Tag.kind == "pessoa").order_by(Tag.name)).all()]
    return templates.TemplateResponse(
        request,
        "editar_fatura.html",
        {
            "cartao": cartao,
            "fatura": fatura,
            "ref": mes,
            "itens": itens,
            "pessoas": pessoas,
            "paga": despesa is not None and despesa.status == "pago",
            "erro": erro,
        },
    )


@router.post("/cartoes/{cartao_id}/fatura/editar")
async def salvar_edicao_fatura(
    cartao_id: int,
    request: Request,
    mes: str = Form(...),
    session: Session = Depends(get_session),
):
    cartao = _cartao(session, cartao_id)
    form = await request.form()
    total = str(form.get("total", ""))
    terceiro = str(form.get("terceiro", ""))
    pessoa_manual = str(form.get("pessoa", ""))
    alteracoes = []
    for i in form.getlist("ids"):
        i = str(i)
        pessoa = str(form.get(f"pessoa_{i}", "")).strip()
        alteracoes.append(
            {
                "id": int(i),
                "descricao": str(form.get(f"descricao_{i}", "")),
                # Com nome de terceiro, a compra é dele; em branco, é sua
                "destino": "terceiro" if pessoa else "sua",
                "pessoa": pessoa,
                "categorias": str(form.get(f"categorias_{i}", "")),
                "remover": f"remover_{i}" in form,
            }
        )
    try:
        fatura = _fatura_do_mes(session, cartao, mes)
        aplicar_edicoes(session, cartao, fatura, alteracoes)
        lancar_fatura(
            session,
            cartao,
            mes,
            _valor(total, "Total da fatura"),
            _valor(terceiro, "Pago por terceiro"),
            pessoa_manual,
        )
    except ValueError as e:
        session.rollback()
        return RedirectResponse(
            f"/cartoes/{cartao_id}/fatura/editar?mes={quote(mes)}&erro={quote(str(e))}", status_code=303
        )
    session.commit()
    return RedirectResponse(_url(mes, ok="item_salvo"), status_code=303)

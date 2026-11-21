"""Categorias (antigas tags): lista, criar, editar, excluir e relatório mensal."""

from datetime import date
from urllib.parse import quote

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from sqlmodel import Session, select

from app.db import get_session
from app.services.charts import categoria_mensal, soma_categoria_periodo
from app.services.settings import get_int_setting
from app.models import Account, Tag, TransactionTag
from app.services.parcelados import ids_da_pessoa, renomear_pessoa
from app.services.tags import (
    CATEGORIA,
    PESSOA,
    RECORRENTE,
    parse_tags,
    reservar_categoria,
    transactions_with_tag,
)
from app.services.util import add_months, current_month, month_bounds
from app.web import RedirectResponse, templates

router = APIRouter()


def _erro(destino: str, mensagem: str) -> RedirectResponse:
    return RedirectResponse(f"{destino}?erro={quote(mensagem)}", status_code=303)


@router.get("/categorias")
def tags_page(
    request: Request,
    erro: str | None = None,
    ok: str | None = None,
    session: Session = Depends(get_session),
):
    tags = session.exec(select(Tag).order_by(Tag.name)).all()
    pessoas = [t for t in tags if t.kind == PESSOA]
    recorrentes = [t for t in tags if t.kind == RECORRENTE]
    categorias = [t for t in tags if t.kind not in (PESSOA, RECORRENTE)]
    return templates.TemplateResponse(
        request,
        "tags.html",
        {
            "pessoas": pessoas,
            "recorrentes": recorrentes,
            "categorias": categorias,
            "erro": erro,
            "ok": ok,
        },
    )


@router.get("/tags")
def tags_antigo():
    return RedirectResponse("/categorias", status_code=303)


@router.post("/categorias")
def create_tag(
    name: str = Form(...),
    excludes: bool = Form(False),
    tipo: str = Form("categoria"),
    session: Session = Depends(get_session),
):
    names = parse_tags(name)
    if not names:
        return _erro("/categorias", "Informe um nome para a categoria.")
    if tipo not in (CATEGORIA, PESSOA):
        return _erro("/categorias", "Tipo inválido.")
    # Mesma regra de nome único do resto do app: não reaproveita nome de outro tipo
    permitidos = ids_da_pessoa(session, names[0]) if tipo == PESSOA else set()
    rotulo = "a pessoa" if tipo == PESSOA else "uma categoria"
    try:
        tag = reservar_categoria(session, names[0], tipo, permitidos, rotulo)
    except ValueError as e:
        session.rollback()
        return _erro("/categorias", str(e))
    tag.excludes_from_total = excludes
    session.add(tag)
    session.commit()
    return RedirectResponse("/categorias?ok=criada", status_code=303)


@router.post("/categorias/{tag_id}/atualizar")
def update_tag(
    tag_id: int,
    name: str = Form(...),
    excludes: bool = Form(False),
    tipo: str | None = Form(None),
    session: Session = Depends(get_session),
):
    destino = f"/categorias/{tag_id}/editar"
    tag = session.get(Tag, tag_id)
    if tag is None:
        raise HTTPException(status_code=404, detail="Categoria não encontrada")
    if tag.kind == RECORRENTE:
        return _erro(destino, "Esta categoria vem de uma recorrência. Edite o nome e o tipo na aba Recorrentes.")
    names = parse_tags(name)
    if not names:
        return _erro(destino, "Informe um nome para a categoria.")
    clash = session.exec(select(Tag).where(Tag.name == names[0], Tag.id != tag.id)).first()
    if clash:
        return _erro(destino, "Já existe uma categoria com esse nome.")
    if tipo is not None:
        if tipo not in (CATEGORIA, PESSOA):
            return _erro(destino, "Tipo inválido.")
        if tag.kind == PESSOA and tipo != PESSOA:
            return _erro(destino, "Pessoa é definida pelas compras a receber e não pode virar categoria.")
        if tipo == PESSOA and tag.kind != PESSOA:
            try:
                reservar_categoria(session, tag.name, PESSOA, ids_da_pessoa(session, tag.name), "a pessoa")
            except ValueError as e:
                session.rollback()
                return _erro(destino, str(e))
    try:
        if tag.kind == PESSOA and names[0] != tag.name:
            renomear_pessoa(session, tag, name)
        else:
            tag.name = names[0]
    except ValueError as e:
        session.rollback()
        return _erro(destino, str(e))
    tag.excludes_from_total = excludes
    session.add(tag)
    session.commit()
    return RedirectResponse("/categorias?ok=salva", status_code=303)


@router.post("/categorias/{tag_id}/excluir")
def delete_tag(tag_id: int, session: Session = Depends(get_session)):
    tag = session.get(Tag, tag_id)
    if tag is None:
        raise HTTPException(status_code=404, detail="Categoria não encontrada")
    if tag.kind == RECORRENTE:
        return _erro("/categorias", "Esta categoria vem de uma recorrência. Exclua a recorrência para removê-la.")
    for link in session.exec(select(TransactionTag).where(TransactionTag.tag_id == tag.id)).all():
        session.delete(link)
    session.delete(tag)
    session.commit()
    return RedirectResponse("/categorias?ok=excluida", status_code=303)


@router.get("/categorias/{tag_id}")
def tag_report(tag_id: int, request: Request, mes: str | None = None, session: Session = Depends(get_session)):
    tag = session.get(Tag, tag_id)
    if tag is None:
        raise HTTPException(status_code=404, detail="Categoria não encontrada")
    ref = mes or current_month()
    antes = get_int_setting(session, "grafico_antes", 1, 24)
    depois = get_int_setting(session, "grafico_depois", 0, 12)
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
            "today": date.today(),
            "grafico": categoria_mensal(session, tag.id, ref, antes, depois),
            "antes": antes,
            "soma6": soma_categoria_periodo(session, tag.id, ref, antes),
        },
    )


@router.get("/categorias/{tag_id}/editar")
def editar_categoria_page(
    tag_id: int,
    request: Request,
    erro: str | None = None,
    session: Session = Depends(get_session),
):
    tag = session.get(Tag, tag_id)
    if tag is None:
        raise HTTPException(status_code=404, detail="Categoria não encontrada")
    return templates.TemplateResponse(request, "editar_categoria.html", {"tag": tag, "erro": erro})

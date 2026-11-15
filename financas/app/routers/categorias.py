"""Categorias (antigas tags): lista, criar, editar, excluir e relatório mensal."""

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from sqlmodel import Session, select

from app.db import get_session
from app.models import Account, Tag, TransactionTag
from app.services.tags import get_or_create_tag, parse_tags, transactions_with_tag
from app.services.util import add_months, current_month, month_bounds
from app.web import RedirectResponse, templates

router = APIRouter()


@router.get("/categorias")
def tags_page(request: Request, session: Session = Depends(get_session)):
    tags = session.exec(select(Tag).order_by(Tag.name)).all()
    return templates.TemplateResponse(request, "tags.html", {"tags": tags})


@router.get("/tags")
def tags_antigo():
    return RedirectResponse("/categorias", status_code=303)


@router.post("/categorias")
def create_tag(
    name: str = Form(...),
    excludes: bool = Form(False),
    session: Session = Depends(get_session),
):
    names = parse_tags(name)
    if not names:
        raise HTTPException(status_code=400, detail="Informe um nome para a categoria")
    tag = get_or_create_tag(session, names[0])
    tag.excludes_from_total = excludes
    session.add(tag)
    session.commit()
    return RedirectResponse("/categorias", status_code=303)


@router.post("/categorias/{tag_id}/atualizar")
def update_tag(
    tag_id: int,
    name: str = Form(...),
    excludes: bool = Form(False),
    session: Session = Depends(get_session),
):
    tag = session.get(Tag, tag_id)
    if tag is None:
        raise HTTPException(status_code=404, detail="Categoria não encontrada")
    names = parse_tags(name)
    if not names:
        raise HTTPException(status_code=400, detail="Informe um nome para a categoria")
    clash = session.exec(select(Tag).where(Tag.name == names[0], Tag.id != tag.id)).first()
    if clash:
        raise HTTPException(status_code=400, detail="Já existe uma categoria com esse nome")
    tag.name = names[0]
    tag.excludes_from_total = excludes
    session.add(tag)
    session.commit()
    return RedirectResponse("/categorias", status_code=303)


@router.post("/categorias/{tag_id}/excluir")
def delete_tag(tag_id: int, session: Session = Depends(get_session)):
    tag = session.get(Tag, tag_id)
    if tag is None:
        raise HTTPException(status_code=404, detail="Categoria não encontrada")
    for link in session.exec(select(TransactionTag).where(TransactionTag.tag_id == tag.id)).all():
        session.delete(link)
    session.delete(tag)
    session.commit()
    return RedirectResponse("/categorias", status_code=303)


@router.get("/categorias/{tag_id}")
def tag_report(tag_id: int, request: Request, mes: str | None = None, session: Session = Depends(get_session)):
    tag = session.get(Tag, tag_id)
    if tag is None:
        raise HTTPException(status_code=404, detail="Categoria não encontrada")
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


@router.get("/categorias/{tag_id}/editar")
def editar_categoria_page(tag_id: int, request: Request, session: Session = Depends(get_session)):
    tag = session.get(Tag, tag_id)
    if tag is None:
        raise HTTPException(status_code=404, detail="Categoria não encontrada")
    return templates.TemplateResponse(request, "editar_categoria.html", {"tag": tag})

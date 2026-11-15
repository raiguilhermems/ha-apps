"""Recorrentes: contas fixas e receitas que se repetem todo mês."""

from datetime import date

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from sqlmodel import Session, select

from app.db import get_session
from app.models import Account, RecurringRule, Tag
from app.services.edit import update_rule
from app.services.recurring import (
    create_rule,
    delete_rule,
    generate_all,
    rule_month_status,
    set_active,
)
from app.services.settings import get_setting
from app.services.tags import parse_tags
from app.services.util import add_months, current_month, parse_brl
from app.web import RedirectResponse, templates

router = APIRouter()


@router.get("/recorrentes")
def recorrentes_page(request: Request, mes: str | None = None, session: Session = Depends(get_session)):
    ref = mes or current_month()
    rules = session.exec(select(RecurringRule).order_by(RecurringRule.description)).all()
    ids = {c.name: c.id for c in session.exec(select(Tag)).all()}
    rows = []
    for r in rules:
        card = session.get(Account, r.account_id) if r.account_id else None
        cats = [{"nome": n, "id": ids.get(n)} for n in parse_tags(r.tags_text)]
        rows.append({"rule": r, "cartao": card.name if card else "—", "cats": cats})
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
            "dia_padrao": int(get_setting(session, "dia_padrao")),
            "today": date.today(),
        },
    )


@router.post("/recorrentes")
def create_recurring(
    description: str = Form(...),
    amount: str = Form(...),
    day: int = Form(...),
    kind: str = Form("despesa"),
    card_name: str = Form(""),
    variable: bool = Form(False),
    categorias: str = Form(""),
    session: Session = Depends(get_session),
):
    if not 0 <= day <= 31:
        raise HTTPException(status_code=400, detail="Dia do mês deve estar entre 1 e 31")
    create_rule(session, description, parse_brl(amount), day, kind, card_name, variable, categorias)
    session.commit()
    generate_all(session)
    return RedirectResponse("/recorrentes", status_code=303)


@router.get("/recorrentes/{rule_id}/editar")
def edit_recurring_page(rule_id: int, request: Request, session: Session = Depends(get_session)):
    rule = session.get(RecurringRule, rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="Recorrência não encontrada")
    card = session.get(Account, rule.account_id) if rule.account_id else None
    cards = session.exec(select(Account).where(Account.type == "cartao")).all()
    return templates.TemplateResponse(
        request,
        "editar_recorrente.html",
        {"rule": rule, "card_name": card.name if card else "", "cards": cards, "categorias": rule.tags_text},
    )


@router.post("/recorrentes/{rule_id}/editar")
def edit_recurring(
    rule_id: int,
    description: str = Form(...),
    amount: str = Form(...),
    day: int = Form(...),
    kind: str = Form("despesa"),
    card_name: str = Form(""),
    variable: bool = Form(False),
    categorias: str = Form(""),
    session: Session = Depends(get_session),
):
    rule = session.get(RecurringRule, rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="Recorrência não encontrada")
    if not 0 <= day <= 31:
        raise HTTPException(status_code=400, detail="Dia do mês deve estar entre 1 e 31")
    update_rule(session, rule, description, parse_brl(amount), day, kind, card_name, variable, categorias)
    session.commit()
    return RedirectResponse("/recorrentes", status_code=303)


@router.post("/recorrentes/{rule_id}/ativar")
def toggle_rule(rule_id: int, session: Session = Depends(get_session)):
    rule = session.get(RecurringRule, rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="Recorrência não encontrada")
    set_active(session, rule, not rule.active)
    session.commit()
    generate_all(session)
    return RedirectResponse("/recorrentes", status_code=303)


@router.post("/recorrentes/{rule_id}/excluir")
def delete_recurring(rule_id: int, session: Session = Depends(get_session)):
    rule = session.get(RecurringRule, rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="Recorrência não encontrada")
    delete_rule(session, rule)
    session.commit()
    return RedirectResponse("/recorrentes", status_code=303)

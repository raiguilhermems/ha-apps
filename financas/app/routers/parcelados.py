"""Parcelados: cartão, boleto, carnê e financiamento."""

from datetime import date

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from sqlmodel import Session, select

from app.db import get_session
from app.models import Account, InstallmentPlan, Transaction
from app.services.charts import parcelas_mensal
from app.services.parcelados import (
    FORMAS,
    create_plan,
    delete_plan,
    generate_installments,
    schedule_summaries,
    update_plan,
)
from app.services.cartoes import buscar_por_nome
from app.services.settings import get_setting
from app.services.util import current_month, parse_brl
from app.web import RedirectResponse, templates

router = APIRouter()


@router.get("/parcelados")
def parcelados_page(
    request: Request,
    erro: str | None = None,
    criadas: int | None = None,
    atualizadas: int | None = None,
    session: Session = Depends(get_session),
):
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
            "erro": erro,
            "criadas": criadas,
            "atualizadas": atualizadas,
            "dia_padrao": int(get_setting(session, "dia_padrao")),
            "graficos": parcelas_mensal(session),
        },
    )


@router.post("/parcelados")
def create_installment(
    description: str = Form(...),
    payment_method: str = Form(...),
    card_name: str = Form(""),
    amount: str = Form(...),
    total: int = Form(...),
    current_n: int = Form(...),
    current_ref: str = Form(...),
    due_day: int = Form(...),
    categorias: str = Form(""),
    session: Session = Depends(get_session),
):
    if payment_method not in ("cartao", "boleto", "carne", "financiamento", "outro"):
        return RedirectResponse("/parcelados?erro=forma", status_code=303)
    if payment_method == "cartao" and not card_name.strip():
        return RedirectResponse("/parcelados?erro=cartao", status_code=303)
    if payment_method == "cartao" and buscar_por_nome(session, card_name) is None:
        return RedirectResponse("/parcelados?erro=cartao", status_code=303)
    if total < 1 or not 1 <= current_n <= total:
        return RedirectResponse("/parcelados?erro=parcela", status_code=303)
    if not 0 <= due_day <= 31:
        return RedirectResponse("/parcelados?erro=dia", status_code=303)
    try:
        int(current_ref[:4]); int(current_ref[5:7])
    except ValueError:
        return RedirectResponse("/parcelados?erro=mes", status_code=303)

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
        categorias,
    )
    session.commit()
    generate_installments(session)
    return RedirectResponse("/parcelados", status_code=303)


@router.post("/parcelados/tx/{tx_id}/pagar")
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


@router.post("/parcelados/{plan_id}/excluir")
def delete_installment(plan_id: int, session: Session = Depends(get_session)):
    plan = session.get(InstallmentPlan, plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Parcelamento não encontrado")
    delete_plan(session, plan)
    session.commit()
    return RedirectResponse("/parcelados", status_code=303)


@router.get("/parcelados/{plan_id}/editar")
def editar_parcelado_page(plan_id: int, request: Request, session: Session = Depends(get_session)):
    plan = session.get(InstallmentPlan, plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Parcelamento não encontrado")
    cartao = ""
    if plan.account_id:
        conta = session.get(Account, plan.account_id)
        cartao = conta.name if conta else ""
    return templates.TemplateResponse(
        request,
        "editar_parcelado.html",
        {
            "plan": plan,
            "forma": FORMAS.get(plan.payment_method, plan.payment_method),
            "cartao": cartao,
            "categorias": plan.tags_text,
        },
    )


@router.post("/parcelados/{plan_id}/editar")
def editar_parcelado(
    plan_id: int,
    description: str = Form(...),
    amount: str = Form(...),
    due_day: int = Form(...),
    categorias: str = Form(""),
    session: Session = Depends(get_session),
):
    plan = session.get(InstallmentPlan, plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Parcelamento não encontrado")
    if not 0 <= due_day <= 31:
        raise HTTPException(status_code=400, detail="Dia do vencimento inválido")
    update_plan(session, plan, description, parse_brl(amount), due_day, categorias)
    session.commit()
    return RedirectResponse("/parcelados", status_code=303)

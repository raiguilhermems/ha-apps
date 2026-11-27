"""Desconto por antecipação: a parcela que já está na fatura aberta do cartão não entra."""

from datetime import date

from app.models import Account, InstallmentPlan
from app.services.parcelados import mes_da_fatura_aberta


def _plano(session, com_cartao=True):
    cartao = Account(name="Nubank", type="cartao", dia_pagamento=10, dia_fechamento=3)
    session.add(cartao)
    session.flush()
    plano = InstallmentPlan(
        description="TV",
        payment_method="cartao" if com_cartao else "boleto",
        account_id=cartao.id if com_cartao else None,
        installment_cents=10000,
        installments_total=5,
        first_due_month="2026-11",
    )
    session.add(plano)
    session.commit()
    return plano


ROWS = [
    {"status": "pendente", "mes": "2026-11"},
    {"status": "pendente", "mes": "2026-12"},
    {"status": "pendente", "mes": "2027-01"},
]


def test_parcela_da_fatura_aberta_nao_tem_desconto(session):
    plano = _plano(session)
    # Hoje é 27/11: a fatura de novembro já fechou (dia 3); a de dezembro ainda está aberta
    assert mes_da_fatura_aberta(session, plano, ROWS, date(2026, 11, 27)) == "2026-12"


def test_sem_cartao_nao_ha_fatura_aberta(session):
    plano = _plano(session, com_cartao=False)
    assert mes_da_fatura_aberta(session, plano, ROWS, date(2026, 11, 27)) is None

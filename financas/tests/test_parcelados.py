from sqlmodel import select
from datetime import date

from app.models import Account, Transaction
from app.services.parcelados import (
    create_plan,
    generate_installments,
    schedule_summaries,
    update_plan,
)
from app.services.util import add_months, current_month, due_in_month
from app.services.parcelados import desconto_antecipacao


def _parcelas(session, plan_id):
    return session.exec(
        select(Transaction).where(Transaction.installment_plan_id == plan_id)
    ).all()


def test_cronograma_conta_passadas_como_pagas(session):
    plan = create_plan(session, "Notebook", "boleto", "", 15000, 10, 3, current_month(), 10)
    session.commit()
    generate_installments(session)
    assert len(_parcelas(session, plan.id)) == 8  # parcelas 3 a 10
    resumo = schedule_summaries(session)["plans"][0]
    assert resumo["pagas"] == 2
    assert resumo["restantes"] == 8


def test_editar_nao_mexe_nas_pagas(session):
    plan = create_plan(session, "Notebook", "boleto", "", 15000, 10, 3, current_month(), 10)
    session.commit()
    generate_installments(session)
    parcelas = sorted(_parcelas(session, plan.id), key=lambda t: t.installment_n)
    paga = parcelas[0]
    paga.status = "pago"
    session.add(paga)
    session.commit()

    update_plan(session, plan, "Notebook novo", 20000, 15, "lazer")
    session.commit()

    assert paga.amount_cents == 15000
    assert paga.description.startswith("Notebook (")
    pendente = parcelas[1]
    assert pendente.amount_cents == 20000
    assert pendente.due_date.day == 15

def test_desconto_zero_sem_parcelas_futuras():
    assert desconto_antecipacao([(date(2026, 11, 1), 10000)], date(2026, 11, 23), 10.58) == 0

def test_desconto_uma_parcela_em_um_ano():
    # 1000 / 1,1058 ≈ 904,32 → desconto ≈ 95,68
    valor = 100000
    d = desconto_antecipacao([(date(2027, 11, 23), valor)], date(2026, 11, 23), 10.58)
    assert abs(d - 9568) <= 2


def test_desconto_so_conta_parcelas_de_meses_futuros(session):
    # Desconto só existe em compra no cartão. Cartão fecha dia 3: a parcela 2 (dezembro) cai
    # na fatura aberta e não é antecipável; a parcela 1 é do mês atual. Só a 3 (janeiro) conta.
    # Válido enquanto hoje for antes de 3 de dezembro de 2026.
    base = current_month()
    session.add(Account(name="Teste cartao", type="cartao", dia_pagamento=10, dia_fechamento=3))
    session.commit()
    create_plan(session, "Teste desconto", "cartao", "Teste cartao", 10000, 3, 1, base, 10)
    session.commit()
    resumo = schedule_summaries(session)["plans"][0]
    janeiro = [(due_in_month(add_months(base, 2), 10), 10000)]
    assert resumo["desconto"] == desconto_antecipacao(janeiro, date.today(), 10.58)
    assert resumo["desconto"] > 0


def test_desconto_zero_quando_so_ha_parcela_do_mes_atual(session):
    create_plan(session, "Teste desconto", "boleto", "", 10000, 1, 1, current_month(), 10)
    session.commit()
    assert schedule_summaries(session)["plans"][0]["desconto"] == 0

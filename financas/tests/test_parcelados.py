from sqlmodel import select
from datetime import date

from app.models import Transaction
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
    base = current_month()
    create_plan(session, "Teste desconto", "boleto", "", 10000, 3, 1, base, 10)
    session.commit()
    resumo = schedule_summaries(session)["plans"][0]
    # Parcela 1 é do mês atual (aberta, fora do desconto); parcelas 2 e 3 são futuras.
    futuras = [(due_in_month(add_months(base, k), 10), 10000) for k in (1, 2)]
    assert resumo["desconto"] == desconto_antecipacao(futuras, date.today(), 10.58)
    assert resumo["desconto"] > 0


def test_desconto_zero_quando_so_ha_parcela_do_mes_atual(session):
    create_plan(session, "Teste desconto", "boleto", "", 10000, 1, 1, current_month(), 10)
    session.commit()
    assert schedule_summaries(session)["plans"][0]["desconto"] == 0

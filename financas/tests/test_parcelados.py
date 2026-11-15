from sqlmodel import select

from app.models import Transaction
from app.services.parcelados import (
    create_plan,
    generate_installments,
    schedule_summaries,
    update_plan,
)
from app.services.util import current_month


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

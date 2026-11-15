from datetime import date

from sqlmodel import select

from app.models import InstallmentPlan, Tag, Transaction, TransactionTag
from app.services.parcelados import create_plan, delete_plan, generate_installments
from app.services.tags import mark_third_party
from app.services.util import current_month


def test_delete_plan_apaga_pendentes_e_mantem_pagas(session):
    plan = create_plan(session, "TV", "boleto", "", 10000, 4, 1, current_month(), 10)
    session.commit()
    generate_installments(session)
    txs = session.exec(
        select(Transaction).where(Transaction.installment_plan_id == plan.id)
    ).all()
    txs[0].status = "pago"
    session.add(txs[0])
    session.commit()

    delete_plan(session, plan)
    session.commit()

    assert session.get(InstallmentPlan, plan.id) is None
    sobras = session.exec(
        select(Transaction).where(Transaction.description.startswith("TV"))
    ).all()
    assert len(sobras) == 1
    assert sobras[0].installment_plan_id is None


def test_mark_third_party_cria_tag_e_vincula(session):
    tx = Transaction(
        description="Almoço",
        amount_cents=1000,
        due_date=date(2026, 11, 10),
        kind="despesa",
        status="pendente",
    )
    session.add(tx)
    session.flush()

    mark_third_party(session, tx)
    session.commit()

    tag = session.exec(select(Tag).where(Tag.name == "terceiro")).one()
    assert tag.excludes_from_total is True
    vinculos = session.exec(
        select(TransactionTag).where(TransactionTag.transaction_id == tx.id)
    ).all()
    assert len(vinculos) == 1

"""Quitar um parcelamento inteiro: as parcelas que faltam viram pagas (ou recebidas)."""

from sqlmodel import select

from app.models import Transaction
from app.services.parcelados import create_plan, generate_installments, quitar_parcelamento, schedule_summaries
from app.services.util import current_month


def _parcelas(session, plan):
    return session.exec(select(Transaction).where(Transaction.installment_plan_id == plan.id)).all()


def test_quitar_marca_todas_as_parcelas_que_faltam(session):
    plan = create_plan(session, "Geladeira", "boleto", "", 10000, 4, 1, current_month(), 10, "")
    session.commit()
    assert quitar_parcelamento(session, plan) == 4
    session.commit()
    parcelas = _parcelas(session, plan)
    assert len(parcelas) == 4
    assert all(t.status == "pago" for t in parcelas)
    resumo = schedule_summaries(session)["plans"][0]
    assert resumo["concluido"] is True
    assert resumo["saldo"] == 0


def test_quitar_nao_cria_parcelas_de_meses_anteriores(session):
    # parcelas 1 e 2 são de meses anteriores ao atual: já contam como pagas, não são criadas
    plan = create_plan(session, "TV", "boleto", "", 10000, 4, 3, current_month(), 10, "")
    session.commit()
    assert quitar_parcelamento(session, plan) == 2
    session.commit()
    assert sorted(t.installment_n for t in _parcelas(session, plan)) == [3, 4]
    assert schedule_summaries(session)["plans"][0]["concluido"] is True


def test_quitar_nao_duplica_parcelas_ja_existentes(session):
    plan = create_plan(session, "Sofá", "boleto", "", 5000, 3, 1, current_month(), 10, "")
    session.commit()
    generate_installments(session)
    session.commit()
    # uma parcela já paga antes de quitar continua sendo uma só
    primeira = _parcelas(session, plan)[0]
    primeira.status = "pago"
    session.add(primeira)
    session.commit()
    quitar_parcelamento(session, plan)
    session.commit()
    assert len(_parcelas(session, plan)) == 3

from datetime import date, timedelta

from sqlmodel import select

from app.models import RecurringRule, Transaction, TransactionTag
from app.services.recurring import create_rule, generate_all, set_active
from app.services.edit import update_rule, update_transaction


def _lancamentos(session):
    return session.exec(select(Transaction)).all()


def test_generate_all_gera_12_meses_sem_duplicar(session):
    create_rule(session, "Luz", 18000, 10, "despesa", "")
    session.commit()
    generate_all(session)
    assert len(_lancamentos(session)) == 12
    generate_all(session)
    assert len(_lancamentos(session)) == 12


def test_receita_nao_recebe_cartao(session):
    rule = create_rule(session, "Salário", 500000, 5, "receita", "Nubank")
    session.commit()
    assert rule.account_id is None


def test_categorias_sao_aplicadas_aos_lancamentos(session):
    create_rule(session, "Luz", 18000, 10, "despesa", "", False, "luz, casa")
    session.commit()
    generate_all(session)
    tx = _lancamentos(session)[0]
    vinculos = session.exec(
        select(TransactionTag).where(TransactionTag.transaction_id == tx.id)
    ).all()
    assert len(vinculos) == 2


def test_pausar_remove_pendentes(session):
    create_rule(session, "Internet", 10000, 15, "despesa", "")
    session.commit()
    generate_all(session)
    rule = session.exec(select(RecurringRule)).one()
    set_active(session, rule, False)
    session.commit()
    assert _lancamentos(session) == []


def test_ajuste_manual_nao_e_sobrescrito(session):
    rule = create_rule(session, "Luz", 18000, 10, "despesa", "", True)
    session.commit()
    generate_all(session)
    tx = _lancamentos(session)[0]
    update_transaction(session, tx, tx.description, 19999, tx.due_date, "despesa")
    session.commit()
    update_rule(session, rule, "Luz", 25000, 10, "despesa", "", True, "")
    session.commit()
    assert tx.amount_manual is True
    assert tx.amount_cents == 19999


def test_recorrente_de_cartao_pula_fim_de_semana(session):
    hoje = date.today()
    # Um sábado do mês atual (entre os dias 1 e 22, para a segunda cair no mesmo mês).
    sabado = next(d for d in range(1, 23) if date(hoje.year, hoje.month, d).weekday() == 5)
    create_rule(session, "Streaming", 4990, sabado, "despesa", "Nubank")
    session.commit()
    generate_all(session)
    tx = next(t for t in _lancamentos(session)
              if t.due_date.year == hoje.year and t.due_date.month == hoje.month)
    assert tx.due_date == date(hoje.year, hoje.month, sabado) + timedelta(days=2)


def test_recorrente_sem_cartao_mantem_o_dia(session):
    hoje = date.today()
    create_rule(session, "Luz", 18000, 10, "despesa", "")
    session.commit()
    generate_all(session)
    tx = next(t for t in _lancamentos(session)
              if t.due_date.year == hoje.year and t.due_date.month == hoje.month)
    assert tx.due_date == date(hoje.year, hoje.month, 10)

"""Edição de lançamentos e recorrências."""

from datetime import date

from sqlmodel import Session, select

from app.models import RecurringRule, Tag, Transaction, TransactionTag
from app.services.tags import mark_third_party
from app.services.recurring import _account_for, aplicar_categoria
from app.services.tags import parse_tags, set_tags
from app.services.util import current_month, due_in_month, month_bounds


def is_third_party(session: Session, tx: Transaction) -> bool:
    tag = session.exec(select(Tag).where(Tag.name == "terceiro")).first()
    if tag is None:
        return False
    return session.exec(
        select(TransactionTag).where(
            TransactionTag.transaction_id == tx.id, TransactionTag.tag_id == tag.id
        )
    ).first() is not None


def set_third_party(session: Session, tx: Transaction, flag: bool) -> None:
    if flag:
        if not is_third_party(session, tx):
            mark_third_party(session, tx)
        return
    tag = session.exec(select(Tag).where(Tag.name == "terceiro")).first()
    if tag is None:
        return
    for link in session.exec(
        select(TransactionTag).where(
            TransactionTag.transaction_id == tx.id, TransactionTag.tag_id == tag.id
        )
    ).all():
        session.delete(link)


def update_transaction(
    session: Session, tx: Transaction, description: str, amount_cents: int, due_date: date, kind: str
) -> None:
    # Se o valor de uma recorrência foi ajustado aqui, a regra não o sobrescreve mais
    if tx.recurring_rule_id and amount_cents != tx.amount_cents:
        tx.amount_manual = True
    tx.description = description.strip()
    tx.amount_cents = amount_cents
    tx.due_date = due_date
    tx.kind = kind
    session.add(tx)


def update_rule(
    session: Session,
    rule: RecurringRule,
    description: str,
    expected_cents: int,
    day: int,
    kind: str,
    card_name: str,
    variable: bool = False,
    categorias: str = "",
) -> None:
    rule.description = description.strip()
    rule.expected_cents = expected_cents
    rule.day_of_month = day
    rule.kind = kind
    rule.variable = variable
    rule.account_id = _account_for(session, kind, card_name)
    session.add(rule)
    # Renomeia a categoria da regra e grava as categorias; levanta ValueError se houver conflito
    aplicar_categoria(session, rule, categorias)

    start = month_bounds(current_month())[0]
    pendentes = session.exec(
        select(Transaction).where(
            Transaction.recurring_rule_id == rule.id,
            Transaction.status == "pendente",
            Transaction.due_date >= start,
        )
    ).all()
    for t in pendentes:
        t.description = rule.description
        t.kind = rule.kind
        t.account_id = rule.account_id
        t.due_date = due_in_month(t.due_date.strftime("%Y-%m"), rule.day_of_month)
        if rule.kind == "receita":
            t.third_party_cents = None
        # Valor ajustado à mão não é sobrescrito
        if not t.amount_manual:
            t.amount_cents = rule.expected_cents
        session.add(t)
        session.flush()
        set_tags(session, t, parse_tags(rule.tags_text))

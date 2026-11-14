"""Projeção: compromissos cadastrados + média dos gastos variáveis.

- Compromissos: despesas futuras de recorrentes e de parcelas.
- Variáveis: média dos últimos 3 meses, sem recorrentes nem parcelas.
"""

from sqlalchemy import or_
from sqlmodel import Session, select

from app.models import Transaction
from app.services.summary import card_account_ids, excluded_transaction_ids, net_amount
from app.services.util import add_months, month_bounds


def variable_average(session: Session, ref: str, months: int = 3) -> int:
    cards = card_account_ids(session)
    excluded = excluded_transaction_ids(session)
    total = 0
    for i in range(1, months + 1):
        start, end = month_bounds(add_months(ref, -i))
        txs = session.exec(
            select(Transaction).where(
                Transaction.kind == "despesa",
                Transaction.due_date >= start,
                Transaction.due_date < end,
                Transaction.is_recurring.is_(False),
                Transaction.installment_plan_id.is_(None),
            )
        ).all()
        for t in txs:
            if t.id in excluded or t.account_id in cards:
                continue
            total += net_amount(t)
    return total // months


def projection(session: Session, ref: str, months: int = 12) -> list[dict]:
    cards = card_account_ids(session)
    excluded = excluded_transaction_ids(session)
    variable = variable_average(session, ref)
    rows = []
    for i in range(1, months + 1):
        m = add_months(ref, i)
        start, end = month_bounds(m)
        txs = session.exec(
            select(Transaction).where(
                Transaction.kind == "despesa",
                Transaction.due_date >= start,
                Transaction.due_date < end,
                or_(
                    Transaction.is_recurring.is_(True),
                    Transaction.installment_plan_id.is_not(None),
                ),
            )
        ).all()
        committed = sum(
            net_amount(t)
            for t in txs
            if t.id not in excluded and t.account_id not in cards
        )
        rows.append({
            "mes": m,
            "compromissos": committed,
            "variavel": variable,
            "total": committed + variable,
        })
    return rows

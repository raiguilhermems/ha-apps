"""Geração de lançamentos previstos a partir de parcelamentos e recorrências."""

from sqlmodel import Session, select

from app.models import InstallmentPlan, RecurringRule, Transaction
from app.services.util import add_months, current_month, due_in_month, month_bounds


def create_installment_plan(
    session: Session,
    *,
    description: str,
    payment_method: str,
    account_id: int | None,
    installment_cents: int,
    installments_total: int,
    first_due_month: str,
    due_day: int,
) -> InstallmentPlan:
    """Cria o parcelamento e um lançamento pendente por parcela."""
    plan = InstallmentPlan(
        description=description,
        payment_method=payment_method,
        account_id=account_id,
        installment_cents=installment_cents,
        installments_total=installments_total,
        first_due_month=first_due_month,
    )
    session.add(plan)
    session.flush()  # garante plan.id

    for n in range(1, installments_total + 1):
        session.add(
            Transaction(
                due_date=due_in_month(add_months(first_due_month, n - 1), due_day),
                description=f"{description} ({n}/{installments_total})",
                amount_cents=installment_cents,
                kind="despesa",
                account_id=account_id,
                installment_plan_id=plan.id,
                installment_n=n,
                status="pendente",
            )
        )
    session.commit()
    return plan


def generate_recurring(session: Session, rule: RecurringRule, months_ahead: int = 12) -> int:
    """Cria lançamentos pendentes da regra nos próximos meses, sem duplicar.

    Retorna quantos foram criados. Se a regra mudar depois, os lançamentos
    pendentes já gerados precisam ser atualizados separadamente.
    """
    created = 0
    base = current_month()
    for i in range(months_ahead):
        m = add_months(base, i)
        start, end = month_bounds(m)
        exists = session.exec(
            select(Transaction.id).where(
                Transaction.recurring_rule_id == rule.id,
                Transaction.due_date >= start,
                Transaction.due_date < end,
            )
        ).first()
        if exists:
            continue
        session.add(
            Transaction(
                due_date=due_in_month(m, rule.day_of_month),
                description=rule.description,
                amount_cents=rule.expected_cents,
                kind="despesa",
                account_id=rule.account_id,
                is_recurring=True,
                recurring_rule_id=rule.id,
                status="pendente",
            )
        )
        created += 1
    session.commit()
    return created
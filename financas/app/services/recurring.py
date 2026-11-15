"""Recorrências: regras mensais que geram lançamentos automaticamente."""

from datetime import date

from sqlmodel import Session, select

from app.models import Account, RecurringRule, Transaction, TransactionTag
from app.services.tags import parse_tags, set_tags
from app.services.util import add_months, current_month, due_in_month, month_bounds


def get_or_create_card(session: Session, name: str) -> Account:
    name = name.strip()
    card = session.exec(
        select(Account).where(Account.type == "cartao", Account.name == name)
    ).first()
    if card is None:
        card = Account(name=name, type="cartao")
        session.add(card)
        session.flush()
    return card


def _account_for(session: Session, kind: str, card_name: str) -> int | None:
    """Cartão só faz sentido em despesa."""
    if kind == "despesa" and card_name.strip():
        return get_or_create_card(session, card_name).id
    return None


def create_rule(
    session: Session,
    description: str,
    expected_cents: int,
    day: int,
    kind: str,
    card_name: str,
    variable: bool = False,
    categorias: str = "",
) -> RecurringRule:
    rule = RecurringRule(
        description=description.strip(),
        expected_cents=expected_cents,
        day_of_month=day,
        kind=kind,
        account_id=_account_for(session, kind, card_name),
        active=True,
        variable=variable,
        tags_text=", ".join(parse_tags(categorias)),
    )
    session.add(rule)
    session.flush()
    return rule


def generate_all(session: Session, months_ahead: int = 12) -> int:
    """Gera lançamentos das regras ativas do mês atual até `months_ahead` meses à frente."""
    base = current_month()
    target_end = add_months(base, months_ahead - 1)
    created = 0

    rules = session.exec(select(RecurringRule).where(RecurringRule.active.is_(True))).all()
    for rule in rules:
        m = base
        if rule.generated_until:
            m = max(base, add_months(rule.generated_until, 1))
        while m <= target_end:
            start, end = month_bounds(m)
            exists = session.exec(
                select(Transaction.id).where(
                    Transaction.recurring_rule_id == rule.id,
                    Transaction.due_date >= start,
                    Transaction.due_date < end,
                )
            ).first()
            if not exists:
                tx = Transaction(
                    description=rule.description,
                    amount_cents=rule.expected_cents,
                    due_date=due_in_month(m, rule.day_of_month),
                    kind=rule.kind,
                    account_id=rule.account_id,
                    recurring_rule_id=rule.id,
                    status="pendente",
                    amount_manual=False,
                )
                session.add(tx)
                session.flush()
                set_tags(session, tx, parse_tags(rule.tags_text))
                created += 1
            m = add_months(m, 1)
        rule.generated_until = target_end
        session.add(rule)

    session.commit()
    return created


def _delete_with_tags(session: Session, tx: Transaction) -> None:
    for link in session.exec(
        select(TransactionTag).where(TransactionTag.transaction_id == tx.id)
    ).all():
        session.delete(link)
    session.delete(tx)


def remove_future_pending(session: Session, rule: RecurringRule) -> None:
    """Apaga os lançamentos pendentes, fora de fatura, a partir do mês atual."""
    start = month_bounds(current_month())[0]
    for t in session.exec(
        select(Transaction).where(
            Transaction.recurring_rule_id == rule.id,
            Transaction.status == "pendente",
            Transaction.due_date >= start,
        )
    ).all():
        _delete_with_tags(session, t)


def set_active(session: Session, rule: RecurringRule, active: bool) -> None:
    rule.active = active
    rule.generated_until = None  # ao reativar, gera de novo a partir do mês atual
    session.add(rule)
    if not active:
        remove_future_pending(session, rule)
    session.flush()


def delete_rule(session: Session, rule: RecurringRule) -> None:
    remove_future_pending(session, rule)
    session.flush()
    # Lançamentos já pagos ou em fatura viram lançamentos comuns
    for t in session.exec(
        select(Transaction).where(Transaction.recurring_rule_id == rule.id)
    ).all():
        t.recurring_rule_id = None
        session.add(t)
    session.flush()
    session.delete(rule)


def rule_month_status(session: Session, ref: str) -> list[dict]:
    """Situação de cada regra ativa no mês `ref`."""
    start, end = month_bounds(ref)
    today = date.today()
    rows = []
    rules = session.exec(
        select(RecurringRule)
        .where(RecurringRule.active.is_(True))
        .order_by(RecurringRule.description)
    ).all()
    for r in rules:
        t = session.exec(
            select(Transaction).where(
                Transaction.recurring_rule_id == r.id,
                Transaction.due_date >= start,
                Transaction.due_date < end,
            )
        ).first()
        if t is None:
            status, real, divergente = "não lançado", None, False
        else:
            real = t.amount_cents
            divergente = (not r.variable) and t.amount_cents != r.expected_cents
            if t.status == "pago":
                status = "recebido" if r.kind == "receita" else "pago"
            elif r.kind == "receita":
                status = "a receber"
            elif t.due_date < today:
                status = "atrasado"
            else:
                status = "pendente"
        rows.append({
            "descricao": r.description,
            "tipo": r.kind,
            "variavel": r.variable,
            "esperado": r.expected_cents,
            "real": real,
            "status": status,
            "divergente": divergente,
        })
    return rows

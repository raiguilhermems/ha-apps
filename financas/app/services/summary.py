"""Resumo mensal em regime de caixa e lista de atrasados.

Regras:
- Lançamentos entram pela data de vencimento.
- Despesa com terceiros entra pelo valor menos a parte de terceiros.
- Lançamentos com tag que não soma ao total ficam de fora.
- Lançamentos ligados a uma conta do tipo cartão ficam de fora do total.
"""

from datetime import date

from sqlmodel import Session, select

from app.models import Account, Tag, Transaction, TransactionTag
from app.services.util import month_bounds


def card_account_ids(session: Session) -> set[int]:
    return set(session.exec(select(Account.id).where(Account.type == "cartao")).all())


def excluded_transaction_ids(session: Session) -> set[int]:
    """Lançamentos com tag que não soma ao total."""
    tag_ids = session.exec(select(Tag.id).where(Tag.excludes_from_total.is_(True))).all()
    if not tag_ids:
        return set()
    return set(
        session.exec(
            select(TransactionTag.transaction_id).where(TransactionTag.tag_id.in_(tag_ids))
        ).all()
    )


def net_amount(t: Transaction) -> int:
    """Valor que conta para o mês: despesa menos a parte de terceiros."""
    if t.kind == "despesa":
        return t.amount_cents - (t.third_party_cents or 0)
    return t.amount_cents


def monthly_summary(session: Session, ref: str) -> dict:
    start, end = month_bounds(ref)
    today = date.today()
    cards = card_account_ids(session)
    excluded = excluded_transaction_ids(session)

    s = {
        "receitas": {"pago": 0, "pendente": 0},
        "despesas": {"pago": 0, "pendente": 0},
        "atrasado": 0,
        "atrasado_qtd": 0,
    }

    txs = session.exec(
        select(Transaction).where(Transaction.due_date >= start, Transaction.due_date < end)
    ).all()
    for t in txs:
        if t.account_id in cards or t.id in excluded or t.kind not in ("receita", "despesa"):
            continue
        bucket = "receitas" if t.kind == "receita" else "despesas"
        value = net_amount(t)
        s[bucket][t.status] += value
        if t.kind == "despesa" and t.status == "pendente" and t.due_date < today:
            s["atrasado"] += value
            s["atrasado_qtd"] += 1

    receitas_total = sum(s["receitas"].values())
    despesas_total = sum(s["despesas"].values())
    s["receitas_total"] = receitas_total
    s["despesas_total"] = despesas_total
    s["saldo"] = receitas_total - despesas_total
    s["pago"] = s["despesas"]["pago"]
    s["a_pagar"] = s["despesas"]["pendente"]
    return s


def overdue_items(session: Session) -> list[dict]:
    """Despesas vencidas e não pagas, de qualquer mês."""
    today = date.today()
    cards = card_account_ids(session)
    excluded = excluded_transaction_ids(session)
    items = []
    txs = session.exec(
        select(Transaction).where(
            Transaction.kind == "despesa",
            Transaction.status == "pendente",
            Transaction.due_date < today,
        )
    ).all()
    for t in txs:
        if t.account_id in cards or t.id in excluded:
            continue
        items.append({
            "descricao": t.description,
            "vencimento": t.due_date,
            "valor": net_amount(t),
        })
    return sorted(items, key=lambda i: i["vencimento"])

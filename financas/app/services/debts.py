"""Parcelamentos no cartão: criação a partir de um item da fatura e saldo devedor."""

from datetime import date

from sqlmodel import Session, select

from app.models import Account, Invoice, InstallmentPlan, Tag, Transaction, TransactionTag
from app.services.util import add_months, due_in_month


def mark_third_party(session: Session, tx: Transaction) -> None:
    tag = session.exec(select(Tag).where(Tag.name == "terceiro")).first()
    if tag is None:
        tag = Tag(name="terceiro", excludes_from_total=True)
        session.add(tag)
        session.flush()
    session.add(TransactionTag(transaction_id=tx.id, tag_id=tag.id))


def add_card_installment(
    session: Session,
    inv: Invoice,
    description: str,
    value_cents: int,
    purchase_date: date,
    n: int,
    total: int,
    third_party: bool,
) -> Transaction:
    """Cria o parcelamento, o item da parcela atual (na fatura) e as parcelas seguintes."""
    ref = inv.due_date.strftime("%Y-%m")
    plan = InstallmentPlan(
        description=description,
        payment_method="cartao",
        account_id=inv.account_id,
        installment_cents=value_cents,
        installments_total=total,
        first_due_month=add_months(ref, -(n - 1)),
    )
    session.add(plan)
    session.flush()

    current = Transaction(
        description=f"{description} ({n}/{total})",
        amount_cents=value_cents,
        due_date=inv.due_date,
        purchase_date=purchase_date,
        kind="despesa",
        account_id=inv.account_id,
        invoice_id=inv.id,
        installment_plan_id=plan.id,
        installment_n=n,
        status="pendente",
    )
    session.add(current)
    session.flush()
    if third_party:
        mark_third_party(session, current)

    for k in range(n + 1, total + 1):
        future = Transaction(
            description=f"{description} ({k}/{total})",
            amount_cents=value_cents,
            due_date=due_in_month(add_months(ref, k - n), inv.due_date.day),
            kind="despesa",
            account_id=inv.account_id,
            installment_plan_id=plan.id,
            installment_n=k,
            status="pendente",
        )
        session.add(future)
        session.flush()
        if third_party:
            mark_third_party(session, future)

    return current


def plan_summaries(session: Session) -> dict:
    rows = []
    for p in session.exec(select(InstallmentPlan)).all():
        txs = session.exec(
            select(Transaction).where(Transaction.installment_plan_id == p.id)
        ).all()
        pend = [t for t in txs if t.status == "pendente"]
        restantes = len(pend)
        card = session.get(Account, p.account_id) if p.account_id else None
        rows.append({
            "id": p.id,
            "descricao": p.description,
            "cartao": card.name if card else "—",
            "parcela": p.installment_cents,
            "total": p.installments_total,
            "pagas": p.installments_total - restantes,
            "restantes": restantes,
            "saldo": sum(t.amount_cents for t in pend),
            "ultima": max((t.due_date for t in txs), default=None),
            "concluido": restantes == 0,
        })
    rows.sort(key=lambda r: (r["concluido"], r["ultima"] or date.min))
    saldo_total = sum(r["saldo"] for r in rows if not r["concluido"])
    return {"rows": rows, "saldo_total": saldo_total}


def delete_plan(session: Session, plan: InstallmentPlan) -> None:
    """Apaga as parcelas pendentes. As já pagas ficam como histórico, sem vínculo."""
    for t in session.exec(
        select(Transaction).where(Transaction.installment_plan_id == plan.id)
    ).all():
        if t.status == "pendente":
            for link in session.exec(
                select(TransactionTag).where(TransactionTag.transaction_id == t.id)
            ).all():
                session.delete(link)
            session.delete(t)
        else:
            t.installment_plan_id = None
            t.installment_n = None
            session.add(t)
    session.flush()
    session.delete(plan)
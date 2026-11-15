"""Parcelados: cadastro, lançamento automático e cronograma."""

from datetime import date

from sqlmodel import Session, select

from app.models import Account, InstallmentPlan, Transaction
from app.services.recurring import get_or_create_card
from app.services.tags import parse_tags, set_tags
from app.services.util import add_months, current_month, due_in_month

FORMAS = {
    "cartao": "Cartão",
    "boleto": "Boleto",
    "carne": "Carnê",
    "financiamento": "Financiamento",
    "outro": "Outro",
}


def _months_between(a: str, b: str) -> int:
    ya, ma = map(int, a.split("-"))
    yb, mb = map(int, b.split("-"))
    return (yb - ya) * 12 + (mb - ma)


def create_plan(
    session: Session,
    description: str,
    payment_method: str,
    card_name: str,
    installment_cents: int,
    total: int,
    current_n: int,
    current_ref: str,
    due_day: int,
    categorias: str = "",
) -> InstallmentPlan:
    account_id = None
    if payment_method == "cartao":
        account_id = get_or_create_card(session, card_name).id
    plan = InstallmentPlan(
        description=description.strip(),
        payment_method=payment_method,
        account_id=account_id,
        installment_cents=installment_cents,
        installments_total=total,
        first_due_month=add_months(current_ref, -(current_n - 1)),
        due_day=due_day,
        tags_text=", ".join(parse_tags(categorias)),
    )
    session.add(plan)
    session.flush()
    return plan


def generate_installments(session: Session, months_ahead: int = 12) -> int:
    """Cria as parcelas das próximas semanas/meses que ainda não existem."""
    base = current_month()
    target_end = add_months(base, months_ahead - 1)
    created = 0

    for plan in session.exec(select(InstallmentPlan)).all():
        m = base
        if plan.generated_until:
            m = max(base, add_months(plan.generated_until, 1))
        while m <= target_end:
            n = _months_between(plan.first_due_month, m) + 1
            if 1 <= n <= plan.installments_total:
                exists = session.exec(
                    select(Transaction.id).where(
                        Transaction.installment_plan_id == plan.id,
                        Transaction.installment_n == n,
                    )
                ).first()
                if not exists:
                    tx = Transaction(
                        description=f"{plan.description} ({n}/{plan.installments_total})",
                        amount_cents=plan.installment_cents,
                        due_date=due_in_month(m, plan.due_day),
                        kind="despesa",
                        account_id=plan.account_id,
                        installment_plan_id=plan.id,
                        installment_n=n,
                        status="pendente",
                    )
                    session.add(tx)
                    session.flush()
                    set_tags(session, tx, parse_tags(plan.tags_text))
                    created += 1
            m = add_months(m, 1)
        plan.generated_until = target_end
        session.add(plan)

    session.commit()
    return created


def schedule_summaries(session: Session) -> dict:
    base = current_month()
    today = date.today()
    plans_out = []
    saldo_total = 0

    for p in session.exec(select(InstallmentPlan)).all():
        txs = session.exec(
            select(Transaction).where(Transaction.installment_plan_id == p.id)
        ).all()
        by_n = {t.installment_n: t for t in txs}

        rows = []
        pagas = 0
        saldo = 0
        for n in range(1, p.installments_total + 1):
            m = add_months(p.first_due_month, n - 1)
            vencimento = due_in_month(m, p.due_day)
            t = by_n.get(n)
            tx_id = None
            if t is not None:
                tx_id = t.id
                if t.status == "pago":
                    status = "pago"
                elif vencimento < today:
                    status = "atrasada"
                else:
                    status = "pendente"
            elif m < base:
                status = "passada"
            else:
                status = "pendente"

            if status in ("pago", "passada"):
                pagas += 1
            else:
                saldo += p.installment_cents

            rows.append({
                "n": n,
                "mes": m,
                "vencimento": vencimento,
                "valor": p.installment_cents,
                "status": status,
                "tx_id": tx_id,
            })

        restantes = p.installments_total - pagas
        concluido = restantes == 0
        if not concluido:
            saldo_total += saldo

        cartao_nome = ""
        if p.account_id:
            acc = session.get(Account, p.account_id)
            cartao_nome = acc.name if acc else ""

        plans_out.append({
            "id": p.id,
            "descricao": p.description,
            "forma_label": f"Cartão {cartao_nome}".strip() if p.payment_method == "cartao" else FORMAS.get(p.payment_method, p.payment_method),
            "parcela": p.installment_cents,
            "total": p.installments_total,
            "pagas": pagas,
            "restantes": restantes,
            "saldo": saldo,
            "concluido": concluido,
            "rows": rows,
        })

    plans_out.sort(key=lambda r: (r["concluido"], r["descricao"]))
    return {"plans": plans_out, "saldo_total": saldo_total}

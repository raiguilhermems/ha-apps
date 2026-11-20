"""Dados dos gráficos: Início (receitas × despesas), Parcelados e Categorias."""

from sqlmodel import Session

from app.services.parcelados import schedule_summaries
from app.services.summary import monthly_summary
from app.services.tags import transactions_with_tag
from app.services.util import add_months, current_month, mes_curto, month_bounds

def receitas_despesas_mensal(session: Session, ref: str, antes: int = 6, depois: int = 3) -> dict:
    """Barras do Início. Meses depois do atual são 'futuro' (ainda não fechados)."""
    atual = current_month()
    meses = [add_months(ref, i) for i in range(-antes, depois + 1)]
    receitas, despesas = [], []
    for m in meses:
        s = monthly_summary(session, m)
        receitas.append(s["receitas_total"] / 100)
        despesas.append(s["despesas_total"] / 100)
    return {
        "labels": [mes_curto(m) for m in meses],
        "receitas": receitas,
        "despesas": despesas,
        "futuro": [m > atual for m in meses],
        "atual": [m == atual for m in meses],
    }


def parcelas_mensal(session: Session, months: int = 12) -> dict:
    """Parcelas a pagar por mês. Parcelas a receber ficam de fora."""
    base = current_month()
    meses = [add_months(base, i) for i in range(months)]
    data = schedule_summaries(session)
    totais = {m: 0 for m in meses}
    for plan in data["plans"]:
        if plan["tipo"] != "pagar":
            continue
        for row in plan["rows"]:
            if row["status"] in ("pago", "passada"):
                continue
            if row["mes"] in totais:
                totais[row["mes"]] += row["valor"]
    return {
        "labels": [mes_curto(m) for m in meses],
        "totais": [totais[m] / 100 for m in meses],
    }


def categoria_mensal(session: Session, tag_id: int, ref: str, antes: int = 6, depois: int = 3) -> dict:
    """Barras da categoria. Mesma regra do Início: 'futuro' e 'atual' para destacar os meses."""
    atual = current_month()
    meses = [add_months(ref, i) for i in range(-antes, depois + 1)]
    receitas, despesas = [], []
    for m in meses:
        start, end = month_bounds(m)
        r = d = 0
        for t in transactions_with_tag(session, tag_id, start, end):
            if t.kind == "receita":
                r += t.amount_cents
            elif t.kind == "despesa":
                d += t.amount_cents
        receitas.append(r / 100)
        despesas.append(d / 100)
    return {
        "labels": [mes_curto(m) for m in meses],
        "receitas": receitas,
        "despesas": despesas,
        "futuro": [m > atual for m in meses],
        "atual": [m == atual for m in meses],
    }


def soma_categoria_periodo(session: Session, tag_id: int, ref: str, meses: int = 6) -> dict:
    """Soma de receitas e despesas da categoria nos `meses` meses terminando em `ref`."""
    mes_inicio = add_months(ref, -(meses - 1))
    receitas = despesas = 0
    for i in range(meses):
        start, end = month_bounds(add_months(mes_inicio, i))
        for t in transactions_with_tag(session, tag_id, start, end):
            if t.kind == "receita":
                receitas += t.amount_cents
            elif t.kind == "despesa":
                despesas += t.amount_cents
    return {"inicio": mes_inicio, "fim": ref, "receitas": receitas, "despesas": despesas}

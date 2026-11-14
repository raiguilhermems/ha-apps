"""Utilitários de data e dinheiro. Meses no formato AAAA-MM."""

from calendar import monthrange
from datetime import date


MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]


def current_month() -> str:
    t = date.today()
    return f"{t.year:04d}-{t.month:02d}"


def add_months(ref: str, n: int) -> str:
    y, m = map(int, ref.split("-"))
    idx = y * 12 + (m - 1) + n
    return f"{idx // 12:04d}-{idx % 12 + 1:02d}"


def month_bounds(ref: str) -> tuple[date, date]:
    """Primeiro dia do mês e primeiro dia do mês seguinte (intervalo [início, fim))."""
    y, m = map(int, ref.split("-"))
    ny, nm = map(int, add_months(ref, 1).split("-"))
    return date(y, m, 1), date(ny, nm, 1)


def due_in_month(ref: str, day: int) -> date:
    """Dia `day` do mês, limitado ao último dia do mês (ex.: 31 vira 30 em abril)."""
    y, m = map(int, ref.split("-"))
    return date(y, m, min(day, monthrange(y, m)[1]))


def parse_brl(text: str) -> int:
    """'1.234,56' -> 123456 (centavos)."""
    t = text.strip().replace("R$", "").replace(" ", "")
    t = t.replace(".", "").replace(",", ".")
    return round(float(t) * 100)


def fmt_brl(cents: int) -> str:
    s = f"{abs(cents) / 100:,.2f}"  # 1,234.56
    s = s.replace(",", "X").replace(".", ",").replace("X", ".")  # 1.234,56
    return ("-" if cents < 0 else "") + "R$ " + s


def mes_curto(ref: str) -> str:
    """'2026-02' -> 'fev/2026'."""
    y, m = ref.split("-")
    return f"{MESES[int(m) - 1]}/{y}"
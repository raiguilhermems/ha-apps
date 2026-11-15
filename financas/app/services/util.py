import calendar
from datetime import date, timedelta
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
    """Dia `day` do mês `ref` (AAAA-MM). day=0 é o 1º dia útil (seg a sex; feriados não entram)."""
    y, m = map(int, ref.split("-"))
    if day == 0:
        d = date(y, m, 1)
        while d.weekday() >= 5:
            d += timedelta(days=1)
        return d
    ultimo = calendar.monthrange(y, m)[1]
    return date(y, m, min(day, ultimo))


def parse_brl(text: str) -> int:
    """'1.234,56' -> 123456 (centavos)."""
    t = text.strip().replace("R$", "").replace(" ", "")
    t = t.replace(".", "").replace(",", ".")
    return round(float(t) * 100)


def fmt_brl(cents: int) -> str:
    s = f"{abs(cents) / 100:,.2f}"  # 1,234.56
    s = s.replace(",", "X").replace(".", ",").replace("X", ".")  # 1.234,56
    return ("-" if cents < 0 else "") + "R$\u00a0" + s


def mes_curto(ref: str) -> str:
    """'2026-02' -> 'fev/2026'."""
    y, m = ref.split("-")
    return f"{MESES[int(m) - 1]}/{y}"
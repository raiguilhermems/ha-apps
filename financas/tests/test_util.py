from datetime import date

from app.services.util import add_months, due_in_month, fmt_brl, parse_brl


def test_parse_brl():
    assert parse_brl("1.234,56") == 123456
    assert parse_brl("10,00") == 1000


def test_fmt_brl_usa_espaco_sem_quebra():
    assert fmt_brl(123456) == "R$\u00a01.234,56"
    assert fmt_brl(-500) == "-R$\u00a05,00"


def test_add_months_muda_de_ano():
    assert add_months("2026-12", 1) == "2027-01"
    assert add_months("2026-01", -1) == "2025-12"


def test_due_in_month_limita_ao_fim_do_mes():
    assert due_in_month("2026-02", 31) == date(2026, 2, 28)


def test_due_in_month_primeiro_dia_util():
    # 1º de novembro de 2026 é domingo: o 1º dia útil é 2
    assert due_in_month("2026-11", 0) == date(2026, 11, 2)
    # 1º de agosto de 2026 é sábado: o 1º dia útil é 3
    assert due_in_month("2026-08", 0) == date(2026, 8, 3)


def test_nome_proprio_capitaliza_cada_palavra():
    from app.services.util import nome_proprio
    assert nome_proprio("ana lima") == "Ana Lima"
    assert nome_proprio("joão da silva") == "João da Silva"
    assert nome_proprio("  maria   dos santos ") == "Maria dos Santos"

"""Adiciona caixinhas de investimento fictícias ao banco demo.

Rode depois do seed_demo.py, usando o mesmo banco:
    PYTHONPATH=. FINANCAS_DB=./demo.db uv run python scripts/seed_investimentos.py

Se já existir alguma caixinha no banco, não altera nada.
"""

import math
import os
import sys
from datetime import date

# Permite rodar de qualquer pasta, sem PYTHONPATH
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlmodel import select

from app.db import get_session, init_db
from app.models import Investimento
from app.services.investimentos import atualizar_valor, criar

FIM = date(2026, 11, 1)

# nome, tipo, mês inicial, valor inicial (R$), crescimento mensal, oscilação (0 a 1)
CAIXINHAS = [
    ("Tesouro Selic", "renda_fixa", date(2026, 3, 1), 4000.00, 0.011, 0.0),
    ("CDB Exemplo 110% CDI", "renda_fixa", date(2026, 6, 1), 2500.00, 0.009, 0.0),
    ("Fundo Imobiliário Exemplo", "renda_variavel", date(2026, 4, 1), 1800.00, 0.004, 0.035),
    ("Ações Exemplo", "renda_variavel", date(2026, 5, 1), 1200.00, 0.005, 0.06),
    ("Previdência Exemplo", "previdencia", date(2026, 1, 1), 3000.00, 0.008, 0.0),
]


def meses(inicio: date, fim: date):
    ano, mes = inicio.year, inicio.month
    while (ano, mes) <= (fim.year, fim.month):
        yield date(ano, mes, 1)
        mes += 1
        if mes == 13:
            ano, mes = ano + 1, 1


def main() -> None:
    init_db()
    gen = get_session()
    session = next(gen) if hasattr(gen, "__next__") else gen

    if session.exec(select(Investimento)).first() is not None:
        print("Já existem caixinhas no banco. Nada foi alterado.")
        return

    for nome, tipo, inicio, valor, crescimento, oscilacao in CAIXINHAS:
        inv = None
        for i, data in enumerate(meses(inicio, FIM)):
            fator = (1 + crescimento) ** i * (1 + oscilacao * math.sin(i * 1.3))
            cents = round(valor * 100 * fator)
            if inv is None:
                inv = criar(session, nome, tipo, cents, data)
            else:
                atualizar_valor(session, inv, cents, data)
        session.commit()
        print(f"{nome}: {i + 1} registros")


if __name__ == "__main__":
    main()

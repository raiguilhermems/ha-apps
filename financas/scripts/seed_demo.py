"""Gera um banco de demonstração com dados fictícios, para as capturas de tela do README.

Uso, a partir da pasta financas/:
    FINANCAS_DB=./demo.db uv run python scripts/seed_demo.py

Depois, para as caixinhas de investimento:
    PYTHONPATH=. FINANCAS_DB=./demo.db uv run python scripts/seed_investimentos.py

ATENÇÃO: apaga o banco indicado em FINANCAS_DB. Nunca aponte para o banco real.
"""

import os
import sys
from datetime import date

# Permite rodar de qualquer pasta, sem PYTHONPATH
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if "FINANCAS_DB" not in os.environ:
    sys.exit("Defina FINANCAS_DB, por exemplo: FINANCAS_DB=./demo.db")

from sqlmodel import Session, SQLModel, select  # noqa: E402

from app.db import engine, init_db  # noqa: E402
from app.models import RecurringRule, Transaction  # noqa: E402
from app.services.cartoes import buscar_por_nome, criar as criar_cartao  # noqa: E402
from app.services.parcelados import create_plan, generate_installments  # noqa: E402
from app.services.recurring import create_rule, generate_all, set_active  # noqa: E402
from app.services.tags import parse_tags, set_tags  # noqa: E402
from app.services.util import add_months, current_month  # noqa: E402

MERCADO = [78000, 91000, 84500, 97000, 88000, 81000]


def dia(mes: str, d: int) -> date:
    return date(int(mes[:4]), int(mes[5:7]), d)


def avulso(s, descricao, valor, due, kind="despesa", status="pendente", categorias="", terceiro=None):
    tx = Transaction(
        description=descricao,
        amount_cents=valor,
        due_date=due,
        kind=kind,
        status=status,
        paid_date=due if status == "pago" else None,
        third_party_cents=terceiro,
    )
    s.add(tx)
    s.flush()
    set_tags(s, tx, parse_tags(categorias))


def main():
    SQLModel.metadata.drop_all(engine)
    init_db()
    ref = current_month()

    with Session(engine) as s:
        # cartões: o dia de pagamento aparece na tela Cartões
        criar_cartao(s, "Nubank", 10)
        criar_cartao(s, "Itaú", 5)
        s.commit()

        # recorrentes (receitas e despesas, algumas com categoria própria)
        create_rule(s, "Salário", 550000, 5, "receita", "")
        create_rule(s, "Aluguel", 180000, 10, "despesa", "", False, "casa")
        create_rule(s, "Internet", 11900, 15, "despesa", "", False, "casa")
        create_rule(s, "Academia", 8990, 1, "despesa", "Nubank", False, "lazer")
        create_rule(s, "Energia", 21000, 12, "despesa", "", True, "casa")
        create_rule(s, "Plano de saúde", 34500, 20, "despesa", "", False, "saude")
        create_rule(s, "Streaming", 4990, 20, "despesa", "Itaú", False, "lazer")
        s.commit()

        # parcelados a pagar (cartão, boleto, carnê e financiamento)
        create_plan(s, "Notebook", "cartao", "Nubank", 49990, 10, 3, ref, 10, "lazer")
        create_plan(s, "Geladeira", "boleto", "", 89900, 6, 2, ref, 5, "casa")
        create_plan(s, "Financiamento do carro", "financiamento", "", 124000, 48, 10, ref, 25, "transporte")
        create_plan(s, "Sofá", "cartao", "Itaú", 32000, 5, 1, ref, 5, "casa")

        # parcelados a receber: compras feitas para outras pessoas, que vão devolver
        nubank = buscar_por_nome(s, "Nubank")
        create_plan(
            s, "Viagem da Ana", "a_receber", "", 45000, 6, 3, add_months(ref, -2), 10, "",
            tipo="receber", pessoa="Ana Lima", cartao_origem_id=nubank.id,
        )
        create_plan(
            s, "Jantar do João", "a_receber", "", 18000, 2, 1, ref, 10, "lazer",
            tipo="receber", pessoa="João", cartao_origem_id=nubank.id,
        )
        s.commit()

        generate_all(s)
        generate_installments(s)
        s.commit()

        # recorrente pausada, para aparecer o status "Pausada"
        streaming = s.exec(select(RecurringRule).where(RecurringRule.description == "Streaming")).one()
        set_active(s, streaming, False)
        s.commit()

        # avulsos: seis meses passados (pagos) e o mês atual (parte pago, parte pendente)
        for i in range(-5, 1):
            m = add_months(ref, i)
            k = i + 5
            pago = i < 0
            avulso(s, "Supermercado", MERCADO[k], dia(m, 8), status="pago" if pago else "pendente", categorias="mercado")
            avulso(s, "Combustível", 25000 + 1000 * k, dia(m, 18), status="pago" if pago else "pendente", categorias="transporte")
            avulso(s, "Restaurante", 9000 + 700 * k, dia(m, 22), status="pago" if pago else "pendente", categorias="lazer")
            avulso(s, "Farmácia", 6500, dia(m, 14), status="pago" if pago else "pendente", categorias="saude")
            if i in (-4, -1):
                avulso(s, "Freelance", 120000, dia(m, 15), kind="receita", status="pago" if pago else "pendente")
            if i == -2:
                avulso(s, "Jantar com amigos", 24000, dia(m, 9), status="pago", categorias="lazer, terceiro", terceiro=9000)
        s.commit()

        # no mês atual, algumas recorrentes já foram pagas
        for tx in s.exec(select(Transaction).where(Transaction.description.in_(["Internet", "Aluguel", "Salário"]))).all():
            if tx.due_date.strftime("%Y-%m") == ref and tx.due_date <= date.today():
                tx.status = "pago"
                tx.paid_date = tx.due_date
                s.add(tx)
        s.commit()

    print(f"Banco de demonstração criado em {os.environ['FINANCAS_DB']}")


if __name__ == "__main__":
    main()

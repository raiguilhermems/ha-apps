"""Conexão com o SQLite, criação das tabelas e migrações simples."""

import os
from pathlib import Path

from sqlalchemy import inspect, text
from sqlmodel import Session, SQLModel, create_engine

import app.models  # noqa: F401  (registra as tabelas no metadata)

DB_PATH = Path(os.getenv("FINANCAS_DB", "data/finance.db"))
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})

# Colunas adicionadas depois da criação inicial: (tabela, coluna, definição SQL)
NEW_COLUMNS = [
    ("recurring_rule", "kind", "VARCHAR NOT NULL DEFAULT 'despesa'"),
    ("recurring_rule", "generated_until", "VARCHAR"),
    ("recurring_rule", "variable", "BOOLEAN NOT NULL DEFAULT 0"),
    ("transacao", "third_party_cents", "INTEGER"),
    ("transacao", "amount_manual", "BOOLEAN NOT NULL DEFAULT 0"),
    ("installment_plan", "due_day", "INTEGER NOT NULL DEFAULT 10"),
    ("installment_plan", "generated_until", "VARCHAR"),
    ("recurring_rule", "tags_text", "VARCHAR NOT NULL DEFAULT ''"),
    ("installment_plan", "tags_text", "VARCHAR NOT NULL DEFAULT ''"),
    ("installment_plan", "tipo", "VARCHAR NOT NULL DEFAULT 'pagar'"),
    ("installment_plan", "pessoa", "VARCHAR NOT NULL DEFAULT ''"),
    ("installment_plan", "parcela_inicial", "INTEGER NOT NULL DEFAULT 1"),
    ("installment_plan", "cartao_origem_id", "INTEGER"),
    ("tag", "kind", "VARCHAR NOT NULL DEFAULT 'categoria'"),
    ("recurring_rule", "tag_id", "INTEGER"),
    ("account", "dia_fechamento", "INTEGER"),
    ("transacao", "reembolso", "BOOLEAN NOT NULL DEFAULT 0"),
    ("transacao", "fatura_id", "INTEGER"),
    ("fatura_cartao", "liquido_cents", "INTEGER NOT NULL DEFAULT 0"),
]


def _migrate() -> None:
    insp = inspect(engine)
    tables = set(insp.get_table_names())
    for table, column, ddl in NEW_COLUMNS:
        if table not in tables:
            continue
        cols = {c["name"] for c in insp.get_columns(table)}
        if column not in cols:
            with engine.begin() as conn:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))


def _backfill() -> None:
    """Ajusta dados antigos para o modelo de reembolso. Pode rodar mais de uma vez sem efeito extra.

    - a receber de terceiro (parcelado) passa a ser reembolso: não conta como receita;
    - a receita "pago por terceiro" de uma fatura antiga vira reembolso ligado à fatura;
    - o valor de terceiro digitado à mão na fatura vira um item da fatura, e o líquido é gravado.
    """
    with engine.begin() as conn:
        conn.execute(text(
            "UPDATE transacao SET reembolso = 1 WHERE kind = 'receita' AND reembolso = 0 "
            "AND installment_plan_id IN (SELECT id FROM installment_plan WHERE tipo = 'receber')"
        ))
        conn.execute(text(
            "UPDATE transacao SET reembolso = 1, "
            "fatura_id = (SELECT f.id FROM fatura_cartao f WHERE f.tx_receita_id = transacao.id) "
            "WHERE fatura_id IS NULL AND id IN (SELECT tx_receita_id FROM fatura_cartao WHERE tx_receita_id IS NOT NULL)"
        ))
        conn.execute(text(
            "INSERT INTO fatura_item (fatura_id, kind, descricao, valor_cents, destino, pessoa, categorias, nome_original) "
            "SELECT id, 'manual', 'Pago por terceiro (lançado antes)', terceiro_cents, 'terceiro', pessoa, '', '' "
            "FROM fatura_cartao WHERE terceiro_cents > 0 AND id NOT IN (SELECT fatura_id FROM fatura_item)"
        ))
        conn.execute(text(
            "UPDATE fatura_cartao SET liquido_cents = total_cents - terceiro_cents WHERE liquido_cents = 0"
        ))


def init_db() -> None:
    SQLModel.metadata.create_all(engine)
    _migrate()
    _backfill()


def get_session():
    with Session(engine) as session:
        yield session

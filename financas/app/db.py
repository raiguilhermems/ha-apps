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


def init_db() -> None:
    SQLModel.metadata.create_all(engine)
    _migrate()


def get_session():
    with Session(engine) as session:
        yield session

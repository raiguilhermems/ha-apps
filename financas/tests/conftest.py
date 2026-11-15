"""Banco temporário para os testes: nunca usa o banco real."""

import os
import tempfile
from pathlib import Path

import pytest

_banco_teste = Path(tempfile.mkdtemp()) / "teste.db"
os.environ["FINANCAS_DB"] = str(_banco_teste)

from sqlmodel import Session, SQLModel  # noqa: E402

from app.db import engine  # noqa: E402


@pytest.fixture()
def session():
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s

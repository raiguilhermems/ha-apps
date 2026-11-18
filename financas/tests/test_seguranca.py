"""Testes das correções de segurança da 0.0.19."""

import sqlite3
from pathlib import Path

from app.main import _prefixo_ingress
from app.routers.configuracoes import _banco_valido

TEMPLATES = Path(__file__).resolve().parent.parent / "app" / "templates"


def _criar_banco(caminho: Path, tabelas: list[str]) -> None:
    con = sqlite3.connect(caminho)
    for tabela in tabelas:
        con.execute(f"CREATE TABLE {tabela} (id INTEGER PRIMARY KEY)")
    con.commit()
    con.close()


def test_prefixo_ingress_aceita_caminho_do_home_assistant():
    assert _prefixo_ingress("/api/hassio_ingress/abc123_XYZ/") == "/api/hassio_ingress/abc123_XYZ"
    assert _prefixo_ingress("") == ""


def test_prefixo_ingress_rejeita_outros_valores():
    assert _prefixo_ingress("//site-externo.com") == ""
    assert _prefixo_ingress("https://exemplo.com/api/hassio_ingress/x") == ""
    assert _prefixo_ingress("/api/hassio_ingress/../admin") == ""
    assert _prefixo_ingress("/outro/caminho") == ""


def test_banco_valido_aceita_banco_com_tabelas_do_app(tmp_path):
    caminho = tmp_path / "ok.db"
    _criar_banco(caminho, ["account", "transacao"])
    assert _banco_valido(caminho)


def test_banco_valido_rejeita_arquivo_que_nao_e_sqlite(tmp_path):
    caminho = tmp_path / "texto.db"
    caminho.write_bytes(b"isto nao e um banco" * 50)
    assert not _banco_valido(caminho)


def test_banco_valido_rejeita_sqlite_de_outro_programa(tmp_path):
    caminho = tmp_path / "outro.db"
    _criar_banco(caminho, ["tabela_qualquer"])
    assert not _banco_valido(caminho)


def test_nome_do_cartao_nao_vai_para_o_javascript_da_confirmacao():
    html = (TEMPLATES / "cartoes.html").read_text(encoding="utf-8")
    assert "confirm('Excluir o cartão {{ c.name }}" not in html
    assert 'data-nome="{{ c.name }}"' in html

"""A versão mostrada no app tem de ser a mesma do config.yaml do add-on."""

import re
from pathlib import Path

from app.web import APP_VERSION

CONFIG = Path(__file__).resolve().parent.parent / "config.yaml"


def test_versao_do_app_igual_ao_config_yaml():
    texto = CONFIG.read_text(encoding="utf-8")
    versao = re.search(r'^version:\s*"?([^"\n]+)"?\s*$', texto, re.MULTILINE).group(1)
    assert APP_VERSION == versao


def test_nome_do_app_no_config_yaml():
    texto = CONFIG.read_text(encoding="utf-8")
    assert "name: FinHome" in texto
    assert "slug: finhome" in texto

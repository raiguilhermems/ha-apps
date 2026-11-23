"""Configuração compartilhada pelas telas: templates, prefixo do ingress e redirecionamento."""

from contextvars import ContextVar
from pathlib import Path

from fastapi.responses import RedirectResponse as _RedirectResponse
from fastapi.templating import Jinja2Templates

from app.services.util import add_months, current_month, fmt_brl, mes_curto, nome_proprio

APP_VERSION = "2026.11.1"

_prefixo: ContextVar[str] = ContextVar("prefixo", default="")


class RedirectResponse(_RedirectResponse):
    """Redireciona respeitando o caminho do ingress do Home Assistant."""

    def __init__(self, url, status_code=307, headers=None, background=None):
        if url.startswith("/"):
            url = _prefixo.get() + url
        super().__init__(url, status_code=status_code, headers=headers, background=background)


templates = Jinja2Templates(directory=Path(__file__).parent / "templates")
templates.env.filters["brl"] = fmt_brl
templates.env.filters["mes"] = mes_curto
templates.env.filters["pessoa"] = nome_proprio
templates.env.globals["base"] = lambda: _prefixo.get()
templates.env.globals["mes_atual"] = current_month
templates.env.globals["add_months"] = add_months
templates.env.globals["versao"] = APP_VERSION

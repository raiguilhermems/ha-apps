"""Configuração compartilhada pelas telas: templates, prefixo do ingress e redirecionamento."""

from contextvars import ContextVar
from pathlib import Path

from fastapi.responses import RedirectResponse as _RedirectResponse
from fastapi.templating import Jinja2Templates

from app.services.util import fmt_brl, mes_curto

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
templates.env.globals["base"] = lambda: _prefixo.get()

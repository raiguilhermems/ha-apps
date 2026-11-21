"""Aplicação FastAPI: monta as telas (routers) e o prefixo do ingress do Home Assistant."""

import re
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request

from app.db import init_db
from app.routers import (
    cartoes,
    categorias,
    configuracoes,
    importacao,
    investimentos,
    lancamentos,
    parcelados,
    recorrentes,
)
from app.web import APP_VERSION, _prefixo


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="FinHome", version=APP_VERSION, lifespan=lifespan)


PADRAO_INGRESS = re.compile(r"/api/hassio_ingress/[A-Za-z0-9_-]+")


def _prefixo_ingress(valor: str) -> str:
    """Aceita só o caminho do ingress do Home Assistant. Qualquer outro valor vira vazio."""
    valor = valor.rstrip("/")
    return valor if PADRAO_INGRESS.fullmatch(valor) else ""


@app.middleware("http")
async def ingress_prefixo(request: Request, call_next):
    token = _prefixo.set(_prefixo_ingress(request.headers.get("x-ingress-path", "")))
    try:
        return await call_next(request)
    finally:
        _prefixo.reset(token)


app.include_router(lancamentos.router)
app.include_router(parcelados.router)
app.include_router(importacao.router)
app.include_router(categorias.router)
app.include_router(recorrentes.router)
app.include_router(cartoes.router)
app.include_router(investimentos.router)
app.include_router(configuracoes.router)

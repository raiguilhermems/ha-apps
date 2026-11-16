"""Aplicação FastAPI: monta as telas (routers) e o prefixo do ingress do Home Assistant."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request

from app.db import init_db
from app.routers import categorias, configuracoes, importacao, lancamentos, parcelados, recorrentes
from app.web import _prefixo


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="Finanças", lifespan=lifespan)


@app.middleware("http")
async def ingress_prefixo(request: Request, call_next):
    token = _prefixo.set(request.headers.get("x-ingress-path", "").rstrip("/"))
    try:
        return await call_next(request)
    finally:
        _prefixo.reset(token)


app.include_router(lancamentos.router)
app.include_router(parcelados.router)
app.include_router(importacao.router)
app.include_router(categorias.router)
app.include_router(recorrentes.router)
app.include_router(configuracoes.router)

"""Configurações: vencimento padrão, backup, importação e apagar dados."""

import os
import shutil
import sqlite3
from datetime import date
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from sqlmodel import Session, SQLModel

from app.db import DB_PATH, engine, get_session, init_db
from app.services.settings import get_int_setting, get_setting, set_setting
from app.web import RedirectResponse, templates

router = APIRouter()

CABECALHO_SQLITE = b"SQLite format 3\x00"
TAMANHO_MAXIMO_BACKUP = 50 * 1024 * 1024  # 50 MB
TABELAS_OBRIGATORIAS = {"account", "transacao"}


def _banco_valido(caminho: Path) -> bool:
    """Confere se o arquivo é um banco SQLite deste app. Abre só para leitura."""
    with caminho.open("rb") as f:
        if f.read(len(CABECALHO_SQLITE)) != CABECALHO_SQLITE:
            return False
    try:
        con = sqlite3.connect(f"{caminho.resolve().as_uri()}?mode=ro", uri=True)
    except sqlite3.Error:
        return False
    try:
        tabelas = {linha[0] for linha in con.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        if not TABELAS_OBRIGATORIAS <= tabelas:
            return False
        return con.execute("PRAGMA quick_check").fetchone()[0] == "ok"
    except sqlite3.Error:
        return False
    finally:
        con.close()


@router.get("/configuracoes")
def configuracoes_page(request: Request, erro: str | None = None, session: Session = Depends(get_session)):
    tamanho = DB_PATH.stat().st_size / 1024 / 1024 if DB_PATH.exists() else 0
    return templates.TemplateResponse(
        request,
        "configuracoes.html",
        {
            "tamanho_mb": f"{tamanho:.2f}".replace(".", ","),
            "erro": erro,
            "dia_padrao": int(get_setting(session, "dia_padrao")),
            "grafico_antes": get_int_setting(session, "grafico_antes", 1, 24),
            "grafico_depois": get_int_setting(session, "grafico_depois", 0, 12),
        },
    )


@router.get("/configuracoes/backup")
def baixar_backup():
    nome = f"financas-backup-{date.today():%Y-%m-%d}.db"
    return FileResponse(DB_PATH, filename=nome, media_type="application/octet-stream")


@router.post("/configuracoes/importar")
async def importar_backup(arquivo: UploadFile = File(...)):
    temporario = DB_PATH.with_name("finance-importacao.tmp")
    try:
        # Grava por partes em arquivo temporário, sem carregar tudo na memória
        with temporario.open("wb") as destino:
            tamanho = 0
            while bloco := await arquivo.read(1024 * 1024):
                tamanho += len(bloco)
                if tamanho > TAMANHO_MAXIMO_BACKUP:
                    return RedirectResponse("/configuracoes?erro=tamanho", status_code=303)
                destino.write(bloco)
        if not _banco_valido(temporario):
            return RedirectResponse("/configuracoes?erro=arquivo", status_code=303)
        engine.dispose()
        if DB_PATH.exists():
            shutil.copyfile(DB_PATH, DB_PATH.with_name("finance-antes-da-importacao.db"))
        os.replace(temporario, DB_PATH)
        init_db()
    finally:
        temporario.unlink(missing_ok=True)
    return RedirectResponse("/configuracoes", status_code=303)


@router.post("/configuracoes/apagar")
def apagar_dados(confirmacao: str = Form(...), session: Session = Depends(get_session)):
    if confirmacao.strip() != "APAGAR":
        return RedirectResponse("/configuracoes?erro=apagar", status_code=303)
    for table in reversed(SQLModel.metadata.sorted_tables):
        if table.name == "setting":
            continue
        session.execute(table.delete())
    session.commit()
    return RedirectResponse("/configuracoes", status_code=303)


@router.post("/configuracoes/dia_padrao")
def salvar_dia_padrao(dia: int = Form(...), session: Session = Depends(get_session)):
    if not 0 <= dia <= 31:
        raise HTTPException(status_code=400, detail="Use 0 (1º dia útil) ou de 1 a 31")
    set_setting(session, "dia_padrao", str(dia))
    return RedirectResponse("/configuracoes", status_code=303)


@router.post("/configuracoes/grafico")
def salvar_grafico(antes: int = Form(...), depois: int = Form(...), session: Session = Depends(get_session)):
    if not 1 <= antes <= 24 or not 0 <= depois <= 12:
        return RedirectResponse("/configuracoes?erro=grafico", status_code=303)
    set_setting(session, "grafico_antes", str(antes))
    set_setting(session, "grafico_depois", str(depois))
    return RedirectResponse("/configuracoes", status_code=303)

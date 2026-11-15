"""Configurações: vencimento padrão, projeção, backup, importação e apagar dados."""

import shutil
from datetime import date

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from sqlmodel import Session, SQLModel

from app.db import DB_PATH, engine, get_session, init_db
from app.services.settings import get_setting, set_setting
from app.web import RedirectResponse, templates

router = APIRouter()


@router.get("/configuracoes")
def configuracoes_page(request: Request, erro: str | None = None, session: Session = Depends(get_session)):
    tamanho = DB_PATH.stat().st_size / 1024 / 1024 if DB_PATH.exists() else 0
    return templates.TemplateResponse(
        request,
        "configuracoes.html",
        {
            "horizonte": int(get_setting(session, "projecao_meses")),
            "tamanho_mb": f"{tamanho:.2f}".replace(".", ","),
            "erro": erro,
            "dia_padrao": int(get_setting(session, "dia_padrao")),
        },
    )


@router.get("/configuracoes/backup")
def baixar_backup():
    nome = f"financas-backup-{date.today():%Y-%m-%d}.db"
    return FileResponse(DB_PATH, filename=nome, media_type="application/octet-stream")


@router.post("/configuracoes/importar")
async def importar_backup(arquivo: UploadFile = File(...)):
    conteudo = await arquivo.read()
    if not conteudo.startswith(b"SQLite format 3\x00"):
        return RedirectResponse("/configuracoes?erro=arquivo", status_code=303)
    engine.dispose()
    if DB_PATH.exists():
        shutil.copyfile(DB_PATH, DB_PATH.with_name("finance-antes-da-importacao.db"))
    DB_PATH.write_bytes(conteudo)
    init_db()
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


@router.post("/configuracoes/projecao")
def salvar_projecao(meses: int = Form(...), session: Session = Depends(get_session)):
    if not 1 <= meses <= 12:
        raise HTTPException(status_code=400, detail="Use de 1 a 12 meses")
    set_setting(session, "projecao_meses", str(meses))
    return RedirectResponse("/configuracoes", status_code=303)


@router.post("/configuracoes/dia_padrao")
def salvar_dia_padrao(dia: int = Form(...), session: Session = Depends(get_session)):
    if not 0 <= dia <= 31:
        raise HTTPException(status_code=400, detail="Use 0 (1º dia útil) ou de 1 a 31")
    set_setting(session, "dia_padrao", str(dia))
    return RedirectResponse("/configuracoes", status_code=303)

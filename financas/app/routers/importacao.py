"""Importação da fatura do Nubank: envio do CSV, prévia e gravação."""

import csv
from datetime import date

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from sqlmodel import Session, select

from app.db import get_session
from app.models import Account
from app.services.fatura_nubank import LinhaFatura, ler_fatura, limpa_nome
from app.services.importacao import gravar, montar_previa
from app.web import RedirectResponse, templates

router = APIRouter()


@router.get("/parcelados/importar")
def importar_page(request: Request, erro: str | None = None, session: Session = Depends(get_session)):
    cartoes = session.exec(select(Account).where(Account.type == "cartao").order_by(Account.name)).all()
    return templates.TemplateResponse(
        request,
        "importar_fatura.html",
        {"cartoes": cartoes, "erro": erro, "hoje": date.today()},
    )


@router.post("/parcelados/importar/previa")
async def importar_previa(
    request: Request,
    arquivo: UploadFile = File(...),
    cartao: str = Form(...),
    vencimento: date = Form(...),
    session: Session = Depends(get_session),
):
    cartao = cartao.strip()
    if not cartao:
        return RedirectResponse("/parcelados/importar?erro=cartao", status_code=303)
    try:
        linhas = ler_fatura(await arquivo.read())
    except (ValueError, csv.Error):
        return RedirectResponse("/parcelados/importar?erro=arquivo", status_code=303)
    if not linhas:
        return RedirectResponse("/parcelados/importar?erro=vazio", status_code=303)

    previa = montar_previa(session, linhas, cartao)
    return templates.TemplateResponse(
        request,
        "previa_fatura.html",
        {"previa": previa, "cartao": cartao, "vencimento": vencimento},
    )


@router.post("/parcelados/importar/confirmar")
async def importar_confirmar(request: Request, session: Session = Depends(get_session)):
    form = await request.form()
    cartao = str(form.get("cartao", "")).strip()
    if not cartao:
        return RedirectResponse("/parcelados/importar?erro=cartao", status_code=303)
    vencimento = date.fromisoformat(str(form["vencimento"]))

    itens = []
    for i in form.getlist("indices"):
        i = str(i)
        original = str(form[f"original_{i}"])
        linha = LinhaFatura(
            data=date.fromisoformat(str(form[f"data_{i}"])),
            nome_original=original,
            nome=limpa_nome(original),
            parcela=int(str(form[f"n_{i}"])),
            total=int(str(form[f"total_{i}"])),
            valor_cents=int(str(form[f"valor_{i}"])),
        )
        itens.append(
            {
                "linha": linha,
                "status": str(form[f"status_{i}"]),
                "incluir": f"incluir_{i}" in form,
                "atualizar": f"atualizar_{i}" in form,
                "plano_id": str(form.get(f"plano_{i}", "")) or None,
                "nome": str(form.get(f"nome_{i}", "")).strip() or linha.nome,
                "categorias": str(form.get(f"categorias_{i}", "")),
            }
        )

    resultado = gravar(session, cartao, vencimento, itens)
    return RedirectResponse(
        f"/parcelados?criadas={resultado['criadas']}&atualizadas={resultado['atualizadas']}",
        status_code=303,
    )

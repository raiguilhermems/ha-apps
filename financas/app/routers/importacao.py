"""Importação da fatura do Nubank: envio do CSV, prévia e gravação."""

import csv
from datetime import date
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from sqlmodel import Session, select

from app.db import get_session
from app.models import Account, Tag
from app.services.cartoes import buscar_por_nome, criar, listar, validar_novo, vencimento_fatura
from app.services.fatura_nubank import LinhaFatura, ler_fatura, limpa_nome
from app.services.importacao import gravar, montar_previa, sem_pessoa
from app.services.tags import validar_categorias_livres
from app.web import RedirectResponse, templates

router = APIRouter()

MESES = [
    (1, "janeiro"), (2, "fevereiro"), (3, "março"), (4, "abril"),
    (5, "maio"), (6, "junho"), (7, "julho"), (8, "agosto"),
    (9, "setembro"), (10, "outubro"), (11, "novembro"), (12, "dezembro"),
]


def _volta(mensagem: str) -> RedirectResponse:
    return RedirectResponse(f"/parcelados/importar?erro={quote(mensagem)}", status_code=303)


def _escolher_cartao(session: Session, cartao_id: str, novo_nome: str, novo_dia: str) -> tuple[str, int]:
    """Devolve (nome, dia de pagamento) do cartão escolhido. Não grava nada no banco."""
    if cartao_id.strip():
        try:
            cartao = session.get(Account, int(cartao_id))
        except ValueError:
            cartao = None
        if cartao is None or cartao.type != "cartao":
            raise ValueError("Cartão não encontrado")
        if cartao.dia_pagamento is None:
            raise ValueError("Este cartão não tem dia de pagamento. Edite-o na aba Cartões.")
        return cartao.name, cartao.dia_pagamento
    if novo_nome.strip():
        dia = novo_dia.strip()
        nome = validar_novo(session, novo_nome, int(dia) if dia else None)
        return nome, int(dia)
    raise ValueError("Escolha um cartão da lista ou preencha os dados de um cartão novo")


@router.get("/parcelados/importar")
def importar_page(request: Request, erro: str | None = None, session: Session = Depends(get_session)):
    hoje = date.today()
    return templates.TemplateResponse(
        request,
        "importar_fatura.html",
        {
            "cartoes": listar(session),
            "erro": erro,
            "meses": MESES,
            "anos": list(range(hoje.year - 1, hoje.year + 3)),
            "mes_atual_num": hoje.month,
            "ano_atual": hoje.year,
        },
    )


@router.post("/parcelados/importar/previa")
async def importar_previa(
    request: Request,
    arquivo: UploadFile = File(...),
    cartao_id: str = Form(""),
    novo_nome: str = Form(""),
    novo_dia: str = Form(""),
    mes_num: str = Form(...),
    ano: str = Form(...),
    session: Session = Depends(get_session),
):
    try:
        linhas: list[LinhaFatura] = ler_fatura(await arquivo.read())
    except (ValueError, csv.Error):
        return _volta("Não consegui ler este arquivo. Confira se é o CSV da fatura do Nubank.")
    if not linhas:
        return _volta("Nenhuma compra parcelada encontrada neste arquivo.")

    try:
        mes = f"{int(ano):04d}-{int(mes_num):02d}"
        nome_cartao, dia_pagamento = _escolher_cartao(session, cartao_id, novo_nome, novo_dia)
        vencimento = vencimento_fatura(mes, dia_pagamento)
    except ValueError as e:
        session.rollback()
        return _volta(str(e))

    previa = montar_previa(session, linhas, nome_cartao)
    pessoas = [t.name for t in session.exec(select(Tag).where(Tag.kind == "pessoa").order_by(Tag.name)).all()]
    # Cartão novo só é gravado na confirmação; o dia vai junto para criá-lo lá.
    dia_novo = dia_pagamento if not cartao_id.strip() else None
    return templates.TemplateResponse(
        request,
        "previa_fatura.html",
        {"previa": previa, "cartao": nome_cartao, "vencimento": vencimento, "dia_novo": dia_novo, "pessoas": pessoas},
    )


@router.post("/parcelados/importar/confirmar")
async def importar_confirmar(request: Request, session: Session = Depends(get_session)):
    form = await request.form()
    cartao = str(form.get("cartao", "")).strip()
    if not cartao:
        return _volta("Cartão não informado")
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
        terceiro = f"terceiro_{i}" in form
        itens.append(
            {
                "linha": linha,
                "status": str(form[f"status_{i}"]),
                # Marcar "de outra pessoa" já cadastra a compra
                "incluir": f"incluir_{i}" in form or terceiro,
                "atualizar": f"atualizar_{i}" in form,
                "plano_id": str(form.get(f"plano_{i}", "")) or None,
                "nome": str(form.get(f"nome_{i}", "")).strip() or linha.nome,
                "categorias": str(form.get(f"categorias_{i}", "")),
                "terceiro": terceiro,
                "pessoa": str(form.get(f"pessoa_{i}", "")).strip(),
            }
        )

    # Valida antes de criar cartão novo ou gravar qualquer coisa
    faltando = sem_pessoa(itens)
    if faltando:
        return _volta("Informe quem vai pagar para: " + ", ".join(faltando) + ". Nada foi gravado.")

    for item in itens:
        try:
            validar_categorias_livres(session, item["categorias"])
        except ValueError as e:
            return _volta(f"{e} Nada foi gravado.")

    dia_novo = str(form.get("dia_novo", "")).strip()
    if dia_novo and buscar_por_nome(session, cartao) is None:
        try:
            criar(session, cartao, int(dia_novo))
        except ValueError as e:
            session.rollback()
            return _volta(str(e))
        session.commit()

    try:
        resultado = gravar(session, cartao, vencimento, itens)
    except ValueError as e:
        session.rollback()
        return _volta(str(e))
    return RedirectResponse(
        f"/parcelados?criadas={resultado['criadas']}&atualizadas={resultado['atualizadas']}",
        status_code=303,
    )

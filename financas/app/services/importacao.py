"""Prévia e gravação da importação da fatura do Nubank."""

from datetime import date

from sqlmodel import Session, select

from app.models import Account, ImportacaoIgnorada, InstallmentPlan
from app.services.fatura_nubank import LinhaFatura, chave_nome, limpa_nome
from app.services.parcelados import create_plan, generate_installments, update_plan

TOLERANCIA_CENTAVOS = 20


def _cartao(session: Session, nome: str) -> Account | None:
    return session.exec(
        select(Account).where(Account.name == nome, Account.type == "cartao")
    ).first()


def _plano_existente(session: Session, linha: LinhaFatura, card_id: int) -> InstallmentPlan | None:
    planos = session.exec(
        select(InstallmentPlan).where(
            InstallmentPlan.account_id == card_id,
            InstallmentPlan.installments_total == linha.total,
        )
    ).all()
    for p in planos:
        if p.origem_csv:
            mesmo_nome = chave_nome(limpa_nome(p.origem_csv)) == chave_nome(linha.nome)
        else:
            mesmo_nome = chave_nome(p.description) == chave_nome(linha.nome)
        if mesmo_nome and abs(p.installment_cents - linha.valor_cents) <= TOLERANCIA_CENTAVOS:
            return p
    return None


def _ignorada(session: Session, linha: LinhaFatura, card_id: int) -> bool:
    registros = session.exec(
        select(ImportacaoIgnorada).where(
            ImportacaoIgnorada.total == linha.total,
            ImportacaoIgnorada.account_id == card_id,
        )
    ).all()
    return any(
        chave_nome(limpa_nome(r.nome_original)) == chave_nome(linha.nome)
        and abs(r.valor_cents - linha.valor_cents) <= TOLERANCIA_CENTAVOS
        for r in registros
    )


def montar_previa(session: Session, linhas: list[LinhaFatura], cartao_nome: str) -> list[dict]:
    card = _cartao(session, cartao_nome)
    card_id = card.id if card else None
    previa = []
    for linha in linhas:
        plano = _plano_existente(session, linha, card_id) if card_id else None
        if plano:
            status, incluir = "existente", False
        elif card_id and _ignorada(session, linha, card_id):
            status, incluir = "ignorada", False
        else:
            status, incluir = "nova", True
        previa.append(
            {
                "linha": linha,
                "status": status,
                "plano_id": plano.id if plano else None,
                "nome": plano.description if plano else linha.nome,
                "incluir": incluir,
            }
        )
    return previa


def gravar(session: Session, cartao_nome: str, vencimento: date, itens: list[dict]) -> dict:
    """Cria os parcelamentos marcados, atualiza os escolhidos e guarda as linhas excluídas."""
    card = _cartao(session, cartao_nome)
    if card is None:
        card = Account(name=cartao_nome, type="cartao")
        session.add(card)
        session.flush()

    referencia = vencimento.strftime("%Y-%m")
    dia = vencimento.day
    criadas = atualizadas = ignoradas = 0

    for item in itens:
        linha: LinhaFatura = item["linha"]

        if item["status"] == "existente":
            if item["atualizar"] and item["plano_id"]:
                plano = session.get(InstallmentPlan, int(item["plano_id"]))
                if plano:
                    update_plan(session, plano, item["nome"], linha.valor_cents, dia, item["categorias"])
                    atualizadas += 1
            continue

        if item["incluir"]:
            plano = create_plan(
                session,
                item["nome"],
                "cartao",
                cartao_nome,
                linha.valor_cents,
                linha.total,
                linha.parcela,
                referencia,
                dia,
                item["categorias"],
            )
            plano.origem_csv = linha.nome
            session.add(plano)
            criadas += 1
        elif not _ignorada(session, linha, card.id):
            session.add(
                ImportacaoIgnorada(
                    data_compra=linha.data,
                    nome_original=linha.nome,
                    total=linha.total,
                    account_id=card.id,
                    valor_cents=linha.valor_cents,
                )
            )
            ignoradas += 1

    session.commit()
    generate_installments(session)
    session.commit()
    return {"criadas": criadas, "atualizadas": atualizadas, "ignoradas": ignoradas}
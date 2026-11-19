"""Prévia e gravação da importação da fatura do Nubank."""

from datetime import date

from sqlalchemy import or_
from sqlmodel import Session, select

from app.models import Account, ImportacaoIgnorada, InstallmentPlan
from app.services.fatura_nubank import LinhaFatura, chave_nome, limpa_nome
from app.services.parcelados import (
    converter_para_receber,
    create_plan,
    generate_installments,
    update_plan,
)

TOLERANCIA_CENTAVOS = 20


def _cartao(session: Session, nome: str) -> Account | None:
    return session.exec(
        select(Account).where(Account.name == nome, Account.type == "cartao")
    ).first()


def _plano_existente(session: Session, linha: LinhaFatura, card_id: int) -> InstallmentPlan | None:
    # Parcelado normal guarda o cartão em account_id; compra de terceiro (receber) em cartao_origem_id
    planos = session.exec(
        select(InstallmentPlan).where(
            or_(
                InstallmentPlan.account_id == card_id,
                InstallmentPlan.cartao_origem_id == card_id,
            ),
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


def sem_pessoa(itens: list[dict]) -> list[str]:
    """Nomes das compras marcadas como de outra pessoa, mas sem o nome de quem paga."""
    return [
        i["linha"].nome
        for i in itens
        if i.get("terceiro") and not i.get("pessoa", "").strip()
    ]


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
                "terceiro": False,
                "pessoa": "",
            }
        )
    return previa


def _remover_ignorada(session: Session, linha: LinhaFatura, card_id: int) -> None:
    """Tira a compra da lista de ignoradas, quando ela é cadastrada depois."""
    registros = session.exec(
        select(ImportacaoIgnorada).where(
            ImportacaoIgnorada.total == linha.total,
            ImportacaoIgnorada.account_id == card_id,
        )
    ).all()
    for r in registros:
        if (
            chave_nome(limpa_nome(r.nome_original)) == chave_nome(linha.nome)
            and abs(r.valor_cents - linha.valor_cents) <= TOLERANCIA_CENTAVOS
        ):
            session.delete(r)


def gravar(session: Session, cartao_nome: str, vencimento: date, itens: list[dict]) -> dict:
    """Cria, atualiza ou converte as compras marcadas, e guarda as linhas excluídas.

    Marcar "de outra pessoa" faz a compra virar a receber:
    - nova: cria o plano a receber;
    - já cadastrada: converte o parcelado de cartão em a receber;
    - ignorada antes: cadastra como a receber e tira da lista de ignoradas.
    """
    faltando = sem_pessoa(itens)
    if faltando:
        raise ValueError("Informe quem vai pagar para: " + ", ".join(faltando) + ". Nada foi gravado.")

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
            plano = session.get(InstallmentPlan, int(item["plano_id"])) if item.get("plano_id") else None
            if plano and item.get("terceiro") and plano.tipo == "pagar":
                converter_para_receber(session, plano, item["pessoa"], card.id, linha.parcela, item["categorias"])
                atualizadas += 1
            elif plano and item.get("atualizar"):
                # Compra de terceiro mantém o dia de recebimento já escolhido no plano
                dia_plano = plano.due_day if plano.tipo == "receber" else dia
                update_plan(session, plano, item["nome"], linha.valor_cents, dia_plano, item["categorias"])
                atualizadas += 1
            continue

        if item["incluir"]:
            if item["status"] == "ignorada":
                _remover_ignorada(session, linha, card.id)
            if item.get("terceiro"):
                plano = create_plan(
                    session,
                    item["nome"],
                    "a_receber",
                    "",
                    linha.valor_cents,
                    linha.total,
                    linha.parcela,
                    referencia,
                    dia,
                    item["categorias"],
                    tipo="receber",
                    pessoa=item.get("pessoa", ""),
                    cartao_origem_id=card.id,
                )
            else:
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

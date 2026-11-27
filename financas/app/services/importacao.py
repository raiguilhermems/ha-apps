"""Prévia e gravação da importação da fatura do Nubank.

A prévia separa as linhas do CSV em duas partes:
- Parcelados: viram parcelados do cartão, ou a receber se forem de terceiro.
- Compras de vencimento (à vista): entram na fatura como itens, para conferência. Se forem de
  terceiro, geram um reembolso no vencimento da fatura.

O total da fatura é digitado por você. O CSV só classifica as linhas; se a soma dele não bater
com o total, a prévia mostra um aviso, mas não impede a gravação.
"""

from datetime import date

from sqlalchemy import or_
from sqlmodel import Session, select

from app.models import Account, FaturaCartao, FaturaItem, ImportacaoIgnorada, InstallmentPlan
from app.services.cartoes import garantir_fatura, recalcular, tag_pessoa
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


def _total_chave(linha: LinhaFatura) -> int:
    """Chave de total usada nas ignoradas: parcelas (>= 2) ou 0 para compras à vista."""
    return linha.total if linha.parcelado else 0


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
            ImportacaoIgnorada.total == _total_chave(linha),
            ImportacaoIgnorada.account_id == card_id,
        )
    ).all()
    for r in registros:
        if chave_nome(limpa_nome(r.nome_original)) != chave_nome(linha.nome):
            continue
        if abs(r.valor_cents - linha.valor_cents) > TOLERANCIA_CENTAVOS:
            continue
        # À vista: a mesma compra só conta na mesma data (uma compra igual em outro dia é outra)
        if not linha.parcelado and r.data_compra != linha.data:
            continue
        return True
    return False


def _registrada(session: Session, linha: LinhaFatura, card_id: int) -> bool:
    """Compra à vista já lançada na fatura deste cartão (mesma data, título e valor)."""
    return (
        session.exec(
            select(FaturaItem.id).where(
                FaturaCartao.account_id == card_id,
                FaturaItem.fatura_id == FaturaCartao.id,
                FaturaItem.kind == "vencimento",
                FaturaItem.data_compra == linha.data,
                FaturaItem.nome_original == linha.nome_original,
                FaturaItem.valor_cents == linha.valor_cents,
            )
        ).first()
        is not None
    )


def sem_pessoa(itens: list[dict]) -> list[str]:
    """Nomes das compras marcadas como de outra pessoa, mas sem o nome de quem paga."""
    return [
        i["linha"].nome
        for i in itens
        if i.get("terceiro") and not i.get("pessoa", "").strip()
    ]


def diferenca_total(linhas: list[LinhaFatura], total_cents: int) -> int:
    """Total digitado menos a soma das linhas do CSV. Zero quando batem."""
    return total_cents - sum(l.valor_cents for l in linhas)


def montar_previa(session: Session, linhas: list[LinhaFatura], cartao_nome: str) -> list[dict]:
    card = _cartao(session, cartao_nome)
    card_id = card.id if card else None
    previa = []
    for linha in linhas:
        if linha.parcelado:
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
        else:
            if card_id and _registrada(session, linha, card_id):
                status, incluir = "registrada", False
            elif card_id and _ignorada(session, linha, card_id):
                status, incluir = "ignorada", False
            else:
                status, incluir = "nova", True
            previa.append(
                {
                    "linha": linha,
                    "status": status,
                    "plano_id": None,
                    "nome": linha.nome,
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
            ImportacaoIgnorada.total == _total_chave(linha),
            ImportacaoIgnorada.account_id == card_id,
        )
    ).all()
    for r in registros:
        if (
            chave_nome(limpa_nome(r.nome_original)) == chave_nome(linha.nome)
            and abs(r.valor_cents - linha.valor_cents) <= TOLERANCIA_CENTAVOS
            and (linha.parcelado or r.data_compra == linha.data)
        ):
            session.delete(r)


def _item_fatura(
    session: Session,
    fatura: FaturaCartao,
    linha: LinhaFatura,
    plano_id: int | None,
    terceiro: bool,
    pessoa: str,
    categorias: str,
) -> None:
    session.add(
        FaturaItem(
            fatura_id=fatura.id,
            kind="vencimento" if not linha.parcelado else "parcelado",
            descricao=linha.nome,
            valor_cents=linha.valor_cents,
            destino="terceiro" if terceiro else "sua",
            pessoa=tag_pessoa(session, pessoa) if terceiro else "",
            categorias=categorias,
            plan_id=plano_id,
            data_compra=linha.data,
            nome_original=linha.nome_original,
        )
    )


def gravar(
    session: Session,
    cartao_nome: str,
    vencimento: date,
    itens: list[dict],
    total_cents: int | None = None,
) -> dict:
    """Grava as linhas marcadas e guarda as desmarcadas, para não reaparecerem como novas.

    - Parcelado: nova cria o plano (cartão, ou a receber se for de terceiro); já cadastrada e
      marcada de terceiro converte o parcelado de cartão em a receber; ignorada antes e marcada
      volta a contar.
    - Compra à vista: vira item da fatura (sua ou de terceiro).
    - Com total_cents, a fatura é criada ou atualizada com esse total, e a despesa dela no
      Início fica líquida do que é de terceiro. Sem total, só parcelados são gravados.
    """
    faltando = sem_pessoa(itens)
    if faltando:
        raise ValueError("Informe quem vai pagar para: " + ", ".join(faltando) + ". Nada foi gravado.")
    avulsas = [i for i in itens if i["incluir"] and not i["linha"].parcelado]
    if avulsas and total_cents is None:
        raise ValueError("Informe o total da fatura antes de gravar as compras à vista. Nada foi gravado.")

    card = _cartao(session, cartao_nome)
    if card is None:
        card = Account(name=cartao_nome, type="cartao")
        session.add(card)
        session.flush()

    referencia = vencimento.strftime("%Y-%m")
    dia = vencimento.day
    fatura = garantir_fatura(session, card, referencia, total_cents) if total_cents is not None else None
    criadas = atualizadas = ignoradas = 0

    for item in itens:
        linha: LinhaFatura = item["linha"]
        terceiro = bool(item.get("terceiro"))
        categorias = item.get("categorias", "")

        if item["status"] == "registrada":
            continue

        if item["status"] == "existente":
            plano = session.get(InstallmentPlan, int(item["plano_id"])) if item.get("plano_id") else None
            if plano and terceiro and plano.tipo == "pagar":
                converter_para_receber(session, plano, item["pessoa"], card.id, linha.parcela, categorias)
                atualizadas += 1
                if fatura is not None:
                    _item_fatura(session, fatura, linha, plano.id, True, item["pessoa"], categorias)
            elif plano and item.get("atualizar"):
                # Compra de terceiro mantém o dia de recebimento já escolhido no plano
                dia_plano = plano.due_day if plano.tipo == "receber" else dia
                update_plan(session, plano, item["nome"], linha.valor_cents, dia_plano, categorias)
                atualizadas += 1
            continue

        if item["incluir"]:
            if item["status"] == "ignorada":
                _remover_ignorada(session, linha, card.id)
            if linha.parcelado:
                if terceiro:
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
                        categorias,
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
                        categorias,
                    )
                plano.origem_csv = linha.nome
                session.add(plano)
                session.flush()
                if fatura is not None:
                    _item_fatura(session, fatura, linha, plano.id, terceiro, item.get("pessoa", ""), categorias)
            elif fatura is not None:
                _item_fatura(session, fatura, linha, None, terceiro, item.get("pessoa", ""), categorias)
            criadas += 1
        elif not _ignorada(session, linha, card.id):
            session.add(
                ImportacaoIgnorada(
                    data_compra=linha.data,
                    nome_original=linha.nome,
                    total=_total_chave(linha),
                    account_id=card.id,
                    valor_cents=linha.valor_cents,
                )
            )
            ignoradas += 1

    if fatura is not None:
        recalcular(session, card, fatura)
    session.commit()
    generate_installments(session)
    session.commit()
    return {"criadas": criadas, "atualizadas": atualizadas, "ignoradas": ignoradas}

"""Cartões: cadastro, fatura mensal, compras da fatura e pagamento.

Modelo de reembolso:
- o total da fatura é digitado por você (não vem do CSV);
- cada compra da fatura é sua ou de terceiro (campo "destino");
- o que é de terceiro sai da sua despesa: a despesa da fatura no Início é o líquido
  (total menos terceiros). O líquido também fica guardado na fatura, para o histórico;
- cada pessoa que vai devolver vira um reembolso (a receber) no vencimento da fatura.
  Reembolso não conta como receita: a despesa já está líquida.

Ao marcar a despesa da fatura como paga (no Início ou aqui), quitam as parcelas e as
recorrências do cartão com vencimento no mês da fatura.
"""

import calendar
import re
import unicodedata
from datetime import date, timedelta

from sqlmodel import Session, select

from app.models import (
    Account,
    FaturaCartao,
    FaturaItem,
    ImportacaoIgnorada,
    InstallmentPlan,
    RecurringRule,
    Tag,
    Transaction,
    TransactionTag,
)
from app.services.tags import PESSOA, parse_tags, reservar_categoria, set_tags
from app.services.util import add_months, mes_curto, month_bounds, nome_proprio

MES_RE = re.compile(r"\d{4}-(0[1-9]|1[0-2])")
# Itens que geram um reembolso no vencimento. Parcelado de terceiro segue o cronograma do plano.
TIPOS_REEMBOLSO = ("vencimento", "manual")


def normaliza(nome: str) -> str:
    """Compara nomes sem diferença de maiúsculas, acento ou espaços."""
    sem_acento = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode()
    return " ".join(sem_acento.lower().split())


def listar(session: Session) -> list[Account]:
    return session.exec(
        select(Account).where(Account.type == "cartao").order_by(Account.name)
    ).all()


def buscar_por_nome(session: Session, nome: str) -> Account | None:
    alvo = normaliza(nome)
    for cartao in listar(session):
        if normaliza(cartao.name) == alvo:
            return cartao
    return None


def _valida(nome: str, dia: int | None, fechamento: int | None) -> str:
    """Nome e vencimento são obrigatórios. Fechamento é opcional aqui (a importação não o pede),
    mas, se vier, tem de ser um dia do mês. A tela de Cartões exige o fechamento."""
    nome = " ".join(nome.split())
    if not nome:
        raise ValueError("Informe o nome do cartão")
    if dia is None or not 1 <= dia <= 31:
        raise ValueError("Informe o dia de vencimento da fatura (de 1 a 31)")
    if fechamento is not None and not 1 <= fechamento <= 31:
        raise ValueError("O dia de fechamento da fatura deve estar entre 1 e 31")
    return nome


def validar_novo(session: Session, nome: str, dia: int | None, fechamento: int | None = None) -> str:
    """Valida um cartão que ainda não existe, sem gravar. Devolve o nome normalizado."""
    nome = _valida(nome, dia, fechamento)
    existente = buscar_por_nome(session, nome)
    if existente:
        raise ValueError(f"Já existe o cartão {existente.name}")
    return nome


def criar(session: Session, nome: str, dia: int | None, fechamento: int | None = None) -> Account:
    nome = validar_novo(session, nome, dia, fechamento)
    cartao = Account(name=nome, type="cartao", dia_pagamento=dia, dia_fechamento=fechamento)
    session.add(cartao)
    session.flush()
    return cartao


def atualizar(
    session: Session, cartao: Account, nome: str, dia: int | None, fechamento: int | None
) -> None:
    nome = _valida(nome, dia, fechamento)
    outro = buscar_por_nome(session, nome)
    if outro and outro.id != cartao.id:
        raise ValueError(f"Já existe o cartão {outro.name}")
    cartao.name = nome
    cartao.dia_pagamento = dia
    cartao.dia_fechamento = fechamento
    session.add(cartao)


def vinculos(session: Session, cartao: Account) -> int:
    planos = session.exec(
        select(InstallmentPlan).where(InstallmentPlan.account_id == cartao.id)
    ).all()
    recorrentes = session.exec(
        select(RecurringRule).where(RecurringRule.account_id == cartao.id)
    ).all()
    faturas = session.exec(
        select(FaturaCartao).where(FaturaCartao.account_id == cartao.id)
    ).all()
    return len(planos) + len(recorrentes) + len(faturas)


def excluir(session: Session, cartao: Account) -> None:
    if vinculos(session, cartao):
        raise ValueError(
            "Este cartão tem parcelamentos, recorrentes ou faturas vinculados e não pode ser excluído"
        )
    session.delete(cartao)


def vencimento_fatura(ref: str, dia: int) -> date:
    """Dia de vencimento no mês ref (AAAA-MM). Se cair em fim de semana, vai para o próximo dia útil."""
    try:
        ano, mes = int(ref[:4]), int(ref[5:7])
    except ValueError:
        raise ValueError("Mês da fatura inválido")
    ultimo = calendar.monthrange(ano, mes)[1]
    d = date(ano, mes, min(dia, ultimo))
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d


def fechamento_fatura(ref: str, dia_fechamento: int, dia_vencimento: int) -> date:
    """Dia em que fecha a fatura que vence no mês ref.

    Se o fechamento cai depois do vencimento no calendário (ex.: fecha dia 25 e vence dia 5),
    a fatura fechou no mês anterior.
    """
    mes = ref if dia_fechamento < dia_vencimento else add_months(ref, -1)
    ano, m = int(mes[:4]), int(mes[5:7])
    return date(ano, m, min(dia_fechamento, calendar.monthrange(ano, m)[1]))


def buscar_fatura(session: Session, cartao_id: int, ref: str) -> FaturaCartao | None:
    return session.exec(
        select(FaturaCartao).where(
            FaturaCartao.account_id == cartao_id, FaturaCartao.referencia == ref
        )
    ).first()


def fatura_de_transacao(session: Session, tx: Transaction) -> FaturaCartao | None:
    """Fatura ligada a este lançamento do Início (despesa da fatura ou reembolso), se houver."""
    fatura = session.exec(
        select(FaturaCartao).where(FaturaCartao.tx_despesa_id == tx.id)
    ).first()
    if fatura is None and tx.fatura_id is not None:
        fatura = session.get(FaturaCartao, tx.fatura_id)
    if fatura is None:
        fatura = session.exec(
            select(FaturaCartao).where(FaturaCartao.tx_receita_id == tx.id)
        ).first()
    return fatura


def tag_pessoa(session: Session, nome: str) -> str:
    """Nome normalizado de quem vai pagar. Cria a categoria do tipo pessoa, se preciso."""
    nomes = parse_tags(" ".join(nome.replace(",", " ").replace(";", " ").split()))
    if not nomes:
        raise ValueError("Informe o nome de quem vai pagar")
    reservar_categoria(session, nomes[0], PESSOA, set(), "a pessoa")
    return nomes[0]


def _nome_unico(pessoa: str) -> str:
    nome = " ".join(pessoa.split())
    if "," in nome or ";" in nome:
        raise ValueError("Informe um nome só por vez")
    return nome


def _pendentes_do_cartao(session: Session, cartao_id: int, ref: str) -> list[Transaction]:
    """Parcelas e recorrências do cartão, ainda não pagas, com vencimento no mês ref."""
    start, end = month_bounds(ref)
    return list(
        session.exec(
            select(Transaction).where(
                Transaction.account_id == cartao_id,
                Transaction.kind == "despesa",
                Transaction.status == "pendente",
                Transaction.due_date >= start,
                Transaction.due_date < end,
            )
        ).all()
    )


def resumo_fatura(session: Session, cartao: Account, ref: str) -> dict:
    """Situação do cartão no mês ref: datas, fatura lançada, compras e reembolsos."""
    hoje = date.today()
    vence = None
    fecha = None
    if cartao.dia_pagamento:
        vence = vencimento_fatura(ref, cartao.dia_pagamento)
    if cartao.dia_pagamento and cartao.dia_fechamento:
        fecha = fechamento_fatura(ref, cartao.dia_fechamento, cartao.dia_pagamento)

    fatura = buscar_fatura(session, cartao.id, ref)
    despesa = session.get(Transaction, fatura.tx_despesa_id) if fatura else None
    itens = []
    reembolsos = []
    if fatura is not None:
        itens = session.exec(
            select(FaturaItem).where(FaturaItem.fatura_id == fatura.id).order_by(FaturaItem.id)
        ).all()
        reembolsos = session.exec(
            select(Transaction).where(Transaction.fatura_id == fatura.id).order_by(Transaction.id)
        ).all()
    pendentes = _pendentes_do_cartao(session, cartao.id, ref)

    if despesa is not None and despesa.status == "pago":
        situacao = "paga"
    elif fecha is None:
        situacao = "sem fechamento"
    elif hoje <= fecha:
        situacao = "em aberto"
    else:
        situacao = "fechada"

    return {
        "cartao": cartao,
        "vence": vence,
        "fecha": fecha,
        "fatura": fatura,
        "despesa": despesa,
        "itens": itens,
        "reembolsos": reembolsos,
        "situacao": situacao,
        "pendentes_qtd": len(pendentes) if despesa is not None and despesa.status == "pendente" else 0,
        "pendentes_valor": sum(t.amount_cents for t in pendentes)
        if despesa is not None and despesa.status == "pendente"
        else 0,
    }


def _apagar_tx(session: Session, tx: Transaction) -> None:
    for link in session.exec(
        select(TransactionTag).where(TransactionTag.transaction_id == tx.id)
    ).all():
        session.delete(link)
    session.delete(tx)


def _pessoa_da_tx(session: Session, tx: Transaction) -> str:
    tag = session.exec(
        select(Tag)
        .join(TransactionTag, TransactionTag.tag_id == Tag.id)
        .where(TransactionTag.transaction_id == tx.id, Tag.kind == "pessoa")
    ).first()
    return tag.name if tag else ""


def garantir_fatura(session: Session, cartao: Account, ref: str, total_cents: int) -> FaturaCartao:
    """Cria ou atualiza a fatura do mês ref com o total digitado, e a despesa dela no Início.

    Só exige o vencimento do cartão. Os valores (líquido, terceiros, reembolsos) são
    recalculados por recalcular().
    """
    if not MES_RE.fullmatch(ref or ""):
        raise ValueError("Mês da fatura inválido")
    if not cartao.dia_pagamento:
        raise ValueError("Complete o cadastro do cartão (vencimento) antes de lançar a fatura")
    if total_cents <= 0:
        raise ValueError("Informe o valor total da fatura")

    venc = vencimento_fatura(ref, cartao.dia_pagamento)
    descricao = f"Fatura {cartao.name} · {mes_curto(ref)}"
    fatura = buscar_fatura(session, cartao.id, ref)
    if fatura is None:
        despesa = Transaction(
            description=descricao, amount_cents=0, due_date=venc, kind="despesa", status="pendente"
        )
        session.add(despesa)
        session.flush()
        fatura = FaturaCartao(
            account_id=cartao.id, referencia=ref, total_cents=total_cents, tx_despesa_id=despesa.id
        )
        session.add(fatura)
    despesa = session.get(Transaction, fatura.tx_despesa_id)
    despesa.description = descricao
    despesa.due_date = venc
    fatura.total_cents = total_cents
    session.add_all([despesa, fatura])
    session.flush()
    return fatura


def recalcular(session: Session, cartao: Account, fatura: FaturaCartao) -> None:
    """Atualiza a despesa (líquido), os totais e os reembolsos da fatura a partir dos itens.

    Levanta ValueError se a fatura não puder mudar (ex.: já paga). O chamador faz rollback.
    """
    itens = session.exec(select(FaturaItem).where(FaturaItem.fatura_id == fatura.id)).all()
    terceiro = sum(i.valor_cents for i in itens if i.destino == "terceiro")
    if terceiro > fatura.total_cents:
        raise ValueError(
            "O que é de terceiro passa do total da fatura. Confira o total ou as compras"
        )
    liquido = fatura.total_cents - terceiro

    despesa = session.get(Transaction, fatura.tx_despesa_id)
    if despesa.status == "pago" and despesa.amount_cents != liquido:
        raise ValueError("Desfaça o pagamento da fatura antes de mudar os valores dela")
    venc = vencimento_fatura(fatura.referencia, cartao.dia_pagamento)
    despesa.amount_cents = liquido
    despesa.due_date = venc
    session.add(despesa)

    # Um reembolso por pessoa, no vencimento da fatura (compras à vista e lançamentos manuais)
    grupos: dict[str, int] = {}
    for i in itens:
        if i.destino == "terceiro" and i.kind in TIPOS_REEMBOLSO:
            grupos[i.pessoa] = grupos.get(i.pessoa, 0) + i.valor_cents

    existentes: dict[str, Transaction] = {}
    for tx in session.exec(select(Transaction).where(Transaction.fatura_id == fatura.id)).all():
        existentes[_pessoa_da_tx(session, tx)] = tx
    if fatura.tx_receita_id:
        legado = session.get(Transaction, fatura.tx_receita_id)
        if legado is not None and legado.id not in {t.id for t in existentes.values()}:
            existentes.setdefault(_pessoa_da_tx(session, legado), legado)

    for pessoa, valor in grupos.items():
        tx = existentes.pop(pessoa, None)
        if tx is None:
            tx = Transaction(description="", amount_cents=0, due_date=venc, kind="receita")
        elif tx.status == "pago" and tx.amount_cents != valor:
            raise ValueError(
                f"{nome_proprio(pessoa)} já pagou. Desfaça o recebimento no Início antes de mudar o valor"
            )
        tx.description = f"{nome_proprio(pessoa)} · Fatura {cartao.name} · {mes_curto(fatura.referencia)}"
        tx.amount_cents = valor
        tx.due_date = venc
        tx.kind = "receita"
        tx.reembolso = True
        tx.fatura_id = fatura.id
        tx.account_id = None
        session.add(tx)
        session.flush()
        set_tags(session, tx, [pessoa])

    for tx in existentes.values():
        if tx.status == "pago":
            raise ValueError(
                "Já há um recebimento marcado nesta fatura. Desfaça-o no Início antes de tirar o reembolso"
            )
        _apagar_tx(session, tx)

    fatura.terceiro_cents = terceiro
    fatura.liquido_cents = liquido
    fatura.pessoa = ", ".join(sorted(grupos))
    fatura.tx_receita_id = None
    session.add(fatura)
    session.flush()


def lancar_fatura(
    session: Session,
    cartao: Account,
    ref: str,
    total_cents: int,
    terceiro_cents: int,
    pessoa: str = "",
) -> FaturaCartao:
    """Lança o total da fatura e, se houver, um valor de terceiro digitado à mão.

    O valor à mão vira um item "manual" da fatura. Compras importadas continuam na fatura.
    Levanta ValueError, sem gravar nada, se algo estiver errado (o chamador faz rollback).
    """
    if not 0 <= terceiro_cents <= total_cents:
        raise ValueError("O valor pago por terceiro deve ficar entre zero e o total da fatura")
    nome = _nome_unico(pessoa) if terceiro_cents > 0 else ""
    if terceiro_cents > 0 and not nome:
        raise ValueError("Informe o nome de quem pagou por terceiro")

    fatura = garantir_fatura(session, cartao, ref, total_cents)
    for item in session.exec(
        select(FaturaItem).where(FaturaItem.fatura_id == fatura.id, FaturaItem.kind == "manual")
    ).all():
        session.delete(item)
    session.flush()
    if terceiro_cents > 0:
        session.add(
            FaturaItem(
                fatura_id=fatura.id,
                kind="manual",
                descricao="Pago por terceiro (lançado à mão)",
                valor_cents=terceiro_cents,
                destino="terceiro",
                pessoa=tag_pessoa(session, nome),
            )
        )
    session.flush()
    recalcular(session, cartao, fatura)
    return fatura


def _item_da_fatura(session: Session, fatura: FaturaCartao, item_id: int) -> FaturaItem:
    item = session.get(FaturaItem, item_id)
    if item is None or item.fatura_id != fatura.id:
        raise ValueError("Compra não encontrada nesta fatura")
    return item


def editar_item(
    session: Session,
    cartao: Account,
    fatura: FaturaCartao,
    item_id: int,
    descricao: str,
    destino: str,
    pessoa: str,
    categorias: str,
) -> None:
    """Muda o nome, quem paga e as categorias de uma compra da fatura. Recalcula a fatura.

    Parcelado também: a mudança vai para o plano, que atualiza as parcelas pendentes.
    O valor da compra vem do CSV e não muda aqui.
    """
    item = _item_da_fatura(session, fatura, item_id)
    descricao = " ".join(descricao.split())
    if not descricao:
        raise ValueError("Informe o nome da compra")
    if destino not in ("sua", "terceiro"):
        raise ValueError("Destino inválido")
    nome_pessoa = _nome_unico(pessoa) if destino == "terceiro" else ""
    if item.kind == "parcelado":
        _editar_parcelado(session, cartao, item, descricao, destino, nome_pessoa, categorias)
    else:
        item.descricao = descricao
        item.destino = destino
        item.pessoa = tag_pessoa(session, nome_pessoa) if destino == "terceiro" else ""
        item.categorias = " ".join(categorias.split())
        session.add(item)
    session.flush()
    recalcular(session, cartao, fatura)


def _editar_parcelado(
    session: Session,
    cartao: Account,
    item: FaturaItem,
    descricao: str,
    destino: str,
    nome_pessoa: str,
    categorias: str,
) -> None:
    """Parcelado editado na fatura: vai para o plano, e as parcelas pendentes acompanham."""
    # Import local: parcelados já importa este módulo
    from app.services.parcelados import converter_para_receber, update_plan

    plano = session.get(InstallmentPlan, item.plan_id) if item.plan_id else None
    if plano is None:
        raise ValueError("Parcelado não encontrado")
    categorias = " ".join(categorias.split())
    if destino == "terceiro":
        if not nome_pessoa:
            raise ValueError("Informe o nome de quem vai pagar")
        if plano.tipo == "pagar":
            # Vira a receber: as parcelas pendentes do cartão saem e as de terceiro entram
            converter_para_receber(session, plano, nome_pessoa, cartao.id, plano.parcela_inicial, categorias)
        else:
            plano.pessoa = nome_pessoa
            session.add(plano)
    elif plano.tipo == "receber":
        raise ValueError(
            "Este parcelado é de terceiro. Para ele voltar a ser seu, exclua-o em Parcelados e cadastre de novo"
        )
    update_plan(session, plano, descricao, plano.installment_cents, plano.due_day, categorias)
    item.descricao = descricao
    item.destino = destino
    item.pessoa = tag_pessoa(session, nome_pessoa) if destino == "terceiro" else ""
    item.categorias = categorias
    session.add(item)


def excluir_item(session: Session, cartao: Account, fatura: FaturaCartao, item_id: int) -> None:
    """Tira uma compra da fatura (à vista ou à mão). Se for de terceiro, o reembolso dela sai.

    Compra à vista removida vai para o histórico de ignoradas, para não voltar como nova
    quando o mesmo CSV for importado de novo.
    """
    item = _item_da_fatura(session, fatura, item_id)
    if item.kind == "parcelado":
        raise ValueError("Parcelado não sai da fatura por aqui. Exclua-o em Parcelados")
    if item.kind == "vencimento" and item.data_compra is not None:
        ja_ignorada = session.exec(
            select(ImportacaoIgnorada).where(
                ImportacaoIgnorada.account_id == cartao.id,
                ImportacaoIgnorada.total == 0,
                ImportacaoIgnorada.data_compra == item.data_compra,
                ImportacaoIgnorada.nome_original == item.nome_original,
                ImportacaoIgnorada.valor_cents == item.valor_cents,
            )
        ).first()
        if ja_ignorada is None:
            session.add(
                ImportacaoIgnorada(
                    data_compra=item.data_compra,
                    nome_original=item.nome_original,
                    total=0,
                    account_id=cartao.id,
                    valor_cents=item.valor_cents,
                )
            )
    session.delete(item)
    session.flush()
    recalcular(session, cartao, fatura)


def renomear_pessoa_nas_faturas(session: Session, antigo: str, novo: str) -> None:
    """Troca o nome de uma pessoa nas compras das faturas e recalcula os reembolsos.

    Chamada depois que a categoria já foi renomeada: os reembolsos seguem a categoria, e o
    recálculo atualiza a descrição e o vínculo deles.
    """
    itens = session.exec(select(FaturaItem).where(FaturaItem.pessoa == antigo)).all()
    faturas_ids = set()
    for item in itens:
        item.pessoa = novo
        session.add(item)
        faturas_ids.add(item.fatura_id)
    session.flush()
    for fatura_id in faturas_ids:
        fatura = session.get(FaturaCartao, fatura_id)
        cartao = session.get(Account, fatura.account_id)
        recalcular(session, cartao, fatura)


def aplicar_edicoes(session: Session, cartao: Account, fatura: FaturaCartao, alteracoes: list[dict]) -> None:
    """Aplica de uma vez as mudanças da tela de edição. Se uma falhar, nada é gravado."""
    for a in alteracoes:
        if a["remover"]:
            excluir_item(session, cartao, fatura, a["id"])
        else:
            editar_item(
                session, cartao, fatura, a["id"], a["descricao"], a["destino"], a["pessoa"], a["categorias"]
            )


def excluir_fatura(session: Session, fatura: FaturaCartao) -> None:
    """Remove a fatura, as compras dela e os lançamentos do Início. Só se nada estiver pago."""
    despesa = session.get(Transaction, fatura.tx_despesa_id)
    reembolsos = list(session.exec(select(Transaction).where(Transaction.fatura_id == fatura.id)).all())
    legado = session.get(Transaction, fatura.tx_receita_id) if fatura.tx_receita_id else None
    if legado is not None and legado.id not in {t.id for t in reembolsos}:
        reembolsos.append(legado)
    if despesa is not None and despesa.status == "pago":
        raise ValueError("Desfaça o pagamento da fatura antes de excluí-la")
    if any(r.status == "pago" for r in reembolsos):
        raise ValueError("Desfaça o recebimento dos reembolsos desta fatura antes de excluí-la")

    for item in session.exec(select(FaturaItem).where(FaturaItem.fatura_id == fatura.id)).all():
        session.delete(item)
    session.delete(fatura)
    session.flush()
    for tx in [despesa, *reembolsos]:
        if tx is not None:
            _apagar_tx(session, tx)


def quitar_mes_do_cartao(session: Session, cartao_id: int, ref: str) -> int:
    """Marca como pagas as parcelas e recorrências do cartão do mês ref. Devolve quantas foram."""
    hoje = date.today()
    txs = _pendentes_do_cartao(session, cartao_id, ref)
    for t in txs:
        t.status = "pago"
        t.paid_date = hoje
        session.add(t)
    session.flush()
    return len(txs)


def alternar_pagamento(session: Session, tx: Transaction) -> None:
    """Marca ou desmarca o lançamento como pago.

    Ao pagar a despesa de uma fatura, quita também as parcelas e recorrências do cartão no mês.
    Desfazer a fatura não reverte essas parcelas: elas podem ter sido pagas antes, de propósito.
    """
    if tx.status == "pendente":
        tx.status = "pago"
        tx.paid_date = date.today()
        session.add(tx)
        fatura = fatura_de_transacao(session, tx)
        if fatura is not None and tx.id == fatura.tx_despesa_id:
            quitar_mes_do_cartao(session, fatura.account_id, fatura.referencia)
    else:
        tx.status = "pendente"
        tx.paid_date = None
        session.add(tx)

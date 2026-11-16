"""Cadastro de cartões: nome, dia de pagamento da fatura e regras de vencimento."""

import calendar
import unicodedata
from datetime import date, timedelta

from sqlmodel import Session, select

from app.models import Account, InstallmentPlan, RecurringRule


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


def _valida(nome: str, dia: int | None) -> str:
    nome = " ".join(nome.split())
    if not nome:
        raise ValueError("Informe o nome do cartão")
    if dia is None or not 1 <= dia <= 31:
        raise ValueError("Informe o dia de pagamento da fatura (de 1 a 31)")
    return nome


def criar(session: Session, nome: str, dia: int | None) -> Account:
    nome = _valida(nome, dia)
    existente = buscar_por_nome(session, nome)
    if existente:
        raise ValueError(f"Já existe o cartão {existente.name}")
    cartao = Account(name=nome, type="cartao", dia_pagamento=dia)
    session.add(cartao)
    session.flush()
    return cartao


def atualizar(session: Session, cartao: Account, nome: str, dia: int | None) -> None:
    nome = _valida(nome, dia)
    outro = buscar_por_nome(session, nome)
    if outro and outro.id != cartao.id:
        raise ValueError(f"Já existe o cartão {outro.name}")
    cartao.name = nome
    cartao.dia_pagamento = dia
    session.add(cartao)


def vinculos(session: Session, cartao: Account) -> int:
    planos = session.exec(
        select(InstallmentPlan).where(InstallmentPlan.account_id == cartao.id)
    ).all()
    recorrentes = session.exec(
        select(RecurringRule).where(RecurringRule.account_id == cartao.id)
    ).all()
    return len(planos) + len(recorrentes)


def excluir(session: Session, cartao: Account) -> None:
    if vinculos(session, cartao):
        raise ValueError("Este cartão tem parcelamentos ou recorrentes vinculados e não pode ser excluído")
    session.delete(cartao)


def vencimento_fatura(ref: str, dia: int) -> date:
    """Dia de pagamento no mês ref (AAAA-MM). Se cair em fim de semana, vai para o próximo dia útil."""
    try:
        ano, mes = int(ref[:4]), int(ref[5:7])
    except ValueError:
        raise ValueError("Mês da fatura inválido")
    ultimo = calendar.monthrange(ano, mes)[1]
    d = date(ano, mes, min(dia, ultimo))
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d

"""Fatura de cartão: lançamento no Início, pago por terceiro e quitação das parcelas do mês."""

from datetime import date

import pytest
from sqlmodel import select

from app.models import Account, FaturaCartao, Tag, TransactionTag, Transaction
from app.services.cartoes import (
    alternar_pagamento,
    criar,
    excluir_fatura,
    fechamento_fatura,
    lancar_fatura,
)
from app.services.summary import monthly_summary


def _cartao(session, nome="Nubank", dia=5, fechamento=25):
    cartao = criar(session, nome, dia, fechamento)
    session.commit()
    return cartao


def _fatura(session):
    return session.exec(select(FaturaCartao)).one()


def _tx(session, descricao, valor, vencimento, cartao_id=None, status="pendente", kind="despesa"):
    tx = Transaction(
        description=descricao,
        amount_cents=valor,
        due_date=vencimento,
        kind=kind,
        account_id=cartao_id,
        status=status,
    )
    session.add(tx)
    session.flush()
    return tx


def test_fechamento_cai_no_mes_anterior_quando_vem_depois_do_vencimento():
    assert fechamento_fatura("2026-11", 25, 5) == date(2026, 10, 25)


def test_fechamento_cai_no_mesmo_mes_quando_vem_antes_do_vencimento():
    assert fechamento_fatura("2026-11", 3, 10) == date(2026, 11, 3)


def test_lancar_fatura_cria_so_a_despesa_no_inicio(session):
    cartao = _cartao(session)
    lancar_fatura(session, cartao, "2026-11", 100000, 0, "")
    session.commit()
    fatura = _fatura(session)
    despesa = session.get(Transaction, fatura.tx_despesa_id)
    assert despesa.kind == "despesa"
    assert despesa.amount_cents == 100000
    assert despesa.account_id is None  # fica no Início, não é conta de cartão
    assert despesa.due_date == date(2026, 11, 5)
    assert fatura.liquido_cents == 100000
    assert session.exec(select(Transaction).where(Transaction.fatura_id == fatura.id)).all() == []


def test_pago_por_terceiro_desconta_da_despesa_e_vira_receita_pessoa(session):
    cartao = _cartao(session)
    lancar_fatura(session, cartao, "2026-11", 100000, 30000, "ana lima")
    session.commit()
    fatura = _fatura(session)
    despesa = session.get(Transaction, fatura.tx_despesa_id)
    receita = session.exec(select(Transaction).where(Transaction.fatura_id == fatura.id)).one()
    assert despesa.amount_cents == 70000
    assert fatura.liquido_cents == 70000
    assert receita.kind == "receita"
    assert receita.reembolso is True  # a receber, não é receita de verdade
    assert receita.amount_cents == 30000
    tag = session.exec(select(Tag).where(Tag.name == "ana lima")).one()
    assert tag.kind == "pessoa"
    vinculo = session.exec(
        select(TransactionTag).where(TransactionTag.transaction_id == receita.id)
    ).one()
    assert vinculo.tag_id == tag.id


def test_pago_por_terceiro_sem_nome_nao_grava_nada(session):
    cartao = _cartao(session)
    with pytest.raises(ValueError):
        lancar_fatura(session, cartao, "2026-11", 100000, 30000, "")
    assert session.exec(select(FaturaCartao)).first() is None


def test_mais_de_um_nome_por_fatura_nao_e_aceito(session):
    cartao = _cartao(session)
    with pytest.raises(ValueError):
        lancar_fatura(session, cartao, "2026-11", 100000, 30000, "ana, bia")


def test_terceiro_nao_pode_passar_do_total(session):
    cartao = _cartao(session)
    with pytest.raises(ValueError):
        lancar_fatura(session, cartao, "2026-11", 100000, 120000, "ana")


def test_salvar_de_novo_atualiza_a_mesma_fatura_sem_duplicar(session):
    cartao = _cartao(session)
    lancar_fatura(session, cartao, "2026-11", 100000, 0, "")
    session.commit()
    lancar_fatura(session, cartao, "2026-11", 120000, 20000, "bia")
    session.commit()
    assert len(session.exec(select(FaturaCartao)).all()) == 1
    despesas = session.exec(select(Transaction).where(Transaction.kind == "despesa")).all()
    receitas = session.exec(select(Transaction).where(Transaction.kind == "receita")).all()
    assert [t.amount_cents for t in despesas] == [100000]  # 120000 menos 20000 de terceiro
    assert [t.amount_cents for t in receitas] == [20000]


def test_pagar_fatura_quita_parcelas_e_recorrencias_do_cartao_no_mes(session):
    cartao = _cartao(session)
    parcela = _tx(session, "TV (1/3)", 10000, date(2026, 11, 10), cartao.id)
    recorrente = _tx(session, "streaming", 4000, date(2026, 11, 5), cartao.id)
    parcela_dezembro = _tx(session, "TV (2/3)", 10000, date(2026, 12, 10), cartao.id)
    lancar_fatura(session, cartao, "2026-11", 50000, 0, "")
    session.commit()
    despesa = session.get(Transaction, _fatura(session).tx_despesa_id)

    alternar_pagamento(session, despesa)
    session.commit()

    assert despesa.status == "pago"
    assert parcela.status == "pago"
    assert recorrente.status == "pago"
    assert parcela_dezembro.status == "pendente"  # outro mês não muda


def test_desfazer_fatura_nao_reverte_as_parcelas_ja_quitadas(session):
    cartao = _cartao(session)
    parcela = _tx(session, "TV (1/3)", 10000, date(2026, 11, 10), cartao.id)
    lancar_fatura(session, cartao, "2026-11", 50000, 0, "")
    session.commit()
    despesa = session.get(Transaction, _fatura(session).tx_despesa_id)
    alternar_pagamento(session, despesa)
    session.commit()
    alternar_pagamento(session, despesa)
    session.commit()
    assert despesa.status == "pendente"
    assert parcela.status == "pago"


def test_fatura_paga_nao_pode_ser_excluida(session):
    cartao = _cartao(session)
    lancar_fatura(session, cartao, "2026-11", 50000, 0, "")
    session.commit()
    fatura = _fatura(session)
    alternar_pagamento(session, session.get(Transaction, fatura.tx_despesa_id))
    session.commit()
    with pytest.raises(ValueError):
        excluir_fatura(session, fatura)


def test_excluir_fatura_remove_despesa_e_receita(session):
    cartao = _cartao(session)
    lancar_fatura(session, cartao, "2026-11", 100000, 30000, "ana")
    session.commit()
    fatura = _fatura(session)
    ids = [fatura.tx_despesa_id] + [
        t.id for t in session.exec(select(Transaction).where(Transaction.fatura_id == fatura.id)).all()
    ]
    assert len(ids) == 2
    excluir_fatura(session, fatura)
    session.commit()
    assert session.exec(select(FaturaCartao)).first() is None
    assert session.exec(select(Transaction).where(Transaction.id.in_(ids))).all() == []


def test_cartao_sem_vencimento_ou_fechamento_nao_lanca_fatura(session):
    antigo = Account(name="Antigo", type="cartao")
    session.add(antigo)
    session.commit()
    with pytest.raises(ValueError):
        lancar_fatura(session, antigo, "2026-11", 50000, 0, "")


def test_terceiro_antigo_no_banco_nao_desconta_no_inicio(session):
    tx = _tx(session, "Jantar com amigos", 10000, date(2026, 11, 10))
    tx.third_party_cents = 4000  # lançamento antigo, guardado só para registro
    session.add(tx)
    session.commit()
    resumo = monthly_summary(session, "2026-11")
    assert resumo["despesas_total"] == 10000


def test_reembolso_nao_conta_como_receita_no_resumo(session):
    cartao = _cartao(session)
    lancar_fatura(session, cartao, "2026-11", 100000, 30000, "ana")
    session.commit()
    resumo = monthly_summary(session, "2026-11")
    assert resumo["receitas_total"] == 0  # o reembolso é a receber, não receita
    assert resumo["despesas_total"] == 70000  # a sua parte da fatura


def test_lancar_de_novo_com_outro_terceiro_troca_o_reembolso(session):
    cartao = _cartao(session)
    lancar_fatura(session, cartao, "2026-11", 100000, 30000, "ana")
    session.commit()
    lancar_fatura(session, cartao, "2026-11", 100000, 0, "")
    session.commit()
    assert session.exec(select(Transaction).where(Transaction.reembolso.is_(True))).all() == []
    assert session.get(Transaction, _fatura(session).tx_despesa_id).amount_cents == 100000

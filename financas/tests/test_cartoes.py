from datetime import date

import pytest

from app.services.cartoes import criar, excluir, listar, validar_novo, vencimento_fatura
from app.services.parcelados import create_plan


def test_vencimento_em_dia_util():
    assert vencimento_fatura("2026-11", 5) == date(2026, 11, 5)


def test_vencimento_em_sabado_vai_para_segunda():
    # 1º de agosto de 2026 é sábado: o pagamento passa para 3 de agosto (segunda)
    assert vencimento_fatura("2026-08", 1) == date(2026, 8, 3)


def test_dia_31_em_fevereiro_usa_ultimo_dia_e_pula_fim_de_semana():
    # 28 de fevereiro de 2026 é sábado: vai para 2 de março (segunda)
    assert vencimento_fatura("2026-02", 31) == date(2026, 3, 2)


def test_nome_repetido_ignora_caixa_e_acento(session):
    criar(session, "Itaú", 5)
    session.commit()
    with pytest.raises(ValueError):
        criar(session, "ITAU", 10)


def test_cartao_com_parcelamento_nao_pode_ser_excluido(session):
    cartao = criar(session, "Nubank", 5)
    session.commit()
    create_plan(session, "TV", "cartao", "Nubank", 10000, 3, 1, "2026-11", 5, "")
    session.commit()
    with pytest.raises(ValueError):
        excluir(session, cartao)


def test_cartao_sem_vinculos_pode_ser_excluido(session):
    cartao = criar(session, "Teste", 5)
    session.commit()
    excluir(session, cartao)
    session.commit()
    assert listar(session) == []


def test_validar_novo_nao_grava_cartao(session):
    nome = validar_novo(session, "  Itaú  ", 5)
    assert nome == "Itaú"
    assert listar(session) == []

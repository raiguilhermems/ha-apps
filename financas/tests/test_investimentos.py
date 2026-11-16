from datetime import date

import pytest
from sqlmodel import select

from app.models import InvestimentoHistorico
from app.services.investimentos import (
    atualizar_valor,
    criar,
    evolucao_total,
    excluir,
    historico_com_variacao,
    listar,
    total,
)


def test_criar_grava_valor_e_historico(session):
    inv = criar(session, "Tesouro Selic", "renda_fixa", 100000, date(2026, 11, 1))
    session.commit()
    assert inv.valor_cents == 100000
    hist = session.exec(select(InvestimentoHistorico)).all()
    assert len(hist) == 1
    assert hist[0].data == date(2026, 11, 1)


def test_atualizar_valor_muda_atual_e_acumula_historico(session):
    inv = criar(session, "CDB", "renda_fixa", 100000, date(2026, 10, 1))
    atualizar_valor(session, inv, 105000, date(2026, 11, 1))
    session.commit()
    assert inv.valor_cents == 105000
    assert inv.atualizado_em == date(2026, 11, 1)
    assert [h["variacao"] for h in historico_com_variacao(session, inv.id)] == [None, 5000]


def test_data_retroativa_nao_muda_valor_atual(session):
    inv = criar(session, "Fundo", "fundos", 50000, date(2026, 11, 1))
    atualizar_valor(session, inv, 40000, date(2026, 10, 1))
    session.commit()
    assert inv.valor_cents == 50000
    assert inv.atualizado_em == date(2026, 11, 1)


def test_evolucao_total_soma_as_caixinhas(session):
    a = criar(session, "A", "outro", 100000, date(2026, 10, 1))
    criar(session, "B", "outro", 200000, date(2026, 10, 1))
    atualizar_valor(session, a, 150000, date(2026, 11, 1))
    session.commit()
    grafico = evolucao_total(session)
    assert grafico["labels"] == ["01/10/2026", "01/11/2026"]
    assert grafico["valores"] == [3000.0, 3500.0]
    assert total(session) == 350000


def test_excluir_apaga_caixinha_e_historico(session):
    inv = criar(session, "X", "outro", 1000, date(2026, 11, 1))
    atualizar_valor(session, inv, 2000, date(2026, 11, 2))
    session.commit()
    excluir(session, inv)
    session.commit()
    assert listar(session) == []
    assert session.exec(select(InvestimentoHistorico)).all() == []


def test_nome_vazio_e_valor_negativo_sao_rejeitados(session):
    with pytest.raises(ValueError):
        criar(session, "   ", "outro", 1000)
    with pytest.raises(ValueError):
        criar(session, "Y", "outro", -1)

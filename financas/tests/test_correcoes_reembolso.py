"""Correções da revisão: remover compra não a devolve como nova, renomear pessoa atualiza a fatura,
e a migração de faturas antigas para o modelo de reembolso."""

from datetime import date

from sqlmodel import select

from app.db import _backfill
from app.models import Account, FaturaCartao, FaturaItem, Tag, Transaction
from app.services.cartoes import criar, excluir_item, lancar_fatura
from app.services.fatura_nubank import ler_fatura_completa
from app.services.importacao import gravar, montar_previa
from app.services.parcelados import renomear_pessoa

VENC = date(2026, 11, 5)
CSV = (
    "date,title,amount\n"
    '2026-11-02,Mercado Teste,"100,00"\n'
    '2026-11-03,Farmacia Teste,"50,00"\n'
).encode()


def _itens(previa, marcar):
    itens = []
    for n, p in enumerate(previa):
        terceiro, pessoa = marcar.get(n, (False, ""))
        itens.append(
            {
                "linha": p["linha"],
                "status": p["status"],
                "incluir": p["incluir"],
                "terceiro": terceiro,
                "pessoa": pessoa,
                "atualizar": False,
                "nome": p["linha"].nome,
                "categorias": "",
                "plano_id": p["plano_id"],
            }
        )
    return itens


def _importar(session, marcar):
    criar(session, "Nubank", 5, 25)
    session.commit()
    previa = montar_previa(session, ler_fatura_completa(CSV), "Nubank")
    gravar(session, "Nubank", VENC, _itens(previa, marcar), total_cents=15000)
    session.commit()


def test_remover_compra_avista_nao_volta_como_nova(session):
    _importar(session, {})
    cartao = session.exec(select(Account)).one()
    fatura = session.exec(select(FaturaCartao)).one()
    farmacia = session.exec(select(FaturaItem).where(FaturaItem.descricao == "Farmacia Teste")).one()
    excluir_item(session, cartao, fatura, farmacia.id)
    session.commit()

    nova = montar_previa(session, ler_fatura_completa(CSV), "Nubank")
    assert [p["status"] for p in nova] == ["registrada", "ignorada"]


def test_renomear_pessoa_atualiza_fatura_sem_duplicar_reembolso(session):
    _importar(session, {0: (True, "Ana")})
    tag = session.exec(select(Tag).where(Tag.name == "ana")).one()

    renomear_pessoa(session, tag, "Ana Maria")
    session.commit()

    item = session.exec(select(FaturaItem).where(FaturaItem.destino == "terceiro")).one()
    assert item.pessoa == tag.name
    reembolsos = session.exec(
        select(Transaction).where(Transaction.reembolso.is_(True), Transaction.fatura_id.is_not(None))
    ).all()
    assert len(reembolsos) == 1
    assert reembolsos[0].description.startswith("Ana Maria · Fatura Nubank")

    # Lançar a fatura de novo com o mesmo total não pode criar outro reembolso
    cartao = session.exec(select(Account)).one()
    lancar_fatura(session, cartao, "2026-11", 15000, 0, "")
    session.commit()
    reembolsos = session.exec(
        select(Transaction).where(Transaction.reembolso.is_(True), Transaction.fatura_id.is_not(None))
    ).all()
    assert len(reembolsos) == 1  # a compra importada da Ana continua na fatura


def test_backfill_converte_fatura_antiga_e_e_idempotente(session):
    cartao = Account(name="Nubank", type="cartao", dia_pagamento=5, dia_fechamento=25)
    session.add(cartao)
    session.flush()
    despesa = Transaction(
        description="Fatura Nubank · nov/2026", amount_cents=70000, due_date=VENC, kind="despesa", status="pendente"
    )
    receita = Transaction(
        description="Pago por Ana · Fatura Nubank", amount_cents=30000, due_date=VENC, kind="receita", status="pendente"
    )
    session.add_all([despesa, receita])
    session.flush()
    session.add(
        FaturaCartao(
            account_id=cartao.id,
            referencia="2026-11",
            total_cents=100000,
            terceiro_cents=30000,
            pessoa="ana",
            tx_despesa_id=despesa.id,
            tx_receita_id=receita.id,
        )
    )
    session.commit()

    _backfill()
    session.expire_all()
    fatura = session.exec(select(FaturaCartao)).one()
    receita = session.get(Transaction, receita.id)
    assert receita.reembolso is True
    assert receita.fatura_id == fatura.id
    assert fatura.liquido_cents == 70000
    itens = session.exec(select(FaturaItem)).all()
    assert [(i.kind, i.destino, i.valor_cents) for i in itens] == [("manual", "terceiro", 30000)]

    _backfill()  # rodar de novo não duplica nada
    session.expire_all()
    assert len(session.exec(select(FaturaItem)).all()) == 1


def test_editar_parcelado_pela_fatura_muda_o_plano(session):
    from app.models import InstallmentPlan
    from app.services.cartoes import editar_item, garantir_fatura
    from app.services.parcelados import create_plan

    cartao = criar(session, "Nubank", 5, 25)
    session.commit()
    plano = create_plan(session, "TV", "cartao", "Nubank", 10000, 3, 1, "2026-11", 5)
    fatura = garantir_fatura(session, cartao, "2026-11", 50000)
    item = FaturaItem(
        fatura_id=fatura.id,
        kind="parcelado",
        descricao="TV",
        valor_cents=10000,
        destino="sua",
        plan_id=plano.id,
        data_compra=date(2026, 11, 2),
        nome_original="TV - Parcela 1/3",
    )
    session.add(item)
    session.commit()

    editar_item(session, cartao, fatura, item.id, "TV nova", "terceiro", "Ana", "casa")
    session.commit()

    plano = session.get(InstallmentPlan, plano.id)
    assert plano.tipo == "receber"
    assert plano.pessoa == "Ana"
    assert plano.description == "TV nova"
    assert fatura.liquido_cents == 40000  # 50000 menos a parcela de terceiro


def test_parcelado_de_terceiro_nao_volta_a_ser_seu_pela_fatura(session):
    import pytest

    from app.services.cartoes import editar_item, garantir_fatura
    from app.services.parcelados import create_plan

    cartao = criar(session, "Nubank", 5, 25)
    session.commit()
    plano = create_plan(
        session, "Presente", "a_receber", "", 10000, 3, 1, "2026-11", 5,
        tipo="receber", pessoa="Ana",
    )
    fatura = garantir_fatura(session, cartao, "2026-11", 50000)
    item = FaturaItem(
        fatura_id=fatura.id, kind="parcelado", descricao="Presente", valor_cents=10000,
        destino="terceiro", pessoa="Ana", plan_id=plano.id,
        data_compra=date(2026, 11, 2), nome_original="Presente - Parcela 1/3",
    )
    session.add(item)
    session.commit()

    with pytest.raises(ValueError, match="de terceiro"):
        editar_item(session, cartao, fatura, item.id, "Presente", "sua", "", "")

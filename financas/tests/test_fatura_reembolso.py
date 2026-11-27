"""Importação da fatura no modelo de reembolso: à vista, parcelado de terceiro, duplicados e histórico."""

from datetime import date

from sqlmodel import select

from app.models import Account, FaturaCartao, FaturaItem, ImportacaoIgnorada, Transaction
from app.services.cartoes import criar, editar_item, excluir_item
from app.services.fatura_nubank import ler_fatura_completa
from app.services.importacao import diferenca_total, gravar, montar_previa
from app.services.summary import monthly_summary

VENC = date(2026, 11, 5)
CSV = (
    "date,title,amount\n"
    '2026-11-02,Mercado Teste,"100,00"\n'
    '2026-11-03,Farmacia Teste,"50,00"\n'
).encode()


def _cartao(session):
    criar(session, "Nubank", 5, 25)
    session.commit()


def _itens(previa, marcar):
    """marcar: {indice: (terceiro, pessoa)}; ausentes ficam como estão na prévia."""
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


def _reembolsos(session):
    return session.exec(select(Transaction).where(Transaction.reembolso.is_(True), Transaction.fatura_id.is_not(None))).all()


def test_compra_avista_de_terceiro_vira_reembolso_no_vencimento(session):
    _cartao(session)
    previa = montar_previa(session, ler_fatura_completa(CSV), "Nubank")
    gravar(session, "Nubank", VENC, _itens(previa, {0: (True, "Ana")}), total_cents=15000)
    session.commit()

    fatura = session.exec(select(FaturaCartao)).one()
    assert fatura.total_cents == 15000
    assert fatura.terceiro_cents == 10000
    assert fatura.liquido_cents == 5000
    despesa = session.get(Transaction, fatura.tx_despesa_id)
    assert despesa.amount_cents == 5000  # só a sua parte entra no Início

    (reembolso,) = _reembolsos(session)
    assert reembolso.amount_cents == 10000
    assert reembolso.kind == "receita"
    assert reembolso.due_date == VENC
    assert len(session.exec(select(FaturaItem)).all()) == 2

    resumo = monthly_summary(session, "2026-11")
    assert resumo["receitas_total"] == 0
    assert resumo["despesas_total"] == 5000


def test_importar_de_novo_nao_duplica_nada(session):
    _cartao(session)
    previa = montar_previa(session, ler_fatura_completa(CSV), "Nubank")
    gravar(session, "Nubank", VENC, _itens(previa, {0: (True, "Ana")}), total_cents=15000)
    session.commit()

    segunda = montar_previa(session, ler_fatura_completa(CSV), "Nubank")
    assert [p["status"] for p in segunda] == ["registrada", "registrada"]
    gravar(session, "Nubank", VENC, _itens(segunda, {}), total_cents=15000)
    session.commit()
    assert len(session.exec(select(FaturaItem)).all()) == 2
    assert len(_reembolsos(session)) == 1


def test_compra_ignorada_fica_no_historico(session):
    _cartao(session)
    previa = montar_previa(session, ler_fatura_completa(CSV), "Nubank")
    itens = _itens(previa, {})
    itens[1]["incluir"] = False  # Farmácia fica de fora
    gravar(session, "Nubank", VENC, itens, total_cents=15000)
    session.commit()

    registro = session.exec(select(ImportacaoIgnorada)).one()
    assert registro.total == 0 and registro.valor_cents == 5000

    segunda = montar_previa(session, ler_fatura_completa(CSV), "Nubank")
    # Mercado foi gravada na primeira vez, então já está lançada; Farmácia segue ignorada
    assert [p["status"] for p in segunda] == ["registrada", "ignorada"]


def test_total_diferente_da_soma_do_csv_so_gera_aviso(session):
    _cartao(session)
    linhas = ler_fatura_completa(CSV)
    assert diferenca_total(linhas, 16000) == 1000  # soma do CSV é 15000
    previa = montar_previa(session, linhas, "Nubank")
    gravar(session, "Nubank", VENC, _itens(previa, {}), total_cents=16000)
    session.commit()
    assert session.exec(select(FaturaCartao)).one().total_cents == 16000


def test_compra_avista_sem_total_nao_grava(session):
    _cartao(session)
    previa = montar_previa(session, ler_fatura_completa(CSV), "Nubank")
    try:
        gravar(session, "Nubank", VENC, _itens(previa, {}), total_cents=None)
    except ValueError:
        pass
    else:
        raise AssertionError("deveria exigir o total da fatura")
    assert session.exec(select(FaturaItem)).all() == []


def test_parcelado_de_terceiro_sai_do_liquido_mas_segue_o_cronograma(session):
    _cartao(session)
    csv = (
        "date,title,amount\n"
        '2026-11-02,Loja Teste - Parcela 1/3,"300,00"\n'
    ).encode()
    previa = montar_previa(session, ler_fatura_completa(csv), "Nubank")
    gravar(session, "Nubank", VENC, _itens(previa, {0: (True, "João")}), total_cents=100000)
    session.commit()

    fatura = session.exec(select(FaturaCartao)).one()
    assert fatura.terceiro_cents == 30000
    assert session.get(Transaction, fatura.tx_despesa_id).amount_cents == 70000
    # Reembolso da parcela vem do plano a receber, não de um lançamento no vencimento da fatura
    assert [t for t in _reembolsos(session) if t.fatura_id == fatura.id] == []


def _tudo_sua(session):
    _cartao(session)
    previa = montar_previa(session, ler_fatura_completa(CSV), "Nubank")
    gravar(session, "Nubank", VENC, _itens(previa, {}), total_cents=15000)
    session.commit()
    return session.exec(select(Account).where(Account.type == "cartao")).one(), session.exec(select(FaturaCartao)).one()


def test_reembolso_tem_nome_cartao_e_mes(session):
    _cartao(session)
    previa = montar_previa(session, ler_fatura_completa(CSV), "Nubank")
    gravar(session, "Nubank", VENC, _itens(previa, {0: (True, "Ana")}), total_cents=15000)
    session.commit()
    (reembolso,) = _reembolsos(session)
    assert reembolso.description.startswith("Ana · Fatura Nubank · ")


def test_editar_compra_para_terceiro_cria_reembolso(session):
    cartao, fatura = _tudo_sua(session)
    item = session.exec(select(FaturaItem).where(FaturaItem.descricao == "Mercado Teste")).one()
    editar_item(session, cartao, fatura, item.id, "Mercado Teste", "terceiro", "Ana", "mercado")
    session.commit()
    assert fatura.liquido_cents == 5000
    assert session.get(Transaction, fatura.tx_despesa_id).amount_cents == 5000
    (reembolso,) = _reembolsos(session)
    assert reembolso.amount_cents == 10000


def test_remover_compra_de_terceiro_devolve_a_despesa_cheia(session):
    cartao, fatura = _tudo_sua(session)
    item = session.exec(select(FaturaItem).where(FaturaItem.descricao == "Mercado Teste")).one()
    editar_item(session, cartao, fatura, item.id, "Mercado Teste", "terceiro", "Ana", "")
    session.commit()
    excluir_item(session, cartao, fatura, item.id)
    session.commit()
    assert _reembolsos(session) == []
    assert session.get(Transaction, fatura.tx_despesa_id).amount_cents == 15000


def test_editar_reembolso_ja_recebido_e_bloqueado(session):
    cartao, fatura = _tudo_sua(session)
    item = session.exec(select(FaturaItem).where(FaturaItem.descricao == "Mercado Teste")).one()
    editar_item(session, cartao, fatura, item.id, "Mercado Teste", "terceiro", "Ana", "")
    session.commit()
    (reembolso,) = _reembolsos(session)
    reembolso.status = "pago"
    session.add(reembolso)
    session.commit()
    import pytest
    with pytest.raises(ValueError):
        excluir_item(session, cartao, fatura, item.id)


def test_parcelado_nao_se_edita_nesta_tela(session):
    cartao, fatura = _tudo_sua(session)
    item = session.exec(select(FaturaItem).where(FaturaItem.descricao == "Mercado Teste")).one()
    item.kind = "parcelado"
    session.add(item)
    session.commit()
    import pytest
    with pytest.raises(ValueError):
        editar_item(session, cartao, fatura, item.id, "x", "sua", "", "")


def test_aplicar_edicoes_muda_varias_compras_de_uma_vez(session):
    from app.services.cartoes import aplicar_edicoes

    cartao, fatura = _tudo_sua(session)
    itens = session.exec(select(FaturaItem).where(FaturaItem.fatura_id == fatura.id)).all()
    mercado = next(i for i in itens if i.descricao == "Mercado Teste")
    farmacia = next(i for i in itens if i.descricao == "Farmacia Teste")
    aplicar_edicoes(
        session,
        cartao,
        fatura,
        [
            {"id": mercado.id, "descricao": "Mercado Teste", "destino": "terceiro", "pessoa": "Ana", "categorias": "", "remover": False},
            {"id": farmacia.id, "descricao": "", "destino": "sua", "pessoa": "", "categorias": "", "remover": True},
        ],
    )
    session.commit()
    assert fatura.liquido_cents == 5000  # 15000 menos 10000 de terceiro
    assert session.exec(select(FaturaItem).where(FaturaItem.fatura_id == fatura.id)).all() == [session.get(FaturaItem, mercado.id)]

from datetime import date

import pytest
from sqlmodel import select

from app.models import ImportacaoIgnorada, InstallmentPlan, Tag, Transaction, TransactionTag
from app.services.fatura_nubank import ler_fatura
from app.services.importacao import gravar, montar_previa
from app.services.parcelados import create_plan, generate_installments, schedule_summaries, update_plan
from app.services.summary import monthly_summary
from app.services.util import current_month


def _csv_compra(n_parcela=3, total=10, valor="100,00"):
    return (
        "date,title,amount\n"
        f'2026-11-10,Loja Exemplo - Parcela {n_parcela}/{total},"{valor}"\n'
    ).encode()


def _itens(previa, terceiro=False, pessoa=""):
    return [
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
        for p in previa
    ]


def _vencimento():
    hoje = date.today()
    return date(hoje.year, hoje.month, 10)


def test_terceiro_vira_a_receber_sem_cartao(session):
    previa = montar_previa(session, ler_fatura(_csv_compra()), "Nubank")
    gravar(session, "Nubank", _vencimento(), _itens(previa, terceiro=True, pessoa="João"))

    plano = session.exec(select(InstallmentPlan)).one()
    assert plano.tipo == "receber"
    assert plano.pessoa == "João"
    assert plano.account_id is None
    assert plano.cartao_origem_id is not None
    assert plano.parcela_inicial == 3

    txs = session.exec(select(Transaction).where(Transaction.installment_plan_id == plano.id)).all()
    assert txs
    assert all(t.kind == "receita" and t.account_id is None for t in txs)


def test_reimportacao_nao_duplica_a_receber(session):
    linhas = ler_fatura(_csv_compra())
    previa = montar_previa(session, linhas, "Nubank")
    gravar(session, "Nubank", _vencimento(), _itens(previa, terceiro=True, pessoa="João"))

    previa2 = montar_previa(session, linhas, "Nubank")
    assert previa2[0]["status"] == "existente"
    assert len(session.exec(select(InstallmentPlan)).all()) == 1


def test_terceiro_sem_nome_nao_grava_nada(session):
    previa = montar_previa(session, ler_fatura(_csv_compra()), "Nubank")
    with pytest.raises(ValueError):
        gravar(session, "Nubank", _vencimento(), _itens(previa, terceiro=True, pessoa=""))
    assert session.exec(select(InstallmentPlan)).all() == []


def test_a_receber_nao_cria_parcelas_anteriores(session):
    plano = create_plan(
        session, "Notebook", "a_receber", "", 10000, 10, 3, current_month(), 10,
        tipo="receber", pessoa="Ana",
    )
    session.commit()
    generate_installments(session)

    txs = session.exec(select(Transaction).where(Transaction.installment_plan_id == plano.id)).all()
    assert sorted(t.installment_n for t in txs) == list(range(3, 11))

    resumo = schedule_summaries(session)["plans"][0]
    assert resumo["pagas"] == 2
    assert resumo["restantes"] == 8
    assert resumo["saldo"] == 8 * 10000


def test_saldo_a_pagar_e_a_receber_sao_separados(session):
    create_plan(session, "Notebook", "boleto", "", 15000, 10, 1, current_month(), 10)
    create_plan(
        session, "Loja", "a_receber", "", 10000, 3, 1, current_month(), 10,
        tipo="receber", pessoa="Ana",
    )
    session.commit()
    generate_installments(session)

    dados = schedule_summaries(session)
    assert dados["saldo_total"] == 10 * 15000
    assert dados["saldo_receber"] == 3 * 10000


def test_parcela_a_receber_nao_entra_como_receita(session):
    create_plan(
        session, "Loja", "a_receber", "", 10000, 3, 1, current_month(), 10,
        tipo="receber", pessoa="Ana",
    )
    session.commit()
    generate_installments(session)

    resumo = monthly_summary(session, current_month())
    # Parcela a receber de terceiro é reembolso: não entra em receitas (a despesa já é líquida)
    assert resumo["receitas"]["pendente"] == 0
    assert resumo["despesas"]["pendente"] == 0


def test_a_receber_cria_categoria_com_nome_da_pessoa(session):
    plano = create_plan(
        session, "Loja", "a_receber", "", 10000, 3, 1, current_month(), 10,
        "mercado", tipo="receber", pessoa="João Silva",
    )
    session.commit()
    generate_installments(session)

    tag = session.exec(select(Tag).where(Tag.name == "joão silva")).one()
    assert tag.excludes_from_total is False
    ligados = session.exec(select(TransactionTag).where(TransactionTag.tag_id == tag.id)).all()
    assert len(ligados) == 3
    assert "mercado" in plano.tags_text.split(", ")


def test_editar_a_receber_mantem_categoria_da_pessoa(session):
    plano = create_plan(
        session, "Loja", "a_receber", "", 10000, 3, 1, current_month(), 10,
        "", tipo="receber", pessoa="Ana",
    )
    session.commit()
    generate_installments(session)

    update_plan(session, plano, "Loja nova", 12000, 10, "lazer")
    session.commit()

    assert set(plano.tags_text.split(", ")) == {"lazer", "ana"}


def test_pessoa_vira_categoria_do_tipo_pessoa(session):
    create_plan(
        session, "Loja", "a_receber", "", 10000, 3, 1, current_month(), 10,
        tipo="receber", pessoa="Ana Lima",
    )
    session.commit()
    assert session.exec(select(Tag).where(Tag.name == "ana lima")).one().kind == "pessoa"


def test_categoria_existente_vira_pessoa(session):
    session.add(Tag(name="ana", kind="categoria"))
    session.commit()
    create_plan(
        session, "Loja", "a_receber", "", 10000, 3, 1, current_month(), 10,
        tipo="receber", pessoa="Ana",
    )
    session.commit()
    assert session.exec(select(Tag).where(Tag.name == "ana")).one().kind == "pessoa"


def test_marcar_existente_como_terceiro_converte_para_a_receber(session):
    linhas = ler_fatura(_csv_compra())
    gravar(session, "Nubank", _vencimento(), _itens(montar_previa(session, linhas, "Nubank")))

    previa = montar_previa(session, linhas, "Nubank")
    assert previa[0]["status"] == "existente"
    gravar(session, "Nubank", _vencimento(), _itens(previa, terceiro=True, pessoa="Ana"))

    plano = session.exec(select(InstallmentPlan)).one()
    assert plano.tipo == "receber"
    assert plano.account_id is None
    assert plano.pessoa == "Ana"
    assert session.exec(select(Transaction).where(Transaction.kind == "despesa")).all() == []
    receitas = session.exec(select(Transaction).where(Transaction.kind == "receita")).all()
    assert len(receitas) == 8


def test_ignorada_marcada_como_terceiro_vira_a_receber(session):
    linhas = ler_fatura(_csv_compra())
    itens = _itens(montar_previa(session, linhas, "Nubank"))
    itens[0]["incluir"] = False
    gravar(session, "Nubank", _vencimento(), itens)

    previa = montar_previa(session, linhas, "Nubank")
    assert previa[0]["status"] == "ignorada"
    itens = _itens(previa, terceiro=True, pessoa="Ana")
    itens[0]["incluir"] = True
    gravar(session, "Nubank", _vencimento(), itens)

    assert session.exec(select(InstallmentPlan)).one().tipo == "receber"
    assert session.exec(select(ImportacaoIgnorada)).all() == []

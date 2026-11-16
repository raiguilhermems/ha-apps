from datetime import date

from sqlmodel import select

from app.models import ImportacaoIgnorada, InstallmentPlan
from app.services.fatura_nubank import LinhaFatura, ler_fatura, limpa_nome, valor_para_centavos
from app.services.importacao import gravar, montar_previa
from app.services.parcelados import create_plan

VENCIMENTO = date(2026, 11, 10)

CSV = """date,title,amount
2026-11-12,Mercado Exemplo,"82,63"
2026-11-11,Loja Exemplo - Parcela 1/10,"62,09"
2026-11-10,Loja Teste - Parcela 1/3,"449,00"
2026-11-08,Restaurante Teste - Parcela 1/3,"93,20"
2026-11-10,Pagamento recebido,"-500,00"
2026-11-09,Estorno Loja - Parcela 2/3,"-30,00"
"""


def aceitar(previa):
    return [
        {
            "linha": p["linha"],
            "status": p["status"],
            "incluir": p["incluir"],
            "atualizar": False,
            "nome": limpa_nome(p["linha"].nome_original),
            "categorias": "",
            "plano_id": p["plano_id"],
        }
        for p in previa
    ]


def test_so_compras_parceladas_entram():
    linhas = ler_fatura(CSV.encode("utf-8"))
    assert [l.nome_original for l in linhas] == [
        "Loja Exemplo - Parcela 1/10",
        "Loja Teste - Parcela 1/3",
        "Restaurante Teste - Parcela 1/3",
    ]


def test_nome_limpo_e_valor_brasileiro():
    assert limpa_nome("Loja Exemplo - Parcela 1/10") == "Loja Exemplo"
    assert valor_para_centavos("1.234,56") == 123456
    assert valor_para_centavos("62,09") == 6209


def test_previa_nova_e_gravacao_cria_planos(session):
    linhas = ler_fatura(CSV.encode("utf-8"))
    previa = montar_previa(session, linhas, "Nubank")
    assert all(p["status"] == "nova" for p in previa)

    gravar(session, "Nubank", VENCIMENTO, aceitar(previa))

    planos = session.exec(select(InstallmentPlan)).all()
    assert len(planos) == 3
    assert {p.origem_csv for p in planos} == {
        "Loja Exemplo",
        "Loja Teste",
        "Restaurante Teste",
    }


def test_reimportacao_reconhece_compra_ja_cadastrada(session):
    linhas = ler_fatura(CSV.encode("utf-8"))
    gravar(session, "Nubank", VENCIMENTO, aceitar(montar_previa(session, linhas, "Nubank")))

    previa = montar_previa(session, linhas, "Nubank")
    assert all(p["status"] == "existente" for p in previa)
    assert all(p["incluir"] is False for p in previa)


def test_linha_excluida_fica_ignorada_na_proxima_importacao(session):
    linhas = ler_fatura(CSV.encode("utf-8"))
    itens = aceitar(montar_previa(session, linhas, "Nubank"))
    itens[0]["incluir"] = False
    gravar(session, "Nubank", VENCIMENTO, itens)

    assert len(session.exec(select(InstallmentPlan)).all()) == 2
    assert len(session.exec(select(ImportacaoIgnorada)).all()) == 1

    previa = montar_previa(session, linhas, "Nubank")
    assert previa[0]["status"] == "ignorada"
    assert previa[0]["incluir"] is False


def test_tolerancia_de_20_centavos(session):
    create_plan(session, "Restaurante Teste", "cartao", "Nubank", 9300, 3, 1, "2026-11", 10, "")
    session.commit()

    def linha(valor):
        return LinhaFatura(
            data=date(2026, 11, 8),
            nome_original="Restaurante Teste - Parcela 1/3",
            nome="Restaurante Teste",
            parcela=1,
            total=3,
            valor_cents=valor,
        )

    assert montar_previa(session, [linha(9320)], "Nubank")[0]["status"] == "existente"
    assert montar_previa(session, [linha(9340)], "Nubank")[0]["status"] == "nova"


def test_parcela_diferente_na_reimportacao_nao_duplica(session):
    novembro = ler_fatura('date,title,amount\n2026-09-27,Loja Exemplo - Parcela 1/10,"62,09"\n'.encode())
    gravar(session, "Nubank", VENCIMENTO, aceitar(montar_previa(session, novembro, "Nubank")))

    dezembro = ler_fatura('date,title,amount\n2026-10-28,Loja Exemplo - Parcela 2/10,"62,09"\n'.encode())
    previa = montar_previa(session, dezembro, "Nubank")
    assert previa[0]["status"] == "existente"

def test_ignorada_reconhecida_mesmo_com_data_de_fatura_diferente(session):
    novembro = ler_fatura('date,title,amount\n2026-09-27,Loja Exemplo - Parcela 1/10,"62,09"\n'.encode())
    itens = aceitar(montar_previa(session, novembro, "Nubank"))
    itens[0]["incluir"] = False
    gravar(session, "Nubank", VENCIMENTO, itens)

    dezembro = ler_fatura('date,title,amount\n2026-10-28,Loja Exemplo - Parcela 2/10,"62,09"\n'.encode())
    assert montar_previa(session, dezembro, "Nubank")[0]["status"] == "ignorada"
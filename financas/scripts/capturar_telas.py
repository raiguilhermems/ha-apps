"""Gera as capturas de tela do README, na pasta docs/ da raiz do repositório.

Passo a passo, a partir da pasta financas/ (em terminais separados quando indicado):

    # 1. banco de demonstração
    FINANCAS_DB=./demo.db uv run python scripts/seed_demo.py
    PYTHONPATH=. FINANCAS_DB=./demo.db uv run python scripts/seed_investimentos.py

    # 2. app rodando (deixe aberto)
    FINANCAS_DB=./demo.db uv run uvicorn app.main:app --port 8001

    # 3. capturas (outro terminal)
    uv run --with playwright python scripts/capturar_telas.py --chart /caminho/chart.umd.js

Na primeira vez, instale o Chromium do Playwright:
    uv run --with playwright playwright install chromium

O app carrega o Chart.js do CDN. O script troca esse endereço pelo arquivo --chart,
para a captura funcionar mesmo sem internet. Use o Chart.js 4.4.1, a mesma versão do app.

As capturas de importação gravam a fatura de novembro no banco de demonstração. Para
refazer as capturas, rode o seed de novo antes.

As capturas são de computador (1280 px de largura). Não há capturas de celular.
"""

import argparse
from datetime import date
from pathlib import Path

from playwright.sync_api import sync_playwright

PASTA_FINANCAS = Path(__file__).resolve().parents[1]
DOCS = PASTA_FINANCAS.parent / "docs"
CSV_DEMO = PASTA_FINANCAS / "scripts" / "demo"
CDN_CHART = "https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.js"
LARGURA, ALTURA = 1280, 900


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--chart", required=True, help="caminho do chart.umd.js (Chart.js 4.4.1)")
    parser.add_argument("--url", default="http://127.0.0.1:8001", help="endereço do app de demonstração")
    parser.add_argument("--mes", default=None, help="mês de referência AAAA-MM (padrão: o mês atual, como o seed)")
    args = parser.parse_args()

    base = args.url.rstrip("/")
    mes = args.mes or date.today().strftime("%Y-%m")
    chart = Path(args.chart).read_bytes()
    DOCS.mkdir(exist_ok=True)

    with sync_playwright() as p:
        navegador = p.chromium.launch()
        pagina = navegador.new_page(viewport={"width": LARGURA, "height": ALTURA})
        # Só o próprio app e o Chart.js local; qualquer outro endereço externo é bloqueado.
        # A última rota registrada é a primeira a rodar, por isso o Chart.js vem depois.
        pagina.route("**/*", lambda r: r.continue_() if r.request.url.startswith(base) else r.abort())
        pagina.route(CDN_CHART, lambda r: r.fulfill(body=chart, content_type="application/javascript"))

        def ir(caminho: str) -> None:
            pagina.goto(base + caminho)
            pagina.wait_for_load_state("networkidle")
            pagina.wait_for_timeout(400)  # o Chart.js anima ao desenhar

        def foto(nome: str) -> None:
            pagina.screenshot(path=str(DOCS / f"{nome}.png"), full_page=True)
            print("ok", nome)

        def link(caminho: str, seletor: str) -> str:
            ir(caminho)
            return pagina.locator(seletor).first.get_attribute("href")

        # telas principais
        ir(f"/?mes={mes}")
        foto("inicio")
        ir("/recorrentes")
        foto("recorrentes")
        ir("/parcelados")
        foto("parcelados")
        ir("/investimentos")
        foto("investimentos")
        ir("/categorias")
        foto("categorias")
        ir(f"/cartoes?mes={mes}")
        foto("cartoes")
        ir("/configuracoes")
        foto("configuracoes")

        # telas de detalhe e edição (o endereço de cada uma sai da própria lista)
        ir(link("/investimentos", "td.nome-caixinha a"))
        foto("investimento_detalhe")

        ir(link("/categorias", 'a[title="Ver lançamentos"]'))
        foto("categoria_detalhe")

        ir(link("/categorias", 'a[title="Editar"]'))
        foto("editar_categoria")

        ir(link(f"/?mes={mes}", 'a[href*="/lancamentos/"][href$="/editar"]'))
        foto("editar_lancamento")

        ir(link("/parcelados", 'a[href*="/parcelados/"][href$="/editar"]'))
        foto("editar_parcelado")

        ir(link("/recorrentes", 'a[href*="/recorrentes/"][href$="/editar"]'))
        foto("editar_recorrente")

        # importação da fatura: primeiro a tela vazia, depois a prévia de novembro e a de dezembro
        ir("/parcelados/importar")
        foto("importar")

        # total = soma das compras do CSV (sem pagamento e estorno), campo obrigatório na importação
        for nome, arquivo, mes_num, total in (
            ("importar1", "fatura_nov.csv", "11", "1.021,82"),
            ("importar2", "fatura_dez.csv", "12", "1.344,59"),
        ):
            ir("/parcelados/importar")
            pagina.set_input_files('input[name="arquivo"]', str(CSV_DEMO / arquivo))
            pagina.select_option('select[name="cartao_id"]', label="Nubank")
            pagina.select_option('select[name="mes_num"]', value=mes_num)
            pagina.select_option('select[name="ano"]', value="2026")
            pagina.fill('input[name="total"]', total)
            pagina.click('button:has-text("Ver prévia")')
            pagina.wait_for_load_state("networkidle")
            foto(nome)
            if nome == "importar1":
                pagina.click('button:has-text("Gravar importação")')
                pagina.wait_for_load_state("networkidle")

        navegador.close()
    print(f"Capturas salvas em {DOCS}")


if __name__ == "__main__":
    main()

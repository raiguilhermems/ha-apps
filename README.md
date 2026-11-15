# Finanças

Controle financeiro pessoal, autohospedado, rodando como add-on do Home Assistant. Acesso pelo painel lateral do Home Assistant (ingress), sem login próprio.

## Telas

![Início](docs/inicio.png)
![Parcelados](docs/parcelados.png)
![Recorrentes](docs/recorrentes.png)
![Configurações](docs/configuracoes.png)

## O que faz

- Lançamentos de receitas e despesas por mês, pela data de vencimento (regime de caixa).
- Saldo do mês em verde quando positivo e em vermelho quando negativo.
- Despesas com valor de terceiros: a parte que não é sua sai do total.
- Recorrentes: regras mensais que geram lançamentos nos próximos 12 meses. Podem ter valor fixo ou variável (estimativa, ajustada mês a mês).
- Vencimento padrão configurável, com a opção de 1º dia útil (segunda a sexta, sem feriados).
- Parcelados: boleto, carnê, financiamento ou cartão. Parcelas de cartão ficam só na aba Parcelados.
- Categorias, com filtro por mês. A categoria "terceiro" não entra no total.
- Projeção dos próximos meses: compromissos cadastrados mais a média dos gastos avulsos.
- Gráficos de receitas × despesas por mês e de parcelas por mês.
- Configurações: vencimento padrão, horizonte da projeção, backup, importação e apagar dados.

## Últimas versões

- **0.0.7**: categorias com botão Editar, vencimento padrão com 1º dia útil, saldo colorido e ajustes de alinhamento nas telas.
- **0.0.6**: ajuste visual para celular: campos de data, botões das tabelas e valores em R$ sem quebrar a linha.
- **0.0.5**: revisão dos textos das telas de categorias.
- **0.0.4**: tags renomeadas para categorias, com o endereço /categorias.
- **0.0.3**: nova aba de Configurações, com projeção, backup, importação e apagar dados.

Histórico completo em [CHANGELOG completo](financas/CHANGELOG.md).

## Instalação no Home Assistant

1. Vá em Configurações → Apps → Loja → menu ⋮ → Repositórios.
2. Adicione o endereço deste repositório.
3. Instale o Finanças, inicie e ative "Mostrar na barra lateral".

## Rodar localmente (desenvolvimento)

Requisitos: uv e Python 3.15 (ou outra versão compatível com as dependências).

    cd financas
    uv venv --python 3.15
    uv pip install -r requirements.txt
    FINANCAS_DB=./finance-dev.db uv run uvicorn app.main:app --reload

Abra http://127.0.0.1:8000 no navegador. O banco de teste fica em finance-dev.db, separado de qualquer banco real.

## Dados

O banco SQLite fica em /data/finance.db dentro do add-on e não é versionado. Antes de atualizar ou apagar qualquer coisa, baixe um backup pela aba Configurações.

## Estrutura

- financas/config.yaml: configuração do add-on (versão, ingress, ícone).
- financas/Dockerfile: imagem do add-on.
- financas/app/main.py: rotas da aplicação.
- financas/app/services/: regras de negócio (recorrentes, parcelados, projeção, resumo, gráficos e configurações).
- financas/app/templates/: telas em Jinja2.
- financas/CHANGELOG.md: histórico de versões.

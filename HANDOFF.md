# HANDOFF — Finanças (app de finanças pessoais para Home Assistant)

Use este arquivo para retomar o projeto em um novo chat. Estado em 21/11/2026 (0.0.22).

## 1. Arquitetura e stack

- **App:** FastAPI + SQLModel/SQLite + Jinja2 + Chart.js 4.4.1 (CDN jsDelivr). Tema escuro.
- **Execução:** add-on do Home Assistant com ingress (sem login próprio). Produção em Raspberry Pi 4 (HAOS). Desenvolvimento em Windows e Linux com `uv`.
- **Repositório:** `github.com/raiguilhermems/ha-apps`, app na pasta `financas/`. Dados em `/data/finance.db` dentro do add-on.
- **Dinheiro:** sempre em centavos (inteiro). Regime de caixa pela data de vencimento.
- **Routers (uma tela cada):** lancamentos (Início), parcelados, importacao, categorias, recorrentes, cartoes, investimentos, configuracoes.
- **Services:** parcelados, recurring, edit, summary, charts, tags, cartoes, fatura_nubank (leitor do CSV do Nubank), importacao, investimentos, settings, util.
- **Templates de categorias:** `tags.html` (seções Pessoas, Recorrentes e Categorias), `editar_categoria.html`, `tag_detalhe.html` (rota `/categorias/{id}`).
- **Migrações:** leves, via `NEW_COLUMNS` em `db.py`. Tabelas novas são criadas sozinhas pelo `create_all`.
- **Testes:** pytest (`uv run pytest -v`), com banco temporário. Arquivos: `test_seguranca.py`, `test_importacao.py`, `test_parcelados.py`, `test_a_receber.py`, `test_rotas.py`, `test_graficos.py`, entre outros.
- **Porta:** dev em 8000; banco demo em 8001.

## 2. Modelo de categorias (regras vigentes)

Cada nome de categoria é único no banco (`Tag.name` é UNIQUE). O campo `Tag.kind` diz o tipo:

- **categoria:** tipo comum, criado digitando o nome nos lançamentos.
- **pessoa:** quem deve ou deve a você. Agrupa tudo do mesmo nome (receitas a receber e despesas manuais).
- **recorrente:** criada automaticamente a partir de cada recorrência (receita ou despesa). Tem hiperlink e é renomeada junto com a recorrência.

Regras de nome:
- Nome repetido entre categoria, recorrente e pessoa é bloqueado. Não há subtipo com unicidade por tipo+nome.
- Categoria comum com nome de pessoa é promovida a pessoa (se não estiver em uso fora do total).
- Lançamento manual ou digitado (inclusive na importação e nos parcelados) com nome de recorrente é bloqueado, com mensagem e sem gravar nada. Ao editar um lançamento que veio da recorrência, o próprio nome não bloqueia.
- Duas recorrências com o mesmo nome também são bloqueadas.
- Renomear recorrente ou pessoa propaga para categorias, planos e lançamentos pendentes. O histórico segue o id da tag.
- Excluir uma recorrência transforma a categoria dela em categoria comum (mantém o histórico).
- Recorrentes antigas recebem categoria automaticamente em `generate_all` (backfill). Conflitos de nome ficam sem categoria e aparecem marcados como "sem categoria" na tela Recorrentes.
- Edição de recorrente de cartão e de categoria recorrente pela aba Categorias é bloqueada (400), com orientação para editar em Recorrentes.

## 3. Modelo de parcelados (regras vigentes)

- **Plano `pagar`** (padrão): compra de cartão, boleto, carnê, financiamento ou outro. Cada parcela vira despesa. Parcelas de cartão ficam só em Parcelados (já estão na fatura).
- **Plano `receber`** (0.0.20): compra feita no cartão para outra pessoa, que devolve o valor.
  - Campos: `tipo='receber'`, `pessoa`, `parcela_inicial`, `cartao_origem_id`, `account_id = NULL`, `payment_method='a_receber'`.
  - Cada parcela é **receita** sem conta de cartão, entra no mês do recebimento e fica fora da fatura.
  - O nome da pessoa vira **categoria do tipo pessoa** automaticamente.
  - O dia de recebimento padrão é o dia da fatura. Pode ser editado no plano.
- **Importação da fatura (prévia):** "de outra pessoa" aparece em todas as linhas, com campo "Quem paga" quando marcado.
  - Nova: cria o plano a receber.
  - Já cadastrada: converte o parcelado de cartão em a receber. Apaga as parcelas pendentes do cartão; as já pagas viram histórico sem vínculo.
  - Ignorada antes: cadastra como a receber e remove da lista de ignoradas.
  - Se alguma linha estiver marcada sem nome, nada é gravado.
  - Categorias digitadas na prévia são conferidas antes de gravar (nome de recorrente bloqueia, nada é gravado).
- **Tela Parcelados:** seção "A receber" primeiro, depois "A pagar". Cards: Saldo a pagar, Saldo a receber, Parcelamentos ativos.
- **Cadastro e edição de parcelamento:** categorias conferidas da mesma forma. No cadastro, o erro aparece como mensagem genérica até `parcelados.html` ganhar o código `categoria` (ver seção 5).

## 4. Início e gráficos (regras vigentes)

- **Cards do topo:** Receitas, Despesas, Saldo, Já pago e A pagar, só do mês de referência.
- **Gráfico Receitas × despesas por mês:** mostra X meses antes e Y meses depois do mês de referência. Padrão 6 antes e 3 depois. Configurável em Configurações (antes de 1 a 24, depois de 0 a 12).
  - Meses depois do mês atual aparecem em cor mais clara (barras "futuro").
  - O mês atual tem contorno.
- **Parcelas por mês** (gráfico da tela Parcelados): soma só as parcelas a pagar. As parcelas a receber ficam de fora.
- **Decidido e removido:** somatório dos últimos N meses e projeção dos próximos 3 meses no Início. A tela mostra só o mês de referência (decisão do usuário em 19/11/2026).

## 5. O que já está pronto e funcionando

- **Versão 0.0.20** (mesclada na principal). Testes OK.
- **Versão 0.0.21 (publicada na `main` com tag `v0.0.21`; testes OK):**
  - Categorias automáticas de recorrente e de pessoa, com trava de nomes e renomeação propagada (`app/services/tags.py`, `recurring.py`, `edit.py`, `parcelados.py`).
  - Backfill de recorrentes antigas em `generate_all`.
  - Checagem de categorias em importação e parcelados (`routers/importacao.py`, `routers/parcelados.py`).
  - Configuração de meses do gráfico em Configurações (`settings.py`, `configuracoes.py`, `configuracoes.html`), gráfico com futuro e mês atual (`charts.py`, `index.html`, `lancamentos.py`).
  - Correção do "Parcelas por mês" para somar só planos a pagar.
  - Gráfico da categoria com a mesma regra do Início (meses antes e depois configurados, futuros mais claros, mês atual com contorno), e cabeçalho "Últimos N meses" com a mesma configuração (`routers/categorias.py`, `services/charts.py`, `templates/tag_detalhe.html`).
  - Teste de rotas com `POST /configuracoes/grafico` incluído (`tests/test_rotas.py`).
  - `config.yaml` (0.0.21), `CHANGELOG.md`, `DOCS.md` e `README.md` atualizados.
  - Atenção: cria a coluna `recurring_rule.tag_id` (migração automática).
- **Versão 0.0.22 (visual e mensagens):** telas padronizadas (`_style.html`, `_macros.html`, `_chart.html`); ações das listas em ícones; erros de cadastro e edição em banner nas telas; confirmações de sucesso; capitalização (pessoa e recorrente em minúsculas, categoria como digitada); nome de categoria conferido com `reservar_categoria` ao criar; `ValueError` de parcelados, pessoa e lançamentos tratado como banner (sem 500); `tags_com_id_by_tx` e as categorias do plano e da recorrência trazem `kind`.
- Início com receitas e despesas separadas, status, atrasados e gráfico.
- Parcelados (pagar e receber), com edição e exclusão.
- Importação da fatura do Nubank (CSV): prévia, reconhecimento de compras já cadastradas e ignoradas, reimportação no mês seguinte, mensagem de resultado após gravar.
- Cadastro de cartões com dia de pagamento (fim de semana vai para o próximo dia útil). Cartão com vínculos não pode ser excluído.
- Recorrentes com verificação mensal, valor variável, categorias e receitas antes das despesas.
- Categorias com relatório mensal e tipo pessoa.
- Aba Investimentos: caixinhas, tipos, histórico, variação e gráficos. Sem vínculo externo.
- Configurações: backup, importação (com limite de 50 MB e validação), vencimento padrão, gráfico do Início e apagar dados.
- Scripts de demonstração: `seed_demo.py`, `seed_investimentos.py` e os CSV `fatura_nov.csv` e `fatura_dez.csv`.

## 6. Falta fazer

Ordem sugerida. Itens com (usuário) dependem de decisão ou ação sua.

1. ~~**Mensagem de categoria em parcelados**~~ feito na 0.0.22 (a mensagem real vem do servidor).
2. **Hiperlink da recorrente** no Início e em Recorrentes (a categoria já existe; falta o link visível).
3. **Tela de evolução mensal da recorrente:** ver salário, luz, gás ao longo dos meses (todos os meses ou um período).
4. **Compra parcelada como filtro:** o tipo "compra" com categoria própria, para filtrar uma compra parcelada como já se faz com pessoa.
5. **Selo "recorrente"** em `tag_detalhe.html`, como já existe para categoria e pessoa.
6. **Liberar nome de recorrente excluída** quando a categoria antiga não tiver lançamentos (hoje fica bloqueado).
7. **Fatura do cartão como total mensal** (não coberto).
8. **Filtros livres de categoria** (não coberto).
9. **Testes automatizados** do fluxo novo: sugerido `test_categorias_recorrente.py` e testes de `charts.py` para `antes`/`depois` e futuro/atual.
10. **Itens antigos da 0.0.20:**
   - `charts.py` já foi conferido nesta rodada (ver seção 5).
   - `editar_parcelado.html` (não recebido): confirmar que mostra "A receber" e não "Cartão".
   - Faixas verde e vermelha em parcelados usam cores inline. Conferir visualmente.
   - Validar a conversão de parcelado em a receber com uma fatura de teste antes de usar na real (ela apaga parcelas pendentes do cartão).
   - Planos a receber criados antes da categoria automática não têm a categoria da pessoa. Ajuste único, se quiser.
   - `tag_detalhe.html` usa `capitalize`: "João Silva" vira "João silva". Trocar por `title` muda outros nomes ("tv a cabo" vira "Tv A Cabo"). Decidir.
   - Renomear uma pessoa em Categorias já atualiza `installment_plan.pessoa` (feito nesta rodada).
   - Dia de recebimento padrão: hoje é o dia da fatura. Decidir se passa a usar o padrão de Configurações.
   - Recorrentes de cartão não aplicam o ajuste de fim de semana das faturas. Decidir.
   - Recorrentes já cadastradas com cartão mantêm o dia antigo até serem editadas.
   - Lacunas de teste: não há testes HTTP para os POSTs de cartões, importação e investimentos. Não há teste para `soma_categoria_periodo`.

## 7. Aguardando decisão do usuário

Sugestões feitas durante a conversa e ainda não escolhidas. Não implementar sem confirmação.

- **Total em aberto por pessoa** na tela da categoria (todos os meses, não só o mês em exibição).
- **Botão "quitar tudo"** para uma pessoa: marca as parcelas pendentes como recebidas.
- **Cobranças em atraso a receber:** hoje receita nunca fica atrasada, por decisão anterior. Pode valer contar as parcelas vencidas e não recebidas.

## 8. Deixado para depois

Combinado com o usuário: não fazer agora.

- **Recusadas:** patrimônio no Início (saldo mais caixinhas); meta por caixinha com barra de progresso.
- **Adiado:** avisos no Home Assistant.
- **Segurança (baixa prioridade):**
  - `panel_admin: false` em `config.yaml`. Se houver contas de convidados, mudar para `true`.
  - Sem CSRF nos formulários. Exige token em todos os formulários.
  - Dependências sem versão fixa e Chart.js sem SRI. Fixar versões em `requirements.txt` e adicionar `integrity` ao Chart.js.
  - Dados e backups em texto puro (informativo).
- **Nome e ícone do app:** não escolhidos. Sugestões: Lar Financeiro, Homeledger, Cofre Local. Ícone preferido: casa com barras (estilo HA).
- **Chart.js:** manter o CDN (o app só roda com internet no HA).

## 9. Método de trabalho

- Commit, push e tag: o assistente não tem acesso ao GitHub nesta conta. Quem faz é o usuário, no repositório local, direto na `main` (sem branch). Procedimento completo na seção 10.

- O assistente não acessa o disco do usuário nem o repositório. Por isso:
  - O usuário envia os arquivos **reais** do repositório, não o repomix (que remove comentários e pode trazer linhas repetidas por artefato).
  - O assistente aplica as alterações em cópias, por script com verificação de cada trecho, e devolve um zip com a estrutura `financas/...` contendo só os arquivos alterados. Versões do zip: v3 (routers), v4 e v5 (gráfico).
  - Arquivos apagados não vão no zip: são listados para o usuário apagar à mão.
- Para mudanças de frontend, preferir arquivos completos no zip. Trechos só quando forem poucos e claros.
- Ao reescrever um template, o assistente precisa do original. Não reescrever às cegas.
- Ao editar vários trechos de um mesmo arquivo em scripts, ler o arquivo de novo a cada substituição.
- Sem código longo em respostas de discussão.
- Commit e push só quando o usuário pedir. Trailer do commit: `Co-Authored-By: Claude Haiku 5.5 <noreply@anthropic.com>`, sem `Claude-Session` (regra definida pelo usuário neste HANDOFF).
- Conversa em português do Brasil.
- Ambiente sem instalação de pacotes: testes não podem ser rodados pelo assistente. Quem roda é o usuário.

## 10. Procedimento para subir uma nova versão

Sempre que o usuário pedir para subir uma nova versão, o assistente faz tudo abaixo, na ordem:

1. **Confirmar o número da versão** com o usuário. Padrão: próximo número de patch (0.0.21 → 0.0.22). Se a mudança for grande, perguntar se é versão menor.
2. **Pedir os arquivos reais** que vão mudar: `financas/config.yaml`, `financas/CHANGELOG.md`, `financas/README.md` (se mudar algo visível ao usuário), `financas/DOCS.md` (se mudar uso), e os arquivos de código alterados. Não usar repomix como base.
3. **Atualizar `config.yaml`:** campo `version` com o número novo.
4. **Atualizar `CHANGELOG.md`:** nova seção no topo, com número, data (dd/mm/aaaa) e lista curta do que mudou, em português, sem detalhes internos.
5. **Atualizar `README.md`** (reduzido) e `DOCS.md` só se o que o usuário vê ou faz mudou.
6. **Atualizar este HANDOFF:** mover os itens feitos da seção 5 para a versão nova, marcar a seção 6 e atualizar a data no topo.
7. **Gerar o zip** com todos os arquivos alterados (incluindo `config.yaml`, `CHANGELOG.md`, `README.md`, `DOCS.md` e `HANDOFF.md`), na estrutura `financas/...`, e enviar ao usuário.
8. **Testes:** o usuário roda `uv run pytest -v`. Só seguir para o commit se passarem.
9. **Commit, push e tag na `main`** (sem branch), feitos pelo usuário no computador:

```bash
git checkout main
git pull
git add financas/
git status            # confira a lista antes de commitar
git commit -m "Título curto (versão)

- item do que mudou
- item do que mudou

Co-Authored-By: Claude Haiku 5.5 <noreply@anthropic.com>"
git push origin main
git tag vX.Y.Z
git push origin vX.Y.Z
```

Regras do commit: mensagem com título e lista de mudanças, trailer `Co-Authored-By: Claude Haiku 5.5 <noreply@anthropic.com>`, sem `Claude-Session`. Se `git status` mostrar arquivos fora da lista da versão, parar e conferir antes de commitar.

O assistente não tem acesso ao GitHub nesta conta: não tenta commit, push ou tag. Entrega o zip e os comandos.

## 11. Como continuar

Peça ao novo chat para ler este HANDOFF. Para os itens da seção 6, pergunte ao usuário quais quer aplicar e peça os arquivos reais correspondentes. Não use o repomix como base.

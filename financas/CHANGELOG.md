# Changelog

## 2026.11.0 — 21/11/2026

- Novo nome: **FinHome**, com ícone próprio na loja de add-ons, na barra lateral e no topo de cada tela.
- Versionamento por data (ano.mês.número). A versão atual aparece na tela de Configurações.
- Atenção: o identificador do add-on mudou para `finhome`. Instale como um app novo. Antes de desinstalar a versão anterior, baixe o backup em Configurações, e depois importe-o no FinHome.

## 0.0.22 — 21/11/2026

- Telas padronizadas: títulos, navegação de mês, cores, botões e nomes de status iguais em todas as telas.
- Ações das listas com ícones do mesmo tamanho: marcar pago ou recebido, desfazer, pausar ou ativar, editar, excluir e atualizar. Ao passar o mouse, aparece o nome da ação.
- Erros de cadastro e de edição aparecem como aviso na própria tela, em vez de mensagem técnica.
- Confirmação ao criar, salvar ou excluir categorias, recorrentes, cartões e configurações.
- Pessoas e recorrentes aparecem em minúsculas. Categorias mantêm o nome como foi digitado.
- Não é mais possível criar uma categoria com o nome de uma pessoa ou recorrente já existente. O app avisa e não grava nada.
- Investimentos: lista mais compacta, com o botão Editar.
- Parcelados: a mensagem de categoria repetida agora mostra o motivo.

## 0.0.21

- Recorrentes viram categorias automaticamente, com link para ver a evolução mês a mês. Renomear a recorrente renomeia a categoria.
- Pessoas e recorrentes não podem ter o nome de outra categoria. Lançamentos digitados à mão e a importação da fatura também são conferidos.
- Renomear uma pessoa atualiza os planos a receber e os lançamentos pendentes.
- Excluir uma recorrente mantém a categoria dela no histórico, como categoria comum.
- Configurações: quantidade de meses antes e depois do mês de referência no gráfico (padrão 6 e 3). Vale para o Início e para as categorias.
- Gráficos: meses ainda não fechados aparecem em cor mais clara, e o mês atual tem contorno.
- Categorias: o rótulo de resumo segue a mesma configuração de meses.
- Parcelas por mês: soma só as parcelas a pagar; as parcelas a receber ficam de fora.
- Atenção: esta versão cria a coluna `recurring_rule.tag_id`. A migração é automática; não precisa recriar o banco.

## 0.0.20

- Parcelados: nova seção **A receber** para compras feitas no cartão para outra pessoa, que vai devolver o valor. Cada parcela recebida entra como receita no mês do recebimento, sem conta de cartão.
- Importação da fatura: a prévia tem a opção "de outra pessoa", com o nome de quem paga. Essas compras viram a receber, e não parcelado. Se alguma estiver sem nome, nada é gravado.
- Reimportar a fatura não duplica as compras de terceiros já cadastradas.
- Prévia: "de outra pessoa" aparece em todas as linhas. Marcar em uma compra já cadastrada converte o parcelado em a receber; em uma ignorada, cadastra como a receber.
- Categorias: a edição permite mudar o tipo entre categoria e pessoa. A tela de cada categoria mostra o selo do tipo.
- A receber: o nome da pessoa aparece só uma vez, como link.
- Categorias têm tipo: "categoria" ou "pessoa". Pessoas aparecem em uma lista própria na tela de Categorias.
- A prévia da importação sugere as pessoas já cadastradas (campo com sugestões).
- A receber: o nome da pessoa leva à categoria dela.
- A receber: o nome de quem paga vira categoria automaticamente nas parcelas. Na tela de Categorias, a pessoa mostra tudo que ela deve e já pagou. Editar o plano não remove essa categoria.
- Parcelados: os cards de saldo passam a ser "Saldo a pagar" e "Saldo a receber".
- Atenção: esta versão cria as colunas `installment_plan.tipo`, `pessoa`, `parcela_inicial` e `cartao_origem_id`. A migração é automática; não precisa recriar o banco.

## 0.0.19

- Segurança: o nome do cartão não entra mais no código JavaScript da confirmação de exclusão.
- Segurança: a importação de backup aceita arquivos de até 50 MB, confere se o arquivo é um banco deste app antes de substituir os dados e lê o arquivo por partes.
- Segurança: o caminho do ingress do Home Assistant é validado antes de ser usado em redirecionamentos.
- README reduzido e reorganizado.
- Novos testes para o prefixo do ingress e para a validação do backup.
- Sem mudança na estrutura do banco.

## 0.0.18

- Início: removida a projeção dos próximos meses.
- Configurações: removida a seção Projeção, que só controlava o horizonte da projeção.
- Botões com tamanho único em todas as telas. Ações em linha única nas tabelas.
- Parcelados e importação da fatura: rótulos "Mês ano da parcela atual" e "Mês ano da fatura".
- Recorrentes: receitas listadas antes das despesas, na tabela de regras e na verificação do mês.
- Recorrentes de cartão usam o dia de pagamento cadastrado no cartão, em vez do dia escolhido no formulário.
- Recorrentes: valor variável centralizado verticalmente.
- Categorias: rótulo acima do gráfico com a soma de receitas e despesas dos últimos 6 meses, até o mês em exibição.
- Investimentos: nome da caixinha sem quebra de linha; campo de valor atualizado e data mais compactos.
- Código: removidos imports e chaves duplicadas em categorias e no início.
- Sem mudança na estrutura do banco.

## 0.0.17

- Nova aba Investimentos: caixinhas com nome, tipo e valor atual, histórico de atualizações, gráfico de evolução do total e de cada caixinha. Sem vínculo com instituições.
- Parcelados mostra o resultado da importação da fatura (compras criadas e atualizadas).
- Script `scripts/seed_investimentos.py` gera caixinhas fictícias no banco demo.
- Tabelas: cabeçalhos centralizados em todas as telas; valores centralizados, exceto a coluna Descrição, que fica à esquerda.
- Início: removidas as cores verde e vermelha do texto da coluna Valor. As bordas coloridas à esquerda permanecem. Status com primeira letra maiúscula.
- Recorrentes: faixa colorida à esquerda das linhas (verde para receita, vermelho para despesa), igual ao Início.
- Botões de ações padronizados e espaçados igualmente em Início, Recorrentes e Categorias.
- Categorias: os três botões de ações ficam em uma única coluna, na mesma linha.
- Cartões: campo de dia de pagamento menor, com o botão Cadastrar na mesma linha.


## 0.0.16

- Nova aba Investimentos: caixinhas com nome, tipo e valor atual, histórico de atualizações, gráfico de evolução do total e de cada caixinha. Sem vínculo com instituições.
- Parcelados mostra o resultado da importação da fatura (compras criadas e atualizadas).
- README com o roteiro do banco demonstração e dos arquivos de fatura de teste.
- Script `scripts/seed_investimentos.py` gera caixinhas fictícias no banco demo.
## 0.0.15

- Importação da fatura do Nubank (CSV) na aba Parcelados, com prévia antes de gravar.
- Prévia marca compras já cadastradas e compras ignoradas em importações anteriores.
- Reimportar no mês seguinte não duplica as parcelas já cadastradas.
- Nova aba Cartões: cadastro com nome e dia de pagamento da fatura (fim de semana passa para o próximo dia útil).
- Parcelados e Recorrentes escolhem o cartão numa lista de cartões cadastrados.
- Mês da fatura escolhido em lista de mês e ano, já preenchido com o mês atual.
- Atenção: esta versão cria as colunas `account.dia_pagamento` e `installment_plan.origem_csv` e a tabela `importacao_ignorada`. Em instalações com dados antigos, apague o banco ou reinstale o add-on.
## 0.0.14

- Celular: a barra de abas ficou numa faixa só, com rolagem horizontal.
- Celular: o cabeçalho de cada grupo (Receitas e Despesas) e o nome do lançamento ficam em linha única.
- README atualizado, com descrição de cada tela e capturas novas.
- Script `scripts/seed_demo.py` para gerar um banco de demonstração com dados fictícios (uso de desenvolvimento).

## 0.0.13

- Início: lançamentos separados em receitas e despesas, com cabeçalho e total de cada grupo. Receitas em verde e despesas em vermelho.
- Início: as categorias de cada lançamento são links para a tela da categoria.
- Categorias: gráfico mensal de receitas e despesas da categoria, que acompanha o mês selecionado.
- Categorias: despesas em vermelho, no card e na tabela de lançamentos.
- Novo teste para o gráfico mensal da categoria.

## 0.0.12

- Removido o código de faturas que não era mais usado (modelos `Invoice` e `Valuation` e campos `invoice_id`, `purchase_date` e `is_recurring`).
- A projeção passa a identificar recorrentes pela regra de origem, sem mudar os valores exibidos.
- Mensagens de erro de categorias usam o nome "categoria".
- Novo teste para garantir que recorrentes entram na projeção como compromisso.
- **Atenção:** esta versão muda a estrutura do banco. Em instalações com dados, é preciso recriar o banco (desinstalar e instalar de novo o app, após baixar o backup).

## 0.0.11

- Código reorganizado em módulos por tela (`app/routers/`). Nenhuma tela ou URL mudou.
- Removido código legado de faturas e dívidas que não era mais usado.
- Adicionados testes automatizados (pytest) para cálculos, recorrentes, parcelados e rotas.

## 0.0.10
- Categorias aparecem como caixinhas clicáveis em Recorrentes e Parcelados, e abrem o detalhamento da categoria.
- Cartão aparece como caixinha na lista de recorrentes, no mesmo estilo do valor das parcelas.

## 0.0.9
- Parcelados podem ser editados: descrição, valor da parcela, dia do vencimento e categorias. As alterações valem para as parcelas pendentes; as pagas não mudam.
- Botão Editar na lista de parcelados.
- Formulários de parcelados passam a respeitar o endereço do Home Assistant.

## 0.0.8
- Recorrentes e parcelados aceitam categorias. Os lançamentos gerados já saem com elas.
- Editar uma recorrência atualiza as categorias dos lançamentos pendentes.
- Cadastro de parcelado com erro (por exemplo, cartão sem nome) mostra um aviso na tela, em vez de texto cru.

## 0.0.7
- Categorias: botão Editar em vez de salvar direto na lista, e página de edição própria.
- Configurações: vencimento padrão, com opção de 1º dia útil (segunda a sexta, sem feriados).
- Recorrentes e parcelados: campo de vencimento com lista de dias e 1º dia útil.
- Início: saldo verde quando positivo e vermelho quando negativo.
- Checkbox "Não soma no total" e "Valor variável" alinhados ao texto.
- Títulos "Ações" nas colunas de botões, e títulos e valores centralizados nas tabelas.
- Configurações: erros de confirmação e de arquivo voltam para a tela com aviso, em vez de mostrar texto cru.
- Links das telas de categoria passam a respeitar o endereço do Home Assistant.

## 0.0.6
- Ajuste visual para celular: campos de data e mês com largura correta, botões das tabelas na mesma linha e valores em R$ sem quebrar a linha.

## 0.0.5
- Textos das telas de categorias revisados: a palavra "tag" saiu de todas as telas.

## 0.0.4
- Tags renomeadas para Categorias nas telas. O endereço agora é /categorias, e o antigo /tags redireciona.

## 0.0.3
- Nova aba Configurações: projeção de 1 a 12 meses, backup (baixar e importar) e apagar dados com confirmação.

## 0.0.2
- Layout adaptado para celular: menu em duas linhas, tabelas com rolagem horizontal e cartões em duas colunas.

## 0.0.1
- Primeira versão no Home Assistant: lançamentos, recorrentes, parcelados, tags, projeção e gráficos.

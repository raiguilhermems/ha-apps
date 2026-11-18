# Finanças

Painel de finanças pessoais. Abra pela barra lateral do Home Assistant.

## Visão geral das telas

- **Início:** o mês em exibição. Mostra o resumo, a lista de lançamentos e o gráfico de receitas × despesas.
- **Parcelados:** compras parceladas, com o cronograma de cada uma e o saldo devedor.
- **Recorrentes:** regras mensais (aluguel, assinaturas, luz) que geram lançamentos automaticamente.
- **Categorias:** agrupam lançamentos (mercado, luz, lazer). Também servem para marcar o que não entra no total.
- **Cartões:** cadastro dos cartões com o dia de pagamento da fatura.
- **Investimentos:** caixinhas com valor atual e histórico, sem vínculo com bancos.
- **Configurações:** vencimento padrão, backup e apagar dados.

## Início

Use **Novo lançamento** para cadastrar uma receita ou despesa avulsa. Escolha a data de vencimento. No campo **Terceiros**, informe a parte que é de outra pessoa: ela sai do total e o restante fica como sua despesa. Use **Categorias** para agrupar, separando por vírgula.

Na lista do mês, o botão muda conforme o tipo:

- Despesa: **Marcar pago**. Enquanto não for paga e já passou do vencimento, aparece como **atrasado**.
- Receita: **Marcar recebido**. Receita nunca aparece como atrasada: ela fica como **a receber** até entrar.
- **Desfazer** volta o lançamento para pendente.

O símbolo ↻ indica um lançamento que veio de uma recorrência.

O saldo fica verde quando é positivo e vermelho quando é negativo.

Use as setas do topo para navegar entre os meses.

## Recorrentes

Cadastre contas que se repetem todo mês. Escolha o valor, o vencimento e se é despesa ou receita.

- **Valor fixo:** o mesmo valor em todos os meses. Exemplo: aluguel.
- **Valor variável** (marque a opção): o valor cadastrado é uma estimativa. Exemplo: luz ou água. Quando a conta chegar, ajuste o valor real no Início, no lançamento do mês. O ajuste vale só para aquele mês, e editar a recorrência depois não sobrescreve esse valor.

As regras geram os lançamentos automaticamente nos próximos 12 meses. Parar ou excluir uma regra apaga os lançamentos futuros que ainda estão pendentes. Os que já foram pagos continuam no histórico.

A tabela **Verificação do mês** mostra, para cada regra, se o lançamento do mês já foi criado e qual é a situação dele.

Regras vinculadas a cartão não aparecem no Início. O valor delas já está na fatura do cartão.

Quando você escolhe um cartão, o campo de vencimento some e a regra usa o dia de pagamento cadastrado no cartão.

## Parcelados

Cadastre a compra com a descrição, a forma de pagamento, o valor de cada parcela, o total de parcelas e em qual parcela você está.

- **Boleto, carnê, financiamento ou outro:** cada parcela entra automaticamente no Início, no mês de vencimento.
- **Cartão:** as parcelas ficam só nesta aba, porque já estão na fatura. Marque cada parcela como paga quando a fatura for paga.

O gráfico mostra quanto vence por mês nos próximos 12 meses. Parcelas anteriores ao mês do cadastro são consideradas pagas.

## Categorias

Crie categorias como mercado, luz ou lazer. Cada lançamento pode ter mais de uma.

- **Não soma no total:** marque para categorias que não devem entrar no total do mês, como a categoria "terceiro".
- **Ver lançamentos:** mostra tudo que tem aquela categoria no mês que está em exibição.
- **Resumo dos 6 meses:** o rótulo acima do gráfico soma receitas e despesas dos 6 meses terminando no mês em exibição.
- **Editar:** muda o nome ou a regra de soma.
- **Excluir:** remove a categoria dos lançamentos que a usavam. Os lançamentos continuam.

## Cartões

Cadastre cada cartão com o dia de pagamento da fatura. Se o dia cair em fim de semana, o vencimento passa para o próximo dia útil. Cartões com parcelamentos ou recorrentes vinculados não podem ser excluídos.

## Investimentos

Cadastre caixinhas com nome, tipo e valor atual. Ao atualizar o valor, o histórico guarda a data e a variação em relação ao registro anterior. O gráfico mostra a evolução do total. Os valores são digitados à mão.

## Configurações

- **Vencimento padrão:** valor sugerido nos formulários de recorrentes e parcelados. Escolha **1º dia útil** ou um dia do mês. O 1º dia útil considera segunda a sexta, sem feriados.
- **Baixar backup:** gera um arquivo com todos os dados. Use antes de atualizar o app ou apagar algo.
- **Importar backup:** substitui todos os dados atuais pelos do arquivo escolhido. Antes, o app guarda uma cópia do banco atual.
- **Apagar tudo:** apaga lançamentos, recorrentes, parcelados, categorias e cartões. Só executa se você digitar APAGAR exatamente como está. Não pode ser desfeito.

## Dicas

- Faça um backup antes de qualquer atualização importante.
- Cadastre primeiro as recorrentes e os parcelados. Depois, use o Início só para o que é avulso e para marcar o que foi pago.
- Se um valor mudar em um mês específico, ajuste só aquele lançamento no Início.

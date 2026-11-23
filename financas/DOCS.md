# FinHome

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

Na lista do mês, cada lançamento tem ícones de ação. Passe o mouse sobre um ícone para ver o nome da ação. O ícone de estado muda conforme o tipo:

- Despesa: ícone de check, **Marcar pago**. Enquanto não for paga e já passou do vencimento, aparece como **atrasado**.
- Receita: ícone de check, **Marcar recebido**. Receita nunca aparece como atrasada: ela fica como **a receber** até entrar.
- **Desfazer** (seta para trás) volta o lançamento para pendente.
- **Editar** (lápis) e **Excluir** (lixeira) ficam ao lado de cada lançamento.

O símbolo ↻ indica um lançamento que veio de uma recorrência.

O saldo fica verde quando é positivo e vermelho quando é negativo.

Use as setas do topo para navegar entre os meses.

O gráfico mostra os meses antes e depois do mês em exibição, conforme a configuração em **Configurações**. Meses ainda não fechados aparecem em cor mais clara, e o mês atual tem contorno.

## Recorrentes

Cadastre contas que se repetem todo mês. Escolha o valor, o vencimento e se é despesa ou receita.

- **Valor fixo:** o mesmo valor em todos os meses. Exemplo: aluguel.
- **Valor variável** (marque a opção): o valor cadastrado é uma estimativa. Exemplo: luz ou água. Quando a conta chegar, ajuste o valor real no Início, no lançamento do mês. O ajuste vale só para aquele mês, e editar a recorrência depois não sobrescreve esse valor.

As regras geram os lançamentos automaticamente nos próximos 12 meses. Parar ou excluir uma regra apaga os lançamentos futuros que ainda estão pendentes. Os que já foram pagos continuam no histórico.

A tabela **Verificação do mês** mostra, para cada regra, se o lançamento do mês já foi criado e qual é a situação dele.

Regras vinculadas a cartão não aparecem no Início. O valor delas já está na fatura do cartão.

Quando você escolhe um cartão, o campo de vencimento some e a regra usa o dia de pagamento cadastrado no cartão. Se esse dia cair em fim de semana, o lançamento vai para o próximo dia útil, como na fatura.

Cada recorrente vira uma categoria com o mesmo nome. Ela aparece em **Categorias** e tem link para ver a evolução mês a mês. Renomear a recorrente também renomeia a categoria. O nome de uma recorrente não pode ser usado em outra categoria, pessoa ou lançamento digitado à mão. Se a recorrente for excluída, a categoria continua no histórico como categoria comum.

## Parcelados

Cadastre a compra com a descrição, a forma de pagamento, o valor de cada parcela, o total de parcelas e em qual parcela você está.

- **Boleto, carnê, financiamento ou outro:** cada parcela entra automaticamente no Início, no mês de vencimento.
- **Cartão:** as parcelas ficam só nesta aba, porque já estão na fatura. Marque cada parcela como paga quando a fatura for paga.

O gráfico mostra quanto vence por mês nos próximos 12 meses, sem contar as parcelas a receber. Parcelas anteriores ao mês do cadastro são consideradas pagas.

**Desconto por antecipação:** nas compras a pagar, a tela mostra quanto você economizaria se quitasse hoje as parcelas dos meses seguintes. É uma estimativa: usa a taxa anual de **Configurações** (padrão 10,58% ao ano, efetiva) e a data de hoje. A parcela do mês atual não entra, porque já está em aberto. Bancos podem calcular de outro jeito.

### Compras de terceiros (a receber)

Quando você compra no cartão para outra pessoa, que vai devolver o valor, marque a compra como **de outra pessoa** na prévia da importação da fatura e informe quem vai pagar. Essa compra não vira parcelado: ela aparece em **Parcelados → A receber**. Cada parcela entra como receita no mês do recebimento, e o botão **Marcar recebido** registra o pagamento. O dia de recebimento padrão é o dia da fatura; é possível ajustá-lo em **Editar**.

## Categorias

Crie categorias como mercado, luz ou lazer. Cada lançamento pode ter mais de uma. Pessoas aparecem com a primeira letra maiúscula; categorias e recorrentes aparecem em minúsculas.

- **Não soma no total:** marque para categorias que não devem entrar no total do mês, como a categoria "terceiro".
- **Ver lançamentos:** mostra tudo que tem aquela categoria no mês que está em exibição.
- **Resumo dos meses:** o rótulo acima do gráfico soma receitas e despesas dos meses configurados (padrão 6), terminando no mês em exibição. O gráfico segue a mesma configuração.
- **Editar:** muda o nome ou a regra de soma.
- **Excluir:** remove a categoria dos lançamentos que a usavam. Os lançamentos continuam.

## Cartões

Cadastre cada cartão com o dia de pagamento da fatura. Se o dia cair em fim de semana, o vencimento passa para o próximo dia útil. Cartões com parcelamentos ou recorrentes vinculados não podem ser excluídos.

## Investimentos

Cadastre caixinhas com nome, tipo e valor atual. Ao atualizar o valor, o histórico guarda a data e a variação em relação ao registro anterior. O gráfico mostra a evolução do total. Os valores são digitados à mão.

## Configurações

- **Gráfico do Início:** quantos meses aparecem antes (1 a 24, padrão 6) e depois (0 a 12, padrão 3) do mês em exibição. Vale também para o gráfico das categorias.
- **Taxa de desconto:** taxa anual (efetiva) usada para estimar o desconto ao antecipar parcelas. Padrão 10,58% ao ano. Aceita valores de 0 a 100.
- **Vencimento padrão:** valor sugerido nos formulários de recorrentes e parcelados. Escolha **1º dia útil** ou um dia do mês. O 1º dia útil considera segunda a sexta, sem feriados.
- **Baixar backup:** gera um arquivo com todos os dados. Use antes de atualizar o app ou apagar algo.
- **Importar backup:** substitui todos os dados atuais pelos do arquivo escolhido. Antes, o app guarda uma cópia do banco atual.
- **Apagar tudo:** apaga lançamentos, recorrentes, parcelados, categorias e cartões. Só executa se você digitar APAGAR exatamente como está. Não pode ser desfeito.

## Dicas

- Faça um backup antes de qualquer atualização importante.
- Cadastre primeiro as recorrentes e os parcelados. Depois, use o Início só para o que é avulso e para marcar o que foi pago.
- Se um valor mudar em um mês específico, ajuste só aquele lançamento no Início.

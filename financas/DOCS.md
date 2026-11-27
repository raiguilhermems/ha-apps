# FinHome

Painel de finanças pessoais. Abra pela barra lateral do Home Assistant.

## Visão geral das telas

- **Início:** o mês em exibição. Mostra o resumo, a lista de lançamentos e o gráfico de receitas × despesas.
- **Parcelados:** compras parceladas, com o cronograma de cada uma e o saldo devedor.
- **Recorrentes:** regras mensais (aluguel, assinaturas, luz) que geram lançamentos automaticamente.
- **Categorias:** agrupam lançamentos (mercado, luz, lazer) e mostram o que cada pessoa deve.
- **Cartões:** cadastro dos cartões (vencimento e fechamento da fatura) e o lançamento da fatura de cada mês.
- **Investimentos:** caixinhas com valor atual e histórico, sem vínculo com bancos.
- **Configurações:** vencimento padrão, backup e apagar dados.

## Início

Use **Novo lançamento** para cadastrar uma receita ou despesa avulsa. Escolha a data de vencimento e, se quiser, as categorias, separadas por vírgula.

Não há campo de terceiros aqui. Valores de terceiros entram pela fatura do cartão (tela **Cartões**) ou por **Parcelados → A receber**. Veja a seção **Como evitar duplicados**.

Na lista do mês, cada lançamento tem ícones de ação. Passe o mouse sobre um ícone para ver o nome da ação. O ícone de estado muda conforme o tipo:

- Despesa: ícone de check, **Marcar pago**. Enquanto não for paga e já passou do vencimento, aparece como **atrasado**.
- Receita: ícone de check, **Marcar recebido**. Receita nunca aparece como atrasada: ela fica como **a receber** até entrar.
- **Desfazer** (seta para trás) volta o lançamento para pendente.
- **Editar** (lápis) e **Excluir** (lixeira) ficam ao lado de cada lançamento.

Lançamentos com a etiqueta **fatura** são a despesa de um cartão, e a etiqueta **reembolso** marca o que uma pessoa vai te devolver. Eles são criados pela tela Cartões, por isso não têm Editar nem Excluir aqui. Para mudá-los, use Cartões. Reembolsos não entram nas receitas do mês. Marcar a despesa da fatura como paga, no Início, também quita as parcelas do cartão daquele mês.

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

Recorrências de cartão não aparecem no Início. O valor delas entra na fatura do cartão, e elas são quitadas quando você marca a fatura como paga.

Quando você escolhe um cartão, o campo de vencimento some e a regra usa o dia de vencimento cadastrado no cartão. Se esse dia cair em fim de semana, o lançamento vai para o próximo dia útil, como na fatura.

Cada recorrente vira uma categoria com o mesmo nome. Ela aparece em **Categorias** e tem link para ver a evolução mês a mês. Renomear a recorrente também renomeia a categoria. O nome de uma recorrente não pode ser usado em outra categoria, pessoa ou lançamento digitado à mão. Se a recorrente for excluída, a categoria continua no histórico como categoria comum.

## Parcelados

Cadastre a compra com a descrição, a forma de pagamento, o valor de cada parcela, o total de parcelas e em qual parcela você está.

- **Boleto, carnê, financiamento ou outro:** cada parcela entra automaticamente no Início, no mês de vencimento.
- **Cartão:** as parcelas ficam só nesta aba e na fatura do cartão. Não lance essas parcelas também no Início. Elas são marcadas como pagas quando você marca a fatura como paga, em **Cartões** ou no Início. Também é possível marcar cada parcela aqui.

O gráfico mostra quanto vence por mês nos próximos 12 meses, sem contar as parcelas a receber. Parcelas anteriores ao mês do cadastro são consideradas pagas.

**Desconto por antecipação:** só nas compras no cartão, nas compras a pagar, a tela mostra quanto você economizaria se quitasse hoje as parcelas dos meses seguintes. É uma estimativa: usa a taxa anual de **Configurações** (padrão 10,58% ao ano, efetiva) e a data de hoje. A parcela do mês atual não entra, porque já está em aberto. Em compras no cartão, a parcela que cai na fatura ainda aberta também não entra, porque ela é paga pela fatura atual. Bancos podem calcular de outro jeito.

### Compras de terceiros (a receber)

Quando você compra no cartão para outra pessoa, que vai devolver o valor, marque a compra como **de outra pessoa** na prévia da importação da fatura e informe quem vai pagar. Essa compra não vira parcelado de cartão: ela aparece em **Parcelados → A receber**. Cada parcela entra como reembolso no mês do recebimento: não conta como receita, e o botão **Marcar recebido** registra o pagamento. O dia de recebimento padrão é o dia da fatura; é possível ajustá-lo em **Editar**.

A compra continua na fatura, porque ela está no cartão. A parte de terceiro sai da despesa da fatura. Por isso, não informe o mesmo valor também no campo **Pago por terceiro, à mão**: ele seria descontado duas vezes.

## Categorias

Crie categorias como mercado, luz ou lazer. Cada lançamento pode ter mais de uma. Pessoas aparecem com a primeira letra maiúscula; categorias e recorrentes aparecem em minúsculas.

- **Não soma no total:** marque para categorias que não devem entrar no total do mês. Lançamentos com a categoria **terceiro** ficam fora do total inteiro. Use essa categoria ou o pago por terceiro da fatura para o mesmo valor, nunca os dois.
- **Ver lançamentos:** mostra tudo que tem aquela categoria no mês que está em exibição.
- **Resumo dos meses:** o rótulo acima do gráfico soma receitas e despesas dos meses configurados (padrão 6), terminando no mês em exibição. O gráfico segue a mesma configuração.
- **Editar:** muda o nome ou a regra de soma.
- **Excluir:** remove a categoria dos lançamentos que a usavam. Os lançamentos continuam.

Cada pessoa que deve ou paga algo vira uma categoria do tipo **pessoa**. Na tela de Categorias, ela mostra tudo o que deve a você. O pago por terceiro de uma fatura usa essa categoria automaticamente.

## Cartões

Cada cartão tem três informações:

- **Nome.**
- **Vencimento da fatura:** dia em que a fatura é paga. Se cair em fim de semana, vai para o próximo dia útil.
- **Fechamento da fatura:** dia em que a fatura fecha. A tela mostra se a fatura ainda está **em aberto** ou já está **fechada**.

Cartões criados automaticamente por uma parcela ou recorrência podem estar sem essas datas. Eles aparecem como **cadastro incompleto** até você preencher o vencimento e o fechamento.

### Lançar a fatura de um mês

1. Abra **Cartões** e escolha o mês com as setas.
2. Em **Total da fatura**, digite o valor total que veio na fatura. O total é digitado por você, não vem do CSV.
3. Se parte dela é de outra pessoa, que vai te devolver, use uma das duas formas (veja a seção **Como evitar duplicados**):
   - **Importação do CSV:** marque cada compra como "de outra pessoa", com o nome de quem paga.
   - **Valor à mão:** em **Pago por terceiro, à mão**, informe o valor e o nome. Só cabe um nome nesse campo.
4. Clique em **Lançar fatura**.

Ao salvar, o Início ganha:

- uma despesa **fatura** com a sua parte: total menos tudo o que é de terceiro, no vencimento;
- para cada pessoa que vai devolver, um **reembolso** (a receber), no mesmo vencimento, na categoria da pessoa.

A tela de Cartões mostra só a sua parte no Início. Para ver ou mudar o total, o valor à mão e as compras, use **Editar fatura**. O líquido fica guardado na fatura para o histórico.

No Início, os reembolsos formam um grupo próprio, em **laranja**, entre Receitas e Despesas, com o total "A receber (terceiros)" no resumo. Eles não entram no total de Receitas. Ele **não conta como receita**, nem no saldo nem no gráfico por categoria. A despesa da fatura já está descontada do que é de terceiro, então contar o reembolso de novo faria a conta errada. O reembolso só mostra o que falta receber. Quando a pessoa pagar, marque **Marcar recebido** no Início. Isso não muda o total do mês.

Para corrigir valores, use **Editar fatura** em Cartões. Não é preciso lançar nada à mão no Início.

### Pagar a fatura

Marque a fatura como paga em **Cartões** (botão **Marcar fatura paga**) ou no Início, no ícone de check da despesa **fatura**. Ao pagar, as parcelas e as recorrências do cartão com vencimento no mês também são marcadas como pagas. Parcelas de outros meses não mudam.

A tela mostra quantas parcelas e recorrências serão quitadas antes de você marcar.

- **Desfazer pagamento** volta só a despesa da fatura para pendente. As parcelas que já foram quitadas continuam pagas, porque podem ter sido pagas antes, de propósito. Ajuste-as em **Parcelados** se precisar.
- **Excluir fatura** remove a despesa, os reembolsos e as compras registradas. Não é possível se a despesa ou algum reembolso já estiver pago ou recebido. Desfaça antes.
- Os reembolsos são recebidos separadamente, no Início, com **Marcar recebido**.

### Importar a fatura do Nubank

Em **Parcelados → Importar fatura**, envie o CSV e digite o total da fatura. A prévia tem duas partes:

- **Parcelados:** cada compra parcelada. Entra como parcelado do cartão, ou a receber se marcar "de outra pessoa".
- **Compras à vista (vencimento):** compras de uma parcela só. Ficam registradas na fatura, para conferência e categorias (só registro). Marque "de outra pessoa" para gerar um reembolso no vencimento da fatura.

Pagamentos, estornos e créditos do CSV são ignorados. A prévia compara a soma do CSV com o total digitado. Se a diferença for grande, aparece um aviso. O aviso não impede a gravação: vale o total digitado.

Ao reimportar a mesma fatura, as compras já lançadas aparecem como "já lançada" e não são duplicadas. As compras que você desmarcou ficam como "ignorada antes" e não voltam como novas.

Para mudar uma compra já lançada, use **Editar compras**, na fatura de **Cartões**: você muda o nome, quem paga (sua ou de terceiro) e as categorias, ou remove a compra. O Início é recalculado. Compras parceladas também se editam em **Editar fatura**: nome, de quem é (terceiro) e categorias mudam no plano e nas parcelas ainda não pagas. Parcelado de terceiro não volta a ser seu por aqui; para isso, exclua-o em Parcelados. O valor de cada compra vem do CSV e não muda na edição: se estiver errado, exclua a fatura (se não estiver paga) e importe de novo. Uma compra à vista removida não volta como nova numa reimportação do mesmo CSV.

## Como evitar duplicados

Cada valor deve entrar em **um só lugar**. Antes de lançar, veja qual caso é o seu:

| Situação | Onde lançar | Não fazer |
| --- | --- | --- |
| Compra sua parcelada no cartão | Parcelados (cartão). Ela entra na fatura | Não lançar as parcelas no Início |
| Compra sua à vista no cartão | Dentro do total da fatura, em Cartões | Não lançar a compra no Início |
| Compra à vista de outra pessoa, que ela vai te devolver | Importação da fatura, marcando "de outra pessoa" (gera reembolso) | Não informar esse valor também em Pago por terceiro |
| Compra parcelada de outra pessoa, que ela vai te devolver | Importação da fatura, marcando "de outra pessoa" (Parcelados → A receber) | Não informar esse valor também em Pago por terceiro |
| Cartão usado por outra pessoa, sem o CSV detalhado | Pago por terceiro à mão, em Cartões, com o total que ela gasta | Não lançar esse valor também como receita avulsa |
| Conta fixa, como luz ou aluguel | Recorrentes | Não criar lançamento manual para o mesmo mês |
| Total da fatura do cartão | Cartões, em Lançar fatura | Não criar a fatura à mão no Início |

Não lance a mesma compra de terceiro duas vezes: uma vez na importação e outra à mão. Se o total de um mês não bater com a fatura, procure um valor lançado em dois lugares.

Valores antigos do campo **Terceiros** continuam guardados, mas não aparecem nem são descontados.

## Investimentos

Cadastre caixinhas com nome, tipo e valor atual. Ao atualizar o valor, o histórico guarda a data e a variação em relação ao registro anterior. O gráfico mostra a evolução do total. Os valores são digitados à mão.

## Configurações

- **Gráfico do Início:** quantos meses aparecem antes (1 a 24, padrão 6) e depois (0 a 12, padrão 3) do mês em exibição. Vale também para o gráfico das categorias.
- **Taxa de desconto:** taxa anual (efetiva) usada para estimar o desconto ao antecipar parcelas. Padrão 10,58% ao ano. Aceita valores de 0 a 100.
- **Vencimento padrão:** valor sugerido nos formulários de recorrentes e parcelados. Escolha **1º dia útil** ou um dia do mês. O 1º dia útil considera segunda a sexta, sem feriados.
- **Baixar backup:** gera um arquivo com todos os dados. Use antes de atualizar o app ou apagar algo.
- **Importar backup:** substitui todos os dados atuais pelos do arquivo escolhido. Antes, o app guarda uma cópia do banco atual.
- **Apagar tudo:** apaga lançamentos, recorrentes, parcelados, categorias, cartões e faturas. Só executa se você digitar APAGAR exatamente como está. Não pode ser desfeito.

## Dicas

- Faça um backup antes de qualquer atualização importante.
- Cadastre primeiro os cartões, as recorrentes e os parcelados. Depois, use o Início para o que é avulso e para marcar o que foi pago.
- Lance a fatura em **Cartões**, não no Início. Assim o pagamento das parcelas do cartão acompanha a fatura.
- Se um valor mudar em um mês específico, ajuste só aquele lançamento no Início.
- Antes de lançar um valor de terceiros, confira a tabela em **Como evitar duplicados**.

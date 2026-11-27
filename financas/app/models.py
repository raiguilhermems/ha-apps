"""Modelo de dados. Valores monetários são guardados em centavos (inteiro)."""

from datetime import date
from typing import Optional

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


class Account(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    type: str  # conta | cartao | investimento
    dia_pagamento: Optional[int] = None  # cartões: dia de vencimento da fatura
    dia_fechamento: Optional[int] = None  # cartões: dia em que a fatura fecha


class Tag(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(unique=True)
    # Se True, lançamentos com esta tag não entram no total (ex.: gasto de terceiro)
    excludes_from_total: bool = False
    kind: str = "categoria"  # categoria | pessoa (quem deve ou deve a você) | recorrente (gerada por uma recorrência)


class RecurringRule(SQLModel, table=True):
    __tablename__ = "recurring_rule"

    id: Optional[int] = Field(default=None, primary_key=True)
    description: str
    expected_cents: int
    day_of_month: int
    kind: str = "despesa"  # despesa | receita
    account_id: Optional[int] = Field(default=None, foreign_key="account.id")
    active: bool = True
    generated_until: Optional[str] = None  # AAAA-MM, último mês já gerado
    variable: bool = False  # valor variável (estimativa)
    tags_text: str = ""
    tag_id: Optional[int] = Field(default=None, foreign_key="tag.id")  # categoria da recorrência


class InstallmentPlan(SQLModel, table=True):
    __tablename__ = "installment_plan"

    id: Optional[int] = Field(default=None, primary_key=True)
    description: str
    payment_method: str  # cartao | boleto | carne | financiamento | outro
    account_id: Optional[int] = Field(default=None, foreign_key="account.id")
    installment_cents: int
    installments_total: int
    first_due_month: str  # AAAA-MM
    origem_csv: str = ""  # nome limpo da compra na fatura importada (para reconhecer duplicidades)
    due_day: int = 10
    tags_text: str = ""
    generated_until: Optional[str] = None  # AAAA-MM, último mês já gerado
    tipo: str = "pagar"  # pagar | receber (compra de terceiro que será devolvida)
    pessoa: str = ""  # quem vai pagar; só para receber
    parcela_inicial: int = 1  # receber: parcelas antes desta são tratadas como já recebidas
    cartao_origem_id: Optional[int] = Field(default=None, foreign_key="account.id")  # cartão da compra (receber)


class Transaction(SQLModel, table=True):
    __tablename__ = "transacao"

    id: Optional[int] = Field(default=None, primary_key=True)
    due_date: date  # vencimento (regime de caixa)
    description: str
    amount_cents: int  # sempre positivo; o tipo define o sinal no resumo
    third_party_cents: Optional[int] = None  # parte de terceiros, abatida do total
    amount_manual: bool = False  # valor alterado à mão; a regra não sobrescreve
    kind: str  # receita | despesa | aporte | resgate | transferencia
    account_id: Optional[int] = Field(default=None, foreign_key="account.id")
    recurring_rule_id: Optional[int] = Field(default=None, foreign_key="recurring_rule.id")
    installment_plan_id: Optional[int] = Field(default=None, foreign_key="installment_plan.id")
    installment_n: Optional[int] = None
    status: str = "pendente"  # pendente | pago
    paid_date: Optional[date] = None
    import_hash: Optional[str] = Field(default=None, unique=True)
    reembolso: bool = False  # a receber de terceiro: não conta como receita
    fatura_id: Optional[int] = None  # fatura do cartão de onde veio este reembolso


class FaturaCartao(SQLModel, table=True):
    """Fatura de um cartão em um mês. Gera a despesa (e a receita de terceiro) no Início."""

    __tablename__ = "fatura_cartao"
    __table_args__ = (UniqueConstraint("account_id", "referencia"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    account_id: int = Field(foreign_key="account.id")
    referencia: str  # AAAA-MM, mês do vencimento da fatura
    total_cents: int
    terceiro_cents: int = 0  # parte paga por outra pessoa, que vai devolver
    pessoa: str = ""  # quem pagou por terceiro (um nome)
    tx_despesa_id: int = Field(foreign_key="transacao.id")  # despesa da fatura no Início
    tx_receita_id: Optional[int] = Field(default=None, foreign_key="transacao.id")  # legado: use fatura_id
    liquido_cents: int = 0  # total menos o que é de terceiro: sua parte, lançada no Início


class FaturaItem(SQLModel, table=True):
    """Compra da fatura registrada para conferência: à vista (vencimento) ou parcela de um parcelado.

    Destino "terceiro" tira o valor da sua despesa. Compras à vista de terceiro geram um reembolso
    (a receber) no vencimento da fatura; parcelados de terceiro seguem o cronograma do plano.
    """

    __tablename__ = "fatura_item"

    id: Optional[int] = Field(default=None, primary_key=True)
    fatura_id: int = Field(foreign_key="fatura_cartao.id")
    kind: str = "vencimento"  # vencimento (à vista) | parcelado | manual (terceiro lançado à mão)
    descricao: str = ""
    valor_cents: int = 0
    destino: str = "sua"  # sua | terceiro
    pessoa: str = ""  # nome normalizado de quem vai devolver (só se destino terceiro)
    categorias: str = ""  # só para registro
    plan_id: Optional[int] = Field(default=None, foreign_key="installment_plan.id")
    data_compra: Optional[date] = None
    nome_original: str = ""  # título como veio no CSV (reconhece duplicidades)


class TransactionTag(SQLModel, table=True):
    transaction_id: int = Field(foreign_key="transacao.id", primary_key=True)
    tag_id: int = Field(foreign_key="tag.id", primary_key=True)


class ImportacaoIgnorada(SQLModel, table=True):
    """Compra da fatura que o usuário excluiu na prévia. Aparece como ignorada nas próximas importações."""

    __tablename__ = "importacao_ignorada"

    id: Optional[int] = Field(default=None, primary_key=True)
    data_compra: date  # data da fatura em que foi ignorada (informativa)
    nome_original: str  # nome limpo da compra
    total: int
    account_id: int = Field(foreign_key="account.id")
    valor_cents: int


class Investimento(SQLModel, table=True):
    """Caixinha de investimento. O valor atual é o último registro do histórico."""

    __tablename__ = "investimento"

    id: Optional[int] = Field(default=None, primary_key=True)
    nome: str
    tipo: str = "outro"  # renda_fixa | renda_variavel | fundos | previdencia | outro
    valor_cents: int = 0
    atualizado_em: date


class InvestimentoHistorico(SQLModel, table=True):
    """Cada valor registrado para uma caixinha, com a data a que se refere."""

    __tablename__ = "investimento_historico"

    id: Optional[int] = Field(default=None, primary_key=True)
    investimento_id: int = Field(foreign_key="investimento.id")
    data: date
    valor_cents: int


class Setting(SQLModel, table=True):
    __tablename__ = "setting"

    key: str = Field(primary_key=True)
    value: str

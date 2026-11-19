"""Modelo de dados. Valores monetários são guardados em centavos (inteiro)."""

from datetime import date
from typing import Optional

from sqlmodel import Field, SQLModel


class Account(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    type: str  # conta | cartao | investimento
    dia_pagamento: Optional[int] = None  # cartões: dia do pagamento da fatura


class Tag(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(unique=True)
    # Se True, lançamentos com esta tag não entram no total (ex.: gasto de terceiro)
    excludes_from_total: bool = False
    kind: str = "categoria"  # categoria | pessoa (pessoa: quem deve ou deve a você)


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

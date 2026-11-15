"""Modelo de dados. Valores monetários são guardados em centavos (inteiro)."""

from datetime import date
from typing import Optional

from sqlmodel import Field, SQLModel


class Account(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    type: str  # conta | cartao | investimento


class Tag(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(unique=True)
    # Se True, lançamentos com esta tag não entram no total (ex.: gasto de terceiro)
    excludes_from_total: bool = False


class Invoice(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    account_id: int = Field(foreign_key="account.id")
    ref_month: str  # AAAA-MM
    closing_date: Optional[date] = None
    due_date: date
    bank_total_cents: int
    third_party_cents: Optional[int] = None  # usado quando a fatura está em resumo
    paid_date: Optional[date] = None


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
    due_day: int = 10
    tags_text: str = ""
    generated_until: Optional[str] = None  # AAAA-MM, último mês já gerado


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
    invoice_id: Optional[int] = Field(default=None, foreign_key="invoice.id")
    purchase_date: Optional[date] = None  # só para análise de itens de fatura
    is_recurring: bool = False
    recurring_rule_id: Optional[int] = Field(default=None, foreign_key="recurring_rule.id")
    installment_plan_id: Optional[int] = Field(default=None, foreign_key="installment_plan.id")
    installment_n: Optional[int] = None
    status: str = "pendente"  # pendente | pago
    paid_date: Optional[date] = None
    import_hash: Optional[str] = Field(default=None, unique=True)


class TransactionTag(SQLModel, table=True):
    transaction_id: int = Field(foreign_key="transacao.id", primary_key=True)
    tag_id: int = Field(foreign_key="tag.id", primary_key=True)


class Valuation(SQLModel, table=True):
    """Atualização manual do valor de um investimento (account do tipo 'investimento')."""

    id: Optional[int] = Field(default=None, primary_key=True)
    account_id: int = Field(foreign_key="account.id")
    date: date
    value_cents: int


class Setting(SQLModel, table=True):
    __tablename__ = "setting"

    key: str = Field(primary_key=True)
    value: str

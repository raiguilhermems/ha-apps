"""Parcelados: cadastro, lançamento automático e cronograma.

Dois tipos de plano:
- pagar: compra parcelada que sai do seu dinheiro (cartão, boleto etc.). Vira despesa.
- receber: compra no cartão feita para outra pessoa, que vai devolver o valor. Vira receita,
  sem conta de cartão, para não entrar na fatura nem nas despesas.
"""

from datetime import date

from sqlmodel import Session, select

from app.models import Account, InstallmentPlan, Tag, Transaction, TransactionTag
from app.services.recurring import get_or_create_card
from app.services.tags import PESSOA, parse_tags, reservar_categoria, set_tags
from app.services.util import add_months, current_month, due_in_month

FORMAS = {
    "cartao": "Cartão",
    "boleto": "Boleto",
    "carne": "Carnê",
    "financiamento": "Financiamento",
    "outro": "Outro",
    "a_receber": "A receber",
}


def _months_between(a: str, b: str) -> int:
    ya, ma = map(int, a.split("-"))
    yb, mb = map(int, b.split("-"))
    return (yb - ya) * 12 + (mb - ma)


def _nome_pessoa(pessoa: str) -> str | None:
    """Nome normalizado da pessoa, usado como categoria do tipo pessoa."""
    texto = " ".join(pessoa.replace(",", " ").replace(";", " ").split())
    nomes = parse_tags(texto)
    return nomes[0] if nomes else None


def ids_da_pessoa(session: Session, nome: str) -> set[int]:
    """Lançamentos das compras a receber desta pessoa (são os únicos que podem ter a categoria dela)."""
    planos = [
        p.id
        for p in session.exec(select(InstallmentPlan).where(InstallmentPlan.tipo == "receber")).all()
        if _nome_pessoa(p.pessoa) == nome
    ]
    if not planos:
        return set()
    return set(
        session.exec(
            select(Transaction.id).where(Transaction.installment_plan_id.in_(planos))
        ).all()
    )


def _garantir_pessoa(session: Session, nome: str) -> None:
    """Cria a categoria como pessoa, ou promove uma categoria comum que só é usada por ela."""
    reservar_categoria(session, nome, PESSOA, ids_da_pessoa(session, nome), "a pessoa")


def renomear_pessoa(session: Session, tag: Tag, nome_novo: str) -> None:
    """Renomeia a pessoa: a categoria e os planos a receber dela acompanham o novo nome."""
    antigo = tag.name
    novo = _nome_pessoa(nome_novo)
    if not novo:
        raise ValueError("Informe o nome da pessoa")
    tag.name = novo
    session.add(tag)
    session.flush()
    planos = [
        p
        for p in session.exec(select(InstallmentPlan).where(InstallmentPlan.tipo == "receber")).all()
        if _nome_pessoa(p.pessoa) == antigo
    ]
    for plan in planos:
        plan.pessoa = " ".join(nome_novo.replace(",", " ").replace(";", " ").split())
        # Tira o nome antigo das categorias do plano; update_plan põe o novo no lugar
        categorias = ", ".join(n for n in parse_tags(plan.tags_text) if n != antigo)
        update_plan(session, plan, plan.description, plan.installment_cents, plan.due_day, categorias)


def _tags_do_plano(tipo: str, pessoa: str, categorias: str) -> list[str]:
    """Categorias do plano. Em "receber", o nome da pessoa vira categoria automaticamente."""
    nomes = parse_tags(categorias)
    nome = _nome_pessoa(pessoa) if tipo == "receber" else None
    if nome and nome not in nomes:
        nomes.append(nome)
    return nomes


def _descricao(plan: InstallmentPlan, n: int) -> str:
    texto = f"{plan.description} ({n}/{plan.installments_total})"
    if plan.tipo == "receber" and plan.pessoa:
        texto += f" · {plan.pessoa}"
    return texto


def create_plan(
    session: Session,
    description: str,
    payment_method: str,
    card_name: str,
    installment_cents: int,
    total: int,
    current_n: int,
    current_ref: str,
    due_day: int,
    categorias: str = "",
    tipo: str = "pagar",
    pessoa: str = "",
    cartao_origem_id: int | None = None,
) -> InstallmentPlan:
    account_id = None
    if payment_method == "cartao":
        account_id = get_or_create_card(session, card_name).id
    plan = InstallmentPlan(
        description=description.strip(),
        payment_method=payment_method,
        account_id=account_id,
        installment_cents=installment_cents,
        installments_total=total,
        first_due_month=add_months(current_ref, -(current_n - 1)),
        due_day=due_day,
        tags_text=", ".join(_tags_do_plano(tipo, pessoa, categorias)),
        tipo=tipo,
        pessoa=pessoa.strip(),
        parcela_inicial=current_n,
        cartao_origem_id=cartao_origem_id,
    )
    session.add(plan)
    session.flush()
    if tipo == "receber":
        nome = _nome_pessoa(pessoa)
        if nome:
            _garantir_pessoa(session, nome)
    return plan


def generate_installments(session: Session, months_ahead: int = 12) -> int:
    """Cria as parcelas das próximas semanas/meses que ainda não existem."""
    base = current_month()
    target_end = add_months(base, months_ahead - 1)
    created = 0

    for plan in session.exec(select(InstallmentPlan)).all():
        receber = plan.tipo == "receber"
        m = base
        if plan.generated_until:
            m = max(base, add_months(plan.generated_until, 1))
        while m <= target_end:
            n = _months_between(plan.first_due_month, m) + 1
            # Em "receber", parcelas antes da atual não são criadas
            if 1 <= n <= plan.installments_total and not (receber and n < plan.parcela_inicial):
                exists = session.exec(
                    select(Transaction.id).where(
                        Transaction.installment_plan_id == plan.id,
                        Transaction.installment_n == n,
                    )
                ).first()
                if not exists:
                    tx = Transaction(
                        description=_descricao(plan, n),
                        amount_cents=plan.installment_cents,
                        due_date=due_in_month(m, plan.due_day),
                        kind="receita" if receber else "despesa",
                        account_id=plan.account_id,
                        installment_plan_id=plan.id,
                        installment_n=n,
                        status="pendente",
                    )
                    session.add(tx)
                    session.flush()
                    set_tags(session, tx, parse_tags(plan.tags_text))
                    created += 1
            m = add_months(m, 1)
        plan.generated_until = target_end
        session.add(plan)

    session.commit()
    return created


def schedule_summaries(session: Session) -> dict:
    base = current_month()
    today = date.today()
    plans_out = []
    saldo_pagar = 0
    saldo_receber = 0
    tags_map = {c.name: c.id for c in session.exec(select(Tag)).all()}
    kinds_map = {c.name: c.kind for c in session.exec(select(Tag)).all()}

    for p in session.exec(select(InstallmentPlan)).all():
        receber = p.tipo == "receber"
        txs = session.exec(
            select(Transaction).where(Transaction.installment_plan_id == p.id)
        ).all()
        by_n = {t.installment_n: t for t in txs}

        # Em "receber", as parcelas antes da inicial contam como já recebidas
        inicio = p.parcela_inicial if receber else 1
        rows = []
        pagas = inicio - 1
        saldo = 0
        for n in range(inicio, p.installments_total + 1):
            m = add_months(p.first_due_month, n - 1)
            vencimento = due_in_month(m, p.due_day)
            t = by_n.get(n)
            tx_id = None
            if t is not None:
                tx_id = t.id
                if t.status == "pago":
                    status = "pago"
                elif vencimento < today:
                    status = "atrasada"
                else:
                    status = "pendente"
            elif m < base:
                status = "passada"
            else:
                status = "pendente"

            if status in ("pago", "passada"):
                pagas += 1
            else:
                saldo += p.installment_cents

            rows.append({
                "n": n,
                "mes": m,
                "vencimento": vencimento,
                "valor": p.installment_cents,
                "status": status,
                "tx_id": tx_id,
            })

        restantes = p.installments_total - pagas
        concluido = restantes == 0
        if not concluido:
            if receber:
                saldo_receber += saldo
            else:
                saldo_pagar += saldo

        cartao_nome = ""
        if p.account_id:
            acc = session.get(Account, p.account_id)
            cartao_nome = acc.name if acc else ""

        if receber:
            forma_label = f"A receber · {p.pessoa.lower()}" if p.pessoa else "A receber"
        elif p.payment_method == "cartao":
            forma_label = f"Cartão {cartao_nome}".strip()
        else:
            forma_label = FORMAS.get(p.payment_method, p.payment_method)

        plans_out.append({
            "id": p.id,
            "tipo": p.tipo,
            "pessoa_tag_id": tags_map.get(_nome_pessoa(p.pessoa)) if receber and p.pessoa else None,
            "pessoa": p.pessoa,
            "descricao": p.description,
            "categorias": [
                {"nome": n, "id": tags_map.get(n), "kind": kinds_map.get(n, "categoria")}
                for n in parse_tags(p.tags_text)
                # Em "receber", o nome da pessoa já aparece no link do plano; não repete aqui
                if not (receber and n == _nome_pessoa(p.pessoa))
            ],
            "forma_label": forma_label,
            "parcela": p.installment_cents,
            "total": p.installments_total,
            "pagas": pagas,
            "restantes": restantes,
            "saldo": saldo,
            "concluido": concluido,
            "rows": rows,
        })

    plans_out.sort(key=lambda r: (r["concluido"], r["descricao"]))
    return {"plans": plans_out, "saldo_total": saldo_pagar, "saldo_receber": saldo_receber}


def update_plan(
    session: Session,
    plan: InstallmentPlan,
    description: str,
    installment_cents: int,
    due_day: int,
    categorias: str = "",
) -> None:
    """Atualiza o parcelamento. Só as parcelas pendentes são alteradas; as pagas não mudam."""
    plan.description = description.strip()
    plan.installment_cents = installment_cents
    plan.due_day = due_day
    plan.tags_text = ", ".join(_tags_do_plano(plan.tipo, plan.pessoa, categorias))
    session.add(plan)
    session.flush()
    if plan.tipo == "receber":
        nome = _nome_pessoa(plan.pessoa)
        if nome:
            _garantir_pessoa(session, nome)

    pendentes = session.exec(
        select(Transaction).where(
            Transaction.installment_plan_id == plan.id,
            Transaction.status == "pendente",
        )
    ).all()
    for t in pendentes:
        t.description = _descricao(plan, t.installment_n)
        t.amount_cents = installment_cents
        t.due_date = due_in_month(t.due_date.strftime("%Y-%m"), due_day)
        session.add(t)
        session.flush()
        set_tags(session, t, parse_tags(plan.tags_text))


def converter_para_receber(
    session: Session,
    plan: InstallmentPlan,
    pessoa: str,
    cartao_origem_id: int,
    current_n: int,
    categorias: str = "",
) -> None:
    """Transforma um parcelado de cartão em a receber. Parcelas já pagas ficam como histórico."""
    for t in session.exec(select(Transaction).where(Transaction.installment_plan_id == plan.id)).all():
        if t.status == "pendente":
            for link in session.exec(select(TransactionTag).where(TransactionTag.transaction_id == t.id)).all():
                session.delete(link)
            session.delete(t)
        else:
            t.installment_plan_id = None
            t.installment_n = None
            session.add(t)
    session.flush()
    plan.tipo = "receber"
    plan.pessoa = pessoa.strip()
    plan.cartao_origem_id = cartao_origem_id
    plan.account_id = None
    plan.payment_method = "a_receber"
    plan.parcela_inicial = current_n
    plan.generated_until = None
    plan.tags_text = ", ".join(_tags_do_plano("receber", plan.pessoa, categorias or plan.tags_text))
    session.add(plan)
    session.flush()
    nome = _nome_pessoa(plan.pessoa)
    if nome:
        _garantir_pessoa(session, nome)


def delete_plan(session: Session, plan: InstallmentPlan) -> None:
    """Apaga as parcelas pendentes. As já pagas ficam como histórico, sem vínculo."""
    for t in session.exec(
        select(Transaction).where(Transaction.installment_plan_id == plan.id)
    ).all():
        if t.status == "pendente":
            for link in session.exec(
                select(TransactionTag).where(TransactionTag.transaction_id == t.id)
            ).all():
                session.delete(link)
            session.delete(t)
        else:
            t.installment_plan_id = None
            t.installment_n = None
            session.add(t)
    session.flush()
    session.delete(plan)

"""Investimentos: caixinhas com valor atual e histórico de atualizações. Sem vínculo externo."""

from datetime import date

from sqlmodel import Session, select

from app.models import Investimento, InvestimentoHistorico

TIPOS = {
    "renda_fixa": "Renda fixa",
    "renda_variavel": "Renda variável",
    "fundos": "Fundos",
    "previdencia": "Previdência",
    "outro": "Outro",
}


def _nome_valido(nome: str) -> str:
    nome = nome.strip()
    if not nome:
        raise ValueError("Informe o nome da caixinha")
    return nome


def _valor_valido(valor_cents: int) -> int:
    if valor_cents < 0:
        raise ValueError("O valor não pode ser negativo")
    return valor_cents


def _tipo_valido(tipo: str) -> str:
    return tipo if tipo in TIPOS else "outro"


def _recalcular(session: Session, inv: Investimento) -> None:
    """Valor atual = último registro pela data (e, em empate, o mais recente lançado)."""
    session.flush()
    ultimo = session.exec(
        select(InvestimentoHistorico)
        .where(InvestimentoHistorico.investimento_id == inv.id)
        .order_by(InvestimentoHistorico.data.desc(), InvestimentoHistorico.id.desc())
    ).first()
    if ultimo is not None:
        inv.valor_cents = ultimo.valor_cents
        inv.atualizado_em = ultimo.data
    session.add(inv)


def listar(session: Session) -> list[Investimento]:
    return session.exec(select(Investimento).order_by(Investimento.nome)).all()


def total(session: Session) -> int:
    return sum(i.valor_cents for i in listar(session))


def criar(session: Session, nome: str, tipo: str, valor_cents: int, data: date | None = None) -> Investimento:
    data = data or date.today()
    inv = Investimento(
        nome=_nome_valido(nome),
        tipo=_tipo_valido(tipo),
        valor_cents=_valor_valido(valor_cents),
        atualizado_em=data,
    )
    session.add(inv)
    session.flush()
    session.add(InvestimentoHistorico(investimento_id=inv.id, data=data, valor_cents=inv.valor_cents))
    _recalcular(session, inv)
    return inv


def atualizar_valor(session: Session, inv: Investimento, valor_cents: int, data: date | None = None) -> None:
    data = data or date.today()
    session.add(
        InvestimentoHistorico(investimento_id=inv.id, data=data, valor_cents=_valor_valido(valor_cents))
    )
    _recalcular(session, inv)


def editar(session: Session, inv: Investimento, nome: str, tipo: str) -> None:
    inv.nome = _nome_valido(nome)
    inv.tipo = _tipo_valido(tipo)
    session.add(inv)


def excluir(session: Session, inv: Investimento) -> None:
    for h in session.exec(
        select(InvestimentoHistorico).where(InvestimentoHistorico.investimento_id == inv.id)
    ).all():
        session.delete(h)
    session.delete(inv)


def historico(session: Session, inv_id: int) -> list[InvestimentoHistorico]:
    return session.exec(
        select(InvestimentoHistorico)
        .where(InvestimentoHistorico.investimento_id == inv_id)
        .order_by(InvestimentoHistorico.data, InvestimentoHistorico.id)
    ).all()


def historico_com_variacao(session: Session, inv_id: int) -> list[dict]:
    saida = []
    anterior = None
    for h in historico(session, inv_id):
        saida.append(
            {
                "data": h.data,
                "valor": h.valor_cents,
                "variacao": None if anterior is None else h.valor_cents - anterior,
            }
        )
        anterior = h.valor_cents
    return saida


def evolucao_total(session: Session) -> dict:
    """Soma das caixinhas em cada data em que houve algum registro."""
    latest: dict[int, int] = {}
    pontos: dict[date, int] = {}
    registros = session.exec(
        select(InvestimentoHistorico).order_by(InvestimentoHistorico.data, InvestimentoHistorico.id)
    ).all()
    for h in registros:
        latest[h.investimento_id] = h.valor_cents
        pontos[h.data] = sum(latest.values())
    datas = sorted(pontos)
    return {
        "labels": [d.strftime("%d/%m/%Y") for d in datas],
        "valores": [pontos[d] / 100 for d in datas],
    }

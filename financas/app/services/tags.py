"""Tags de lançamentos: criação, atribuição e consultas."""

from datetime import date

from sqlmodel import Session, select

from app.models import Tag, Transaction, TransactionTag

CATEGORIA = "categoria"
PESSOA = "pessoa"
RECORRENTE = "recorrente"


def nome_recorrente(descricao: str) -> str:
    """Nome da categoria de uma recorrência: minúsculo, sem vírgula nem espaço duplo."""
    return " ".join(descricao.replace(",", " ").replace(";", " ").split()).lower()


def tag_usada_fora(session: Session, tag_id: int, permitidos: set[int]) -> bool:
    """True se a categoria está em algum lançamento que não está em `permitidos`."""
    ids = session.exec(
        select(TransactionTag.transaction_id).where(TransactionTag.tag_id == tag_id)
    ).all()
    return any(tid not in permitidos for tid in ids)


def validar_categorias_livres(
    session: Session, texto: str, proprio: str | None = None, tx_id: int | None = None
) -> None:
    """Categorias digitadas à mão não podem usar o nome de uma recorrência.

    Ignora `proprio` (nome da própria regra) e categorias que já estão no lançamento `tx_id`,
    para não bloquear a edição de um lançamento que veio de uma recorrência.
    """
    for nome in parse_tags(texto):
        if nome == proprio:
            continue
        tag = session.exec(select(Tag).where(Tag.name == nome)).first()
        if tag is None or tag.kind != RECORRENTE:
            continue
        if tx_id is not None and session.exec(
            select(TransactionTag).where(
                TransactionTag.transaction_id == tx_id, TransactionTag.tag_id == tag.id
            )
        ).first() is not None:
            continue
        raise ValueError(
            f"'{nome}' é o nome de uma recorrência. Use outra categoria para este lançamento."
        )


def reservar_categoria(
    session: Session, nome: str, kind: str, permitidos: set[int], rotulo: str
) -> Tag:
    """Devolve a categoria `nome` com o tipo `kind`, sem misturar donos.

    - Não existe: cria com o tipo.
    - Já tem o tipo: reaproveita.
    - É categoria comum e só tem lançamentos de quem a reclama (`permitidos`): promove.
    - Qualquer outro caso: ValueError, sem alterar nada.
    """
    tag = session.exec(select(Tag).where(Tag.name == nome)).first()
    if tag is None:
        tag = Tag(name=nome, kind=kind, excludes_from_total=False)
        session.add(tag)
        session.flush()
        return tag
    if tag.kind == kind:
        return tag
    # Pessoa reúne tudo do mesmo nome: categoria comum vira pessoa mesmo com outros lançamentos.
    # Recorrente só aceita categoria que pertence só a ela.
    usada_fora = kind != PESSOA and tag_usada_fora(session, tag.id, permitidos)
    if tag.kind != CATEGORIA or tag.excludes_from_total or usada_fora:
        raise ValueError(
            f"Já existe a categoria '{nome}', que não pode ser usada para {rotulo}. "
            "Escolha outro nome."
        )
    tag.kind = kind
    session.add(tag)
    session.flush()
    return tag


def parse_tags(text: str) -> list[str]:
    """'Mercado, lazer;  mercado' -> ['mercado', 'lazer']."""
    names: list[str] = []
    for part in text.replace(";", ",").split(","):
        name = part.strip().lower()
        if name and name not in names:
            names.append(name)
    return names


def get_or_create_tag(session: Session, name: str, kind: str = "categoria") -> Tag:
    tag = session.exec(select(Tag).where(Tag.name == name)).first()
    if tag is None:
        tag = Tag(name=name, excludes_from_total=(name == "terceiro"), kind=kind)
        session.add(tag)
        session.flush()
    return tag


def set_tags(session: Session, tx: Transaction, names: list[str]) -> None:
    """Substitui todas as tags do lançamento pelas informadas."""
    for link in session.exec(
        select(TransactionTag).where(TransactionTag.transaction_id == tx.id)
    ).all():
        session.delete(link)
    session.flush()
    for name in names:
        tag = get_or_create_tag(session, name)
        session.add(TransactionTag(transaction_id=tx.id, tag_id=tag.id))
    session.flush()


def tags_by_tx(session: Session, tx_ids: list[int]) -> dict[int, list[str]]:
    if not tx_ids:
        return {}
    rows = session.exec(
        select(TransactionTag.transaction_id, Tag.name).where(
            Tag.id == TransactionTag.tag_id,
            TransactionTag.transaction_id.in_(tx_ids),
        )
    ).all()
    out: dict[int, list[str]] = {}
    for tid, name in rows:
        out.setdefault(tid, []).append(name)
    return out


def tag_text(session: Session, tx_id: int, exclude: tuple[str, ...] = ()) -> str:
    names = [n for n in tags_by_tx(session, [tx_id]).get(tx_id, []) if n not in exclude]
    return ", ".join(names)


def transactions_with_tag(
    session: Session, tag_id: int, start: date, end: date
) -> list[Transaction]:
    ids = session.exec(
        select(TransactionTag.transaction_id).where(TransactionTag.tag_id == tag_id)
    ).all()
    if not ids:
        return []
    return list(
        session.exec(
            select(Transaction)
            .where(
                Transaction.id.in_(ids),
                Transaction.due_date >= start,
                Transaction.due_date < end,
            )
            .order_by(Transaction.due_date)
        ).all()
    )

def mark_third_party(session: Session, tx: Transaction) -> None:
    """Marca o lançamento como terceiro (categoria 'terceiro', não soma no total)."""
    tag = session.exec(select(Tag).where(Tag.name == "terceiro")).first()
    if tag is None:
        tag = Tag(name="terceiro", excludes_from_total=True)
        session.add(tag)
        session.flush()
    session.add(TransactionTag(transaction_id=tx.id, tag_id=tag.id))


def tags_com_id_by_tx(session: Session, tx_ids: list[int]) -> dict[int, list[dict]]:
    """Como tags_by_tx, mas cada categoria vem como {"id", "name", "kind"} (para os links e a capitalização)."""
    if not tx_ids:
        return {}
    rows = session.exec(
        select(TransactionTag.transaction_id, Tag.id, Tag.name, Tag.kind).where(
            Tag.id == TransactionTag.tag_id,
            TransactionTag.transaction_id.in_(tx_ids),
        )
    ).all()
    out: dict[int, list[dict]] = {}
    for tid, tag_id, name, kind in rows:
        out.setdefault(tid, []).append({"id": tag_id, "name": name, "kind": kind})
    return out

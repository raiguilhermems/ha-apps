"""Tags de lançamentos: criação, atribuição e consultas."""

from datetime import date

from sqlmodel import Session, select

from app.models import Tag, Transaction, TransactionTag


def parse_tags(text: str) -> list[str]:
    """'Mercado, lazer;  mercado' -> ['mercado', 'lazer']."""
    names: list[str] = []
    for part in text.replace(";", ",").split(","):
        name = part.strip().lower()
        if name and name not in names:
            names.append(name)
    return names


def get_or_create_tag(session: Session, name: str) -> Tag:
    tag = session.exec(select(Tag).where(Tag.name == name)).first()
    if tag is None:
        tag = Tag(name=name, excludes_from_total=(name == "terceiro"))
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
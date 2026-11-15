from datetime import date

from app.models import Tag, Transaction, TransactionTag
from app.services.charts import categoria_mensal


def test_categoria_mensal_soma_por_mes(session):
    tag = Tag(name="mercado")
    session.add(tag)
    session.flush()
    tx = Transaction(
        description="Feira",
        amount_cents=5000,
        due_date=date(2026, 11, 10),
        kind="despesa",
        status="pendente",
    )
    session.add(tx)
    session.flush()
    session.add(TransactionTag(transaction_id=tx.id, tag_id=tag.id))
    session.commit()

    g = categoria_mensal(session, tag.id, "2026-11", antes=1, depois=1)
    assert g["despesas"] == [0, 50.0, 0]
    assert g["receitas"] == [0, 0, 0]
    assert len(g["labels"]) == 3

from app.services.projections import projection
from app.services.recurring import create_rule, generate_all
from app.services.util import current_month


def test_recorrente_entra_como_compromisso_e_nao_como_variavel(session):
    create_rule(session, "Luz", 18000, 10, "despesa", "")
    session.commit()
    generate_all(session)
    rows = projection(session, current_month(), 2)
    assert rows[0]["compromissos"] == 18000
    assert rows[0]["variavel"] == 0

"""Configurações simples guardadas no banco (chave e valor)."""

from sqlmodel import Session

from app.models import Setting

DEFAULTS = {
    "dia_padrao": "10",
    "grafico_antes": "6",
    "grafico_depois": "3",
    "taxa_desconto": "10.58",
}


def get_setting(session: Session, key: str) -> str:
    s = session.get(Setting, key)
    if s is not None:
        return s.value
    return DEFAULTS.get(key, "")


def set_setting(session: Session, key: str, value: str) -> None:
    s = session.get(Setting, key)
    if s is None:
        s = Setting(key=key, value=value)
    else:
        s.value = value
    session.add(s)
    session.commit()


def get_int_setting(session: Session, key: str, minimo: int, maximo: int) -> int:
    """Lê uma configuração numérica. Valor inválido volta ao padrão; fora da faixa é ajustado."""
    try:
        valor = int(get_setting(session, key))
    except ValueError:
        valor = int(DEFAULTS[key])
    return min(max(valor, minimo), maximo)


def get_taxa_desconto(session: Session) -> float:
    """Taxa anual em % usada para estimar o desconto de antecipação. Valor inválido volta ao padrão."""
    try:
        valor = float(get_setting(session, "taxa_desconto").replace(",", "."))
    except ValueError:
        valor = float(DEFAULTS["taxa_desconto"])
    return min(max(valor, 0.0), 100.0)

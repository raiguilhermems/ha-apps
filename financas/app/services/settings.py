"""Configurações simples guardadas no banco (chave e valor)."""

from sqlmodel import Session

from app.models import Setting

DEFAULTS = {"projecao_meses": "3"}


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

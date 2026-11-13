"""Base declarativa y utilidades compartidas por los modelos."""

import enum

from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


def enum_texto(clase: type[enum.Enum], nombre_restriccion: str) -> SAEnum:
    """Enum guardado como VARCHAR con CHECK (no como tipo ENUM nativo de Postgres).

    Para agregar un valor basta con cambiar la clase de Python y recrear la
    restricción CHECK (o la tabla, en hackathon), sin ALTER TYPE.
    """
    return SAEnum(
        clase,
        native_enum=False,
        create_constraint=True,
        name=nombre_restriccion,
        length=40,  # holgura para valores futuros
        values_callable=lambda miembros: [m.value for m in miembros],
        validate_strings=True,
    )

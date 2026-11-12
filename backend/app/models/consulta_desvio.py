"""Tabla consultas_desvio: cada mensaje del ciudadano al chat de desvío (US-009).

Sirve para medir cuántas consultas se resolvieron sin radicar una PQRSD.
No se guarda la respuesta del agente, solo la pregunta, la cobertura y los
documentos citados.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, enum_texto

LARGO_MAXIMO_PREGUNTA = 1000


class CoberturaDesvio(enum.StrEnum):
    total = "total"
    parcial = "parcial"
    ninguna = "ninguna"


class ResultadoDesvio(enum.StrEnum):
    resuelta = "resuelta"
    no_resuelta = "no_resuelta"
    continuo = "continuo"  # el ciudadano siguió hacia una PQRSD


class ConsultaDesvio(Base):
    __tablename__ = "consultas_desvio"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )
    sesion_id: Mapped[str] = mapped_column(String(64), index=True)
    pregunta: Mapped[str] = mapped_column(String(LARGO_MAXIMO_PREGUNTA))
    cobertura: Mapped[CoberturaDesvio] = mapped_column(
        enum_texto(CoberturaDesvio, "ck_consultas_desvio_cobertura")
    )
    # Nombres de los documentos citados en la respuesta (p. ej. "faq_clientes.md").
    documentos: Mapped[list[str]] = mapped_column(
        JSONB, default=list, server_default=text("'[]'::jsonb")
    )
    resultado: Mapped[ResultadoDesvio | None] = mapped_column(
        enum_texto(ResultadoDesvio, "ck_consultas_desvio_resultado")
    )
    # clock_timestamp() y no now(): dos filas de la misma transacción quedan
    # con horas distintas y "la última consulta de la sesión" no es ambigua.
    creada_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("clock_timestamp()")
    )

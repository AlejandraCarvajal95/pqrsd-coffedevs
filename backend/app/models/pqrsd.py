"""Tabla pqrsd: cada petición, queja, reclamo, sugerencia o denuncia radicada."""

import enum
import secrets
import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    Index,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, enum_texto

# Colombia no tiene horario de verano: UTC-5 fijo (evita depender de tzdata).
ZONA_COLOMBIA = timezone(timedelta(hours=-5))

# Sin caracteres ambiguos (0/O, 1/I/L) para que el radicado se pueda dictar.
ALFABETO_RADICADO = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


def generar_radicado() -> str:
    """Radicado PQRSD-AAAA-XXXXXX, aleatorio y NO consecutivo (no se puede adivinar).

    Con 31^6 (unos 887 millones) de combinaciones por año la colisión es muy
    improbable; aun así la columna es UNIQUE y quien radique debe reintentar
    si recibe IntegrityError.
    """
    anio = datetime.now(ZONA_COLOMBIA).year
    sufijo = "".join(secrets.choice(ALFABETO_RADICADO) for _ in range(6))
    return f"PQRSD-{anio}-{sufijo}"


class CanalPQRSD(enum.StrEnum):
    formulario = "formulario"
    chat = "chat"


class TipoPQRSD(enum.StrEnum):
    peticion = "peticion"
    queja = "queja"
    reclamo = "reclamo"
    sugerencia = "sugerencia"
    denuncia = "denuncia"


class EstadoPQRSD(enum.StrEnum):
    recibida = "recibida"
    clasificada = "clasificada"
    pendiente_revision_clasificacion = "pendiente_revision_clasificacion"
    asignada = "asignada"
    borrador_listo = "borrador_listo"
    respondida = "respondida"


class PQRSD(Base):
    __tablename__ = "pqrsd"
    __table_args__ = (
        CheckConstraint(
            "confianza IS NULL OR (confianza >= 0 AND confianza <= 1)",
            name="ck_pqrsd_confianza_rango",
        ),
        Index("ix_pqrsd_fecha_vencimiento", "fecha_vencimiento"),
        Index("ix_pqrsd_area_estado", "area", "estado"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )
    radicado: Mapped[str] = mapped_column(String(20), unique=True, default=generar_radicado)

    nombre_ciudadano: Mapped[str] = mapped_column(String(200))
    contacto: Mapped[str] = mapped_column(String(200))  # correo o teléfono (ficticio)
    asunto: Mapped[str] = mapped_column(String(300))
    descripcion: Mapped[str] = mapped_column(Text)
    canal: Mapped[CanalPQRSD] = mapped_column(enum_texto(CanalPQRSD, "ck_pqrsd_canal"))

    # Los define el clasificador; nulos mientras la PQRSD no se clasifique.
    tipo: Mapped[TipoPQRSD | None] = mapped_column(enum_texto(TipoPQRSD, "ck_pqrsd_tipo"))
    area: Mapped[str | None] = mapped_column(String(120))
    confianza: Mapped[float | None] = mapped_column(Float)
    # Capas que resuelve el SVM (pipeline/clasificacion_hibrida.py).
    tema: Mapped[str | None] = mapped_column(String(80))
    sentimiento: Mapped[str | None] = mapped_column(String(20))
    riesgo_fraude: Mapped[bool | None] = mapped_column(Boolean)
    # Qué dijo cada clasificador, por qué quedó en revisión y los tipos candidatos
    # (si el tipo es dudoso, el motor de plazos debe usar el plazo más corto).
    clasificacion_detalle: Mapped[dict | None] = mapped_column(JSONB)

    estado: Mapped[EstadoPQRSD] = mapped_column(
        enum_texto(EstadoPQRSD, "ck_pqrsd_estado"),
        default=EstadoPQRSD.recibida,
        server_default=EstadoPQRSD.recibida.value,
    )

    fecha_radicacion: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    fecha_vencimiento: Mapped[date | None] = mapped_column(Date)  # la calcula otra historia
    actualizada_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    borradores: Mapped[list["Borrador"]] = relationship(  # noqa: F821
        back_populates="pqrsd", cascade="all, delete-orphan", passive_deletes=True
    )

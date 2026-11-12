"""Tablas borradores y revisiones.

texto_original guarda lo que propuso la IA y NUNCA se modifica (lo protege un
trigger en la base). Las ediciones van a texto_actual y cada acción del
revisor queda en revisiones.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, enum_texto


class AccionRevision(str, enum.Enum):
    editado = "editado"
    aprobado = "aprobado"
    rechazado = "rechazado"
    regenerado = "regenerado"


class Borrador(Base):
    __tablename__ = "borradores"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )
    pqrsd_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("pqrsd.id", ondelete="CASCADE"), index=True
    )
    texto_original: Mapped[str] = mapped_column(Text)
    texto_actual: Mapped[str] = mapped_column(Text)
    # Lista de {"fragmento_id": "...", "documento": "...", "seccion": "..."}
    citas: Mapped[list[dict]] = mapped_column(
        JSONB, default=list, server_default=text("'[]'::jsonb")
    )
    modelo: Mapped[str] = mapped_column(String(100))
    tokens_entrada: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    tokens_salida: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    pqrsd: Mapped["PQRSD"] = relationship(back_populates="borradores")  # noqa: F821
    revisiones: Mapped[list["Revision"]] = relationship(
        back_populates="borrador", cascade="all, delete-orphan", passive_deletes=True
    )

    def editar(self, texto_nuevo: str, revisor: str) -> "Revision":
        """Aplica una edición humana: cambia texto_actual y registra la revisión.

        texto_original no se toca. La revisión queda en la sesión por el
        cascade de la relación; falta hacer commit.
        """
        self.texto_actual = texto_nuevo
        revision = Revision(
            pqrsd_id=self.pqrsd_id,
            accion=AccionRevision.editado,
            texto_final=texto_nuevo,
            revisor=revisor,
        )
        self.revisiones.append(revision)
        return revision


class Revision(Base):
    __tablename__ = "revisiones"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )
    borrador_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("borradores.id", ondelete="CASCADE"), index=True
    )
    pqrsd_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("pqrsd.id", ondelete="CASCADE"), index=True
    )
    accion: Mapped[AccionRevision] = mapped_column(
        enum_texto(AccionRevision, "ck_revisiones_accion")
    )
    texto_final: Mapped[str | None] = mapped_column(Text)
    revisor: Mapped[str] = mapped_column(String(120))  # por ahora un nombre ficticio
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    borrador: Mapped[Borrador] = relationship(back_populates="revisiones")


# Se ejecuta en cada arranque (idempotente): impide modificar texto_original
# aunque alguien actualice la fila con SQL directo.
DDL_PROTEGER_TEXTO_ORIGINAL = (
    """
    CREATE OR REPLACE FUNCTION proteger_texto_original() RETURNS trigger AS $$
    BEGIN
        IF NEW.texto_original IS DISTINCT FROM OLD.texto_original THEN
            RAISE EXCEPTION 'texto_original de borradores no se puede modificar (borrador %)', OLD.id;
        END IF;
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql
    """,
    """
    CREATE OR REPLACE TRIGGER trg_borradores_texto_original_inmutable
        BEFORE UPDATE OF texto_original ON borradores
        FOR EACH ROW EXECUTE FUNCTION proteger_texto_original()
    """,
)

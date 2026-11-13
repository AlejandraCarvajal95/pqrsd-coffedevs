"""Tabla consumos_ia: una fila por llamada a la API de Claude (US-015).

Sirve de contador de gasto: el total estimado en USD es la suma de costo_usd,
y se puede agrupar por tarea (clasificador, chat, generador, edicion).
"""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Numeric, String, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ConsumoIA(Base):
    __tablename__ = "consumos_ia"
    __table_args__ = (Index("ix_consumos_ia_tarea", "tarea"),)

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )
    tarea: Mapped[str] = mapped_column(String(40))
    modelo: Mapped[str] = mapped_column(String(100))
    tokens_entrada: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    tokens_salida: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    tokens_cache_escritura: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    tokens_cache_lectura: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    costo_usd: Mapped[Decimal] = mapped_column(Numeric(12, 6))
    # Opcional: la PQRSD que originó la llamada (el chat previo a radicar no tiene).
    pqrsd_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("pqrsd.id", ondelete="SET NULL"), index=True
    )
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

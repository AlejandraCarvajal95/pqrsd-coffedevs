"""Tabla fragmentos_conocimiento: trozos de normativa y políticas para el RAG."""

import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, Index, Integer, String, Text, UniqueConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.config import configuracion
from app.models.base import Base


class FragmentoConocimiento(Base):
    __tablename__ = "fragmentos_conocimiento"
    __table_args__ = (
        # Permite que la carga del conocimiento sea idempotente (upsert por esta llave).
        UniqueConstraint(
            "documento", "seccion", "indice", name="uq_fragmento_documento_seccion_indice"
        ),
        Index(
            "ix_fragmentos_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )
    documento: Mapped[str] = mapped_column(String(300))
    # NOT NULL con '' por defecto: con NULL la restricción única no detectaría duplicados.
    seccion: Mapped[str] = mapped_column(String(300), default="", server_default="")
    indice: Mapped[int] = mapped_column(Integer)
    contenido: Mapped[str] = mapped_column(Text)
    # La dimensión sale de EMBEDDING_DIM; si cambia hay que recrear la tabla.
    embedding: Mapped[list[float]] = mapped_column(Vector(configuracion.embedding_dim))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

"""Tabla cache_embeddings_consulta: embeddings de consultas RAG ya calculadas (US-012).

Si llega exactamente el mismo texto (sin contar espacios repetidos) se reutiliza
el vector guardado y no se vuelve a calcular. Se guarda el embedding y no la
lista de fragmentos, para que una recarga del conocimiento se refleje de
inmediato sin tener que invalidar la caché.
"""

from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.config import configuracion
from app.models.base import Base


class CacheEmbeddingConsulta(Base):
    __tablename__ = "cache_embeddings_consulta"

    # sha256 (hex) de "modelo de embeddings + texto normalizado".
    huella: Mapped[str] = mapped_column(String(64), primary_key=True)
    modelo: Mapped[str] = mapped_column(String(200))
    embedding: Mapped[list[float]] = mapped_column(Vector(configuracion.embedding_dim))
    usos: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    ultimo_uso: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

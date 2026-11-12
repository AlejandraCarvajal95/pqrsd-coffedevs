"""Conexión a PostgreSQL: engine, sesión y dependencia para FastAPI."""

import logging
from collections.abc import Iterator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.config import configuracion

logger = logging.getLogger(__name__)

engine = create_engine(
    configuracion.db_url.get_secret_value(),
    pool_pre_ping=True,
    connect_args={"connect_timeout": 3},  # que /api/health no se cuelgue si la base no responde
)

SesionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def obtener_sesion() -> Iterator[Session]:
    """Dependencia de FastAPI: abre una sesión por petición y la cierra al final."""
    with SesionLocal() as sesion:
        yield sesion


def base_disponible() -> bool:
    """True si se puede ejecutar una consulta trivial en la base."""
    try:
        with engine.connect() as conexion:
            conexion.execute(text("SELECT 1"))
        return True
    except Exception as error:  # noqa: BLE001 - el health solo informa disponibilidad
        # Solo el tipo de error: el mensaje podría incluir la URL de conexión.
        logger.warning("La base de datos no responde (%s)", type(error).__name__)
        return False

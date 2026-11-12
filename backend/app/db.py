"""Conexión a PostgreSQL: engine, sesión, dependencia para FastAPI e
inicialización del esquema al arrancar.

Sin Alembic (decisión de hackathon, ver CLAUDE.md): el esquema se crea con
Base.metadata.create_all, que solo crea lo que no existe.
"""

import logging
import time
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


def inicializar_base_de_datos(intentos: int = 10, espera_segundos: float = 2.0) -> None:
    """Espera a la base, habilita pgvector y crea las tablas que falten.

    Es idempotente: arrancar dos veces no falla ni borra datos.
    """
    # Import local: los modelos leen EMBEDDING_DIM de la configuración.
    from app.models import Base
    from app.models.borrador import DDL_PROTEGER_TEXTO_ORIGINAL

    for intento in range(1, intentos + 1):
        try:
            with engine.connect() as conexion:
                conexion.execute(text("SELECT 1"))
            break
        except Exception as error:  # noqa: BLE001
            logger.warning(
                "Base no disponible (intento %d/%d, %s); reintento en %.0f s",
                intento, intentos, type(error).__name__, espera_segundos,
            )
            if intento == intentos:
                raise RuntimeError(
                    f"No se pudo conectar a la base de datos tras {intentos} intentos"
                ) from None
            time.sleep(espera_segundos)

    with engine.begin() as conexion:
        conexion.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.create_all(engine)
    with engine.begin() as conexion:
        for sentencia in DDL_PROTEGER_TEXTO_ORIGINAL:
            conexion.execute(text(sentencia))
    logger.info("Base de datos lista: extensión vector y tablas verificadas")

"""Configuración común de las pruebas.

app.config se carga al importarse, así que las variables de entorno se fijan
ANTES de importar la aplicación. Los valores son de prueba (nunca reales).
La base de pruebas se toma de DB_URL; en CI la levanta GitHub Actions.
"""

import os

import pytest

os.environ.setdefault("ANTHROPIC_API_KEY", "clave-falsa-para-pruebas")
os.environ.setdefault("DB_URL", "postgresql+psycopg://pqrsd:pqrsd@localhost:5432/pqrsd_test")


@pytest.fixture(scope="session")
def base_inicializada():
    """Crea extensión y tablas una vez por sesión de pruebas."""
    from app.db import inicializar_base_de_datos

    inicializar_base_de_datos(intentos=5, espera_segundos=2)


@pytest.fixture
def sesion(base_inicializada):
    """Sesión dentro de una transacción que se deshace al final: no deja datos."""
    from sqlalchemy.orm import Session

    from app.db import engine

    conexion = engine.connect()
    transaccion = conexion.begin()
    sesion = Session(bind=conexion, join_transaction_mode="create_savepoint")
    try:
        yield sesion
    finally:
        sesion.close()
        transaccion.rollback()
        conexion.close()

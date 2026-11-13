"""Configuración común de las pruebas.

app.config se carga al importarse, así que las variables de entorno se fijan
ANTES de importar la aplicación. Los valores son de prueba (nunca reales).
La base de pruebas se toma de DB_URL; en CI la levanta GitHub Actions.
"""

import os

import pytest

os.environ.setdefault("ANTHROPIC_API_KEY", "clave-falsa-para-pruebas")
os.environ.setdefault("DB_URL", "postgresql+psycopg://pqrsd:pqrsd@localhost:5432/pqrsd_test")
os.environ.setdefault("PRECARGAR_MODELOS", "false")  # no descargar el modelo de embeddings


@pytest.fixture(scope="session")
def base_inicializada():
    """Crea extensión y tablas una vez por sesión de pruebas."""
    from app.db import inicializar_base_de_datos

    inicializar_base_de_datos(intentos=5, espera_segundos=2)


@pytest.fixture
def embedder_falso(monkeypatch):
    """Reemplaza el modelo de embeddings por uno determinista (bolsa de palabras).

    Textos con palabras en común quedan cerca; así las pruebas no descargan el
    modelo real. Devuelve la lista de lotes recibidos para contar llamadas.
    """
    import hashlib
    import re

    from app.config import configuracion
    from app.pipeline import embeddings

    llamadas: list[list[str]] = []

    def vector(texto: str) -> list[float]:
        valores = [0.0] * configuracion.embedding_dim
        for palabra in re.findall(r"\w{3,}", texto.lower()):
            posicion = int(hashlib.md5(palabra.encode()).hexdigest(), 16)
            valores[posicion % configuracion.embedding_dim] += 1.0
        if not any(valores):
            valores[0] = 1.0
        return valores

    def generar(textos: list[str]) -> list[list[float]]:
        llamadas.append(list(textos))
        return [vector(texto) for texto in textos]

    monkeypatch.setattr(embeddings, "generar_embeddings", generar)
    return llamadas


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

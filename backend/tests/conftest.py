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


class ClienteClaudeFalso:
    """Cliente de Anthropic falso: responde, en orden, lo que se le indique.

    Cada respuesta es un texto, un dict {"texto", "stop_reason"} o una excepción
    (que se lanza). La última se repite. Guarda los parámetros de cada llamada.
    """

    def __init__(self, *respuestas):
        self.respuestas = list(respuestas) or ["respuesta de prueba"]
        self.llamadas: list[dict] = []
        self.messages = self

    def create(self, **parametros):
        from types import SimpleNamespace

        self.llamadas.append(parametros)
        respuesta = self.respuestas[min(len(self.llamadas), len(self.respuestas)) - 1]
        if isinstance(respuesta, Exception):
            raise respuesta
        if isinstance(respuesta, str):
            respuesta = {"texto": respuesta}
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text=respuesta["texto"])],
            usage=SimpleNamespace(
                input_tokens=1500,
                output_tokens=600,
                cache_creation_input_tokens=0,
                cache_read_input_tokens=0,
            ),
            stop_reason=respuesta.get("stop_reason", "end_turn"),
        )


@pytest.fixture
def ia_falsa(sesion, monkeypatch):
    """Claude falso y contador de gasto dentro de la transacción de la prueba.

    Ninguna prueba llama a la API real. `ia_falsa.usar(...)` define las
    respuestas y devuelve el cliente para revisar sus llamadas.
    """
    import contextlib
    from types import SimpleNamespace

    from app.config import configuracion
    from app.pipeline import costos

    monkeypatch.setattr(configuracion, "modelo_ligero", "modelo-ligero-de-prueba")
    monkeypatch.setattr(configuracion, "modelo_borrador", "modelo-borrador-de-prueba")
    monkeypatch.setattr(costos, "fabrica_sesion", lambda: contextlib.nullcontext(sesion))
    estado = SimpleNamespace(sesion=sesion, cliente=ClienteClaudeFalso())
    monkeypatch.setattr(costos, "obtener_cliente", lambda: estado.cliente)

    def usar(*respuestas):
        estado.cliente = ClienteClaudeFalso(*respuestas)
        return estado.cliente

    estado.usar = usar
    return estado


CONOCIMIENTO_DE_PRUEBA = """# Banco de Prueba

## Cuota de manejo

La cuota de manejo de la tarjeta de crédito se cobra una sola vez cada mes.

## Reversión de cobros

Si la cuota de manejo de la tarjeta se cobra dos veces en un mes, el banco reversa el duplicado.

## Seguro de vida

El seguro de vida de saldo deudor se puede cancelar en cualquier momento.
"""


@pytest.fixture
def conocimiento_banco(sesion, embedder_falso, monkeypatch, tmp_path):
    """Base de conocimiento mínima cargada con el embedder falso (umbral 0.3)."""
    from app.config import configuracion
    from app.pipeline.conocimiento import cargar_directorio

    monkeypatch.setattr(configuracion, "rag_umbral_similitud", 0.3)
    (tmp_path / "banco_prueba.md").write_text(CONOCIMIENTO_DE_PRUEBA, encoding="utf-8")
    cargar_directorio(sesion, tmp_path)
    embedder_falso.clear()
    return sesion

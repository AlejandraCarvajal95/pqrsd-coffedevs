"""Generación de embeddings con un modelo local (fastembed + ONNX).

Anthropic no ofrece API de embeddings. Un modelo local no consume el
presupuesto de 40 USD ni necesita otra clave. El modelo se descarga la primera
vez a EMBEDDING_CACHE_DIR (en Docker, un volumen) y se carga en memoria una
sola vez por proceso, de forma perezosa: /api/health no lo carga.

El modelo por defecto (paraphrase-multilingual-MiniLM-L12-v2) entiende
español, produce 384 dimensiones y trunca la entrada a 128 tokens; por eso
los fragmentos de conocimiento son cortos.
"""

import logging
import threading

from app.config import configuracion

logger = logging.getLogger(__name__)

_modelo = None
_candado = threading.Lock()


def _obtener_modelo():
    global _modelo
    with _candado:
        if _modelo is None:
            # Import local: fastembed tarda en importarse y solo hace falta aquí.
            from fastembed import TextEmbedding

            logger.info(
                "Cargando modelo de embeddings %s (la primera vez se descarga)",
                configuracion.embedding_modelo,
            )
            _modelo = TextEmbedding(
                model_name=configuracion.embedding_modelo,
                cache_dir=configuracion.embedding_cache_dir,
            )
    return _modelo


def generar_embeddings(textos: list[str]) -> list[list[float]]:
    """Devuelve un vector por texto, en el mismo orden."""
    if not textos:
        return []
    modelo = _obtener_modelo()
    vectores = [vector.tolist() for vector in modelo.embed(textos, batch_size=32)]
    dimension = len(vectores[0])
    if dimension != configuracion.embedding_dim:
        raise RuntimeError(
            f"El modelo {configuracion.embedding_modelo} produce vectores de {dimension} "
            f"dimensiones pero EMBEDDING_DIM={configuracion.embedding_dim}. "
            "Ajusta una de las dos variables y recrea fragmentos_conocimiento."
        )
    return vectores


def generar_embedding(texto: str) -> list[float]:
    return generar_embeddings([texto])[0]

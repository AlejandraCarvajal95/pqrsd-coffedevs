"""Paso 2 del pipeline: recuperación RAG de normativa y políticas (US-012).

Uso típico desde el generador:

    resultado = recuperar(sesion, f"{pqrsd.asunto}\\n{pqrsd.descripcion}")
    if not resultado.suficiente:
        # resultado.estado == SIN_CONTEXTO: no se pasa nada al generador;
        # el borrador debe decir que no hay soporte y derivar a una persona.
        ...
    contexto = resultado.como_contexto()      # va al prompt
    citas = resultado.citas()                  # va a borradores.citas

Reglas:
- Solo pasan los fragmentos con similitud coseno >= RAG_UMBRAL_SIMILITUD.
  Si ninguno pasa, el resultado es SIN_CONTEXTO y no lleva fragmentos.
- El embedding de cada consulta se guarda en cache_embeddings_consulta. Si
  llega el mismo texto, se reutiliza sin volver a calcularlo.
"""

import hashlib
import logging
import uuid
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.config import configuracion
from app.models import CacheEmbeddingConsulta, FragmentoConocimiento
from app.pipeline import embeddings

logger = logging.getLogger(__name__)

SIN_CONTEXTO = "sin contexto suficiente"
CON_CONTEXTO = "ok"


@dataclass(frozen=True)
class FragmentoRecuperado:
    id: uuid.UUID
    documento: str
    seccion: str
    contenido: str
    similitud: float

    def cita(self) -> dict:
        """Formato de borradores.citas."""
        return {
            "fragmento_id": str(self.id),
            "documento": self.documento,
            "seccion": self.seccion,
            "similitud": round(self.similitud, 4),
        }


@dataclass(frozen=True)
class ResultadoRAG:
    estado: str  # CON_CONTEXTO o SIN_CONTEXTO
    fragmentos: tuple[FragmentoRecuperado, ...]

    @property
    def suficiente(self) -> bool:
        return self.estado == CON_CONTEXTO

    def citas(self) -> list[dict]:
        return [fragmento.cita() for fragmento in self.fragmentos]

    def como_contexto(self) -> str:
        """Texto para el prompt; cada fragmento lleva su etiqueta [F1], [F2]… para citarlo."""
        if not self.suficiente:
            return SIN_CONTEXTO
        return "\n\n".join(
            f"[F{numero}] Fuente: {f.documento} › {f.seccion}\n{f.contenido}"
            for numero, f in enumerate(self.fragmentos, start=1)
        )


def normalizar_consulta(texto: str) -> str:
    """Misma consulta = mismo texto, sin contar espacios ni saltos de línea repetidos."""
    return " ".join(texto.split())


def _huella(texto_normalizado: str) -> str:
    datos = f"{configuracion.embedding_modelo}\n{texto_normalizado}".encode()
    return hashlib.sha256(datos).hexdigest()


def embedding_de_consulta(sesion: Session, texto: str) -> list[float]:
    """Devuelve el embedding de la consulta, usando la caché si ya se calculó.

    La escritura en la caché va en un savepoint: si falla, no rompe la
    transacción de quien llama. El commit lo hace quien llama.
    """
    normalizado = normalizar_consulta(texto)
    huella = _huella(normalizado)

    guardado = sesion.get(CacheEmbeddingConsulta, huella)
    if guardado is not None:
        guardado.usos += 1
        guardado.ultimo_uso = func.now()
        logger.debug("Embedding de consulta tomado de la caché")
        return list(guardado.embedding)

    vector = embeddings.generar_embedding(normalizado)
    with sesion.begin_nested():
        sesion.execute(
            insert(CacheEmbeddingConsulta)
            .values(huella=huella, modelo=configuracion.embedding_modelo, embedding=vector)
            .on_conflict_do_nothing(index_elements=["huella"])  # otra petición se adelantó
        )
    return vector


def recuperar(
    sesion: Session,
    texto: str,
    k: int | None = None,
    umbral: float | None = None,
) -> ResultadoRAG:
    """Busca los k fragmentos más parecidos al texto y descarta los que no superan el umbral."""
    k = k or configuracion.rag_top_k
    umbral = configuracion.rag_umbral_similitud if umbral is None else umbral
    if not texto or not texto.strip():
        return ResultadoRAG(estado=SIN_CONTEXTO, fragmentos=())

    vector = embedding_de_consulta(sesion, texto)
    distancia = FragmentoConocimiento.embedding.cosine_distance(vector)
    filas = sesion.execute(
        select(FragmentoConocimiento, (1 - distancia).label("similitud"))
        .order_by(distancia)
        .limit(k)
    ).all()

    fragmentos = tuple(
        FragmentoRecuperado(
            id=fila.id,
            documento=fila.documento,
            seccion=fila.seccion,
            contenido=fila.contenido,
            similitud=float(similitud),
        )
        for fila, similitud in filas
        if similitud >= umbral
    )
    if not fragmentos:
        mejor = max((float(similitud) for _, similitud in filas), default=0.0)
        logger.info("RAG sin contexto suficiente (mejor similitud %.3f < %.3f)", mejor, umbral)
        return ResultadoRAG(estado=SIN_CONTEXTO, fragmentos=())
    return ResultadoRAG(estado=CON_CONTEXTO, fragmentos=fragmentos)

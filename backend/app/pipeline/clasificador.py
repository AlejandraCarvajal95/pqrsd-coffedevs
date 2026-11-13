"""Paso 1 del pipeline: clasificación de tipo, área y confianza (US-011).

Usa el modelo liviano con el prompt de prompts/clasificador.md, que incluye
los ejemplos fijos y se envía con caché. La salida es un JSON corto:
{"tipo", "area", "confianza", "justificacion"}.

- Si la salida no es un JSON válido (o trae un tipo, área o confianza fuera
  de lo permitido), se reintenta una vez.
- Si vuelve a fallar, o si la API no responde o se agotó el presupuesto, la
  PQRSD queda en "pendiente_revision_clasificacion" para que una persona la
  clasifique. Nunca se inventa una clasificación.

El enrutamiento según la confianza (asignar o mandar a revisión) es US-014.
"""

import logging
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from sqlalchemy.orm import Session

from app.models import PQRSD, EstadoPQRSD, TipoPQRSD
from app.pipeline import costos
from app.pipeline.costos import ErrorIA, LimiteExcedido, Tarea
from app.pipeline.json_ia import extraer_objeto_json

logger = logging.getLogger(__name__)

RUTA_PROMPT = Path(__file__).parent / "prompts" / "clasificador.md"
INTENTOS = 2  # el primero y un reintento

# Áreas de Banco Andino Ficticio (data/conocimiento/politica_y_contratos.md).
AREAS = ("Tarjetas de Crédito", "Cartera", "Seguros de Vida", "Jurídica")


@dataclass(frozen=True)
class Clasificacion:
    tipo: TipoPQRSD
    area: str
    confianza: float
    justificacion: str


@lru_cache
def prompt_sistema() -> str:
    return RUTA_PROMPT.read_text(encoding="utf-8")


def _normalizar(texto: str) -> str:
    sin_tildes = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return " ".join(sin_tildes.casefold().split())


_AREAS_NORMALIZADAS = {_normalizar(area): area for area in AREAS}


def interpretar(texto: str) -> Clasificacion | None:
    """Valida la salida del modelo. None si falta algo o está fuera de lo permitido."""
    datos = extraer_objeto_json(texto)
    if datos is None:
        return None
    try:
        tipo = TipoPQRSD(_normalizar(str(datos.get("tipo", ""))))  # "Petición" -> peticion
    except ValueError:
        return None
    area = _AREAS_NORMALIZADAS.get(_normalizar(str(datos.get("area", ""))))
    confianza = datos.get("confianza")
    if area is None or isinstance(confianza, bool) or not isinstance(confianza, int | float):
        return None
    if not 0 <= confianza <= 1:
        return None
    justificacion = str(datos.get("justificacion") or "")[:300]
    return Clasificacion(
        tipo=tipo, area=area, confianza=float(confianza), justificacion=justificacion
    )


def _mensaje(asunto: str, descripcion: str) -> list[dict]:
    contenido = f"<pqrsd>\nAsunto: {asunto}\nDescripción: {descripcion}\n</pqrsd>"
    return [{"role": "user", "content": contenido}]


def clasificar_texto(asunto: str, descripcion: str, pqrsd_id=None) -> Clasificacion | None:
    """Pide la clasificación al modelo liviano. None si dos intentos no dan un JSON válido.

    Los errores de la API y de presupuesto (ErrorIA, LimiteExcedido) se propagan.
    """
    sistema = [
        {"type": "text", "text": prompt_sistema(), "cache_control": {"type": "ephemeral"}}
    ]
    for intento in range(1, INTENTOS + 1):
        respuesta = costos.llamar_claude(
            Tarea.clasificador,
            _mensaje(asunto, descripcion),
            sistema=sistema,
            pqrsd_id=pqrsd_id,
        )
        clasificacion = None if respuesta.rechazada else interpretar(respuesta.texto)
        if clasificacion is not None:
            return clasificacion
        logger.warning(
            "Clasificación inválida (intento %d/%d, stop_reason=%s)",
            intento, INTENTOS, respuesta.stop_reason,
        )
    return None


def clasificar_pqrsd(sesion: Session, pqrsd: PQRSD) -> Clasificacion | None:
    """Clasifica y actualiza la PQRSD. No hace commit.

    Con éxito: tipo, área, confianza y estado "clasificada". Si no se pudo:
    estado "pendiente_revision_clasificacion" y tipo, área y confianza vacíos.
    """
    try:
        clasificacion = clasificar_texto(pqrsd.asunto, pqrsd.descripcion, pqrsd_id=pqrsd.id)
    except (ErrorIA, LimiteExcedido) as error:
        logger.error("No se pudo clasificar %s: %s", pqrsd.radicado, type(error).__name__)
        clasificacion = None

    if clasificacion is None:
        pqrsd.estado = EstadoPQRSD.pendiente_revision_clasificacion
        logger.info("%s queda en revisión humana de la clasificación", pqrsd.radicado)
    else:
        pqrsd.tipo = clasificacion.tipo
        pqrsd.area = clasificacion.area
        pqrsd.confianza = clasificacion.confianza
        pqrsd.estado = EstadoPQRSD.clasificada
        logger.info(
            "%s clasificada: %s, %s (confianza %.2f)",
            pqrsd.radicado, clasificacion.tipo, clasificacion.area, clasificacion.confianza,
        )
    sesion.flush()
    return clasificacion

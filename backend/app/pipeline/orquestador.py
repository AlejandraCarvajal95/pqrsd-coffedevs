"""Orquestador del pipeline de IA de una PQRSD.

Se dispara en segundo plano justo después de radicar (US-007), para que el
ciudadano reciba su radicado sin esperar a Claude. Cada paso se agrega aquí:
clasificador (US-011), clasificación híbrida con SVM, RAG y borrador (US-013).

Abre su propia sesión de base: la de la petición ya se cerró cuando corre.
Los errores se registran y no se propagan; la PQRSD radicada nunca se pierde.
"""

import logging
import uuid

from app.db import SesionLocal
from app.models import PQRSD
from app.pipeline import clasificacion_hibrida, clasificador

logger = logging.getLogger(__name__)

# Fábrica de sesiones del orquestador. Las pruebas la reemplazan.
fabrica_sesion = SesionLocal


def procesar_pqrsd(pqrsd_id: uuid.UUID) -> None:
    """Corre los pasos del pipeline sobre una PQRSD recién radicada."""
    try:
        with fabrica_sesion() as sesion:
            pqrsd = sesion.get(PQRSD, pqrsd_id)
            if pqrsd is None:
                logger.warning("Pipeline: no existe la PQRSD %s", pqrsd_id)
                return
            logger.info("Pipeline iniciado para %s", pqrsd.radicado)
            # Paso 1: Claude decide el tipo (US-011). Si falla, queda en revisión humana.
            clasificacion = clasificador.clasificar_pqrsd(sesion, pqrsd)
            # Paso 1b: el SVM resuelve área, tema, sentimiento y fraude, y verifica el tipo.
            clasificacion_hibrida.complementar(sesion, pqrsd, clasificacion)
            sesion.commit()
    except Exception:  # noqa: BLE001 - un fallo del pipeline no debe tumbar el backend
        logger.exception("Pipeline falló para la PQRSD %s", pqrsd_id)

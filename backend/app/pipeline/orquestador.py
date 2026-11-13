"""Orquestador del pipeline de IA de una PQRSD.

Se dispara en segundo plano justo después de radicar (US-007), para que el
ciudadano reciba su radicado sin esperar a Claude. Pasos:

1. Clasificador (US-011): Claude decide el tipo.
1b. Clasificación híbrida: el SVM resuelve área, tema, sentimiento y fraude.
2 y 3. RAG y borrador con citas (US-012 y US-013, pipeline/generador.py).

La clasificación se guarda (commit) antes de pedir el borrador: si el
borrador falla, la PQRSD queda "clasificada" y la atiende una persona. Las
PQRSD que quedan en revisión humana de la clasificación no reciben borrador
hasta que alguien confirme su tipo y su área.

Abre su propia sesión de base: la de la petición ya se cerró cuando corre.
Los errores se registran y no se propagan; la PQRSD radicada nunca se pierde.
"""

import logging
import uuid

from app.db import SesionLocal
from app.models import PQRSD, EstadoPQRSD
from app.pipeline import clasificacion_hibrida, clasificador, generador

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
            radicado = pqrsd.radicado
            logger.info("Pipeline iniciado para %s", radicado)
            # Paso 1: Claude decide el tipo (US-011). Si falla, queda en revisión humana.
            clasificacion = clasificador.clasificar_pqrsd(sesion, pqrsd)
            # Paso 1b: el SVM resuelve área, tema, sentimiento y fraude, y verifica el tipo.
            clasificacion_hibrida.complementar(sesion, pqrsd, clasificacion)
            # La clasificación queda guardada pase lo que pase con el borrador.
            sesion.commit()

            if pqrsd.estado != EstadoPQRSD.clasificada:
                logger.info("%s espera revisión humana; no se genera borrador", radicado)
                return
            # Pasos 2 y 3: RAG y borrador con citas (US-012 y US-013).
            try:
                generador.generar_borrador(sesion, pqrsd)
                sesion.commit()
            except Exception:  # noqa: BLE001 - sin borrador, la PQRSD sigue clasificada
                sesion.rollback()
                logger.exception("Falló el borrador de %s; queda clasificada", radicado)
    except Exception:  # noqa: BLE001 - un fallo del pipeline no debe tumbar el backend
        logger.exception("Pipeline falló para la PQRSD %s", pqrsd_id)

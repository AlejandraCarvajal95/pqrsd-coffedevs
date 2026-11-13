"""Orquestador del pipeline de IA de una PQRSD.

Se dispara en segundo plano justo después de radicar (US-007), para que el
ciudadano reciba su radicado sin esperar a Claude. Pasos:

1. Clasificador (US-011): Claude decide el tipo.
1b. Clasificación híbrida: el SVM resuelve área, tema, sentimiento y fraude.
    Con el tipo ya definido se recalcula la fecha de vencimiento (US-016).
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
from app.pipeline import clasificacion_hibrida, clasificador, dias_habiles, generador

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
            detalle = clasificacion_hibrida.complementar(sesion, pqrsd, clasificacion)
            # El plazo depende del tipo (US-016); si el tipo es dudoso, el más corto.
            tipos = detalle.get("tipos_candidatos") or [pqrsd.tipo]
            pqrsd.fecha_vencimiento = dias_habiles.calcular_vencimiento(
                pqrsd.fecha_radicacion, tipos
            )
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


def redactar_borrador(pqrsd_id: uuid.UUID) -> None:
    """Genera el borrador de una PQRSD ya clasificada que todavía no tiene uno.

    Lo dispara el panel en segundo plano cuando una persona confirma la
    clasificación o pide generar el borrador. No hace nada si ya existe.
    """
    try:
        with fabrica_sesion() as sesion:
            pqrsd = sesion.get(PQRSD, pqrsd_id)
            if pqrsd is None or pqrsd.estado != EstadoPQRSD.clasificada or pqrsd.borradores:
                return
            try:
                generador.generar_borrador(sesion, pqrsd)
                sesion.commit()
            except Exception:  # noqa: BLE001 - sin borrador, la PQRSD sigue clasificada
                sesion.rollback()
                logger.exception("Falló el borrador de la PQRSD %s", pqrsd_id)
    except Exception:  # noqa: BLE001
        logger.exception("No se pudo redactar el borrador de la PQRSD %s", pqrsd_id)

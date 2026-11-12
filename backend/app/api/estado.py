"""Consulta del estado de una PQRSD por el ciudadano (US-010).

GET /api/pqrsd/{radicado} devuelve solo lo que el ciudadano puede ver: estado
simplificado y fechas. Nunca expone borradores, clasificación, área ni datos
personales. Un radicado inexistente o mal escrito da siempre la misma
respuesta (404 genérico), y hay un límite de consultas por IP para que no se
puedan adivinar radicados probando uno tras otro.
"""

import threading
import time
from collections import defaultdict, deque
from datetime import date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import obtener_sesion
from app.models import PQRSD, EstadoPQRSD

router = APIRouter(prefix="/pqrsd", tags=["estado"])

SesionDB = Annotated[Session, Depends(obtener_sesion)]

# Máximo de consultas por IP en la ventana. Ventana deslizante en memoria:
# se pierde al reiniciar el backend, suficiente para frenar adivinanzas.
MAX_CONSULTAS_VENTANA = 20
VENTANA_SEGUNDOS = 60

MENSAJE_NO_ENCONTRADO = (
    "No encontramos una PQRSD con ese número de radicado. "
    "Revise que esté escrito igual que en su constancia."
)
MENSAJE_LIMITE = "Hizo demasiadas consultas seguidas. Espere un minuto e intente de nuevo."

# El ciudadano ve tres estados; los pasos internos del pipeline no le importan.
ETAPAS_PUBLICAS = {
    EstadoPQRSD.recibida: ("recibida", "Recibida"),
    EstadoPQRSD.clasificada: ("en_tramite", "En trámite"),
    EstadoPQRSD.pendiente_revision_clasificacion: ("en_tramite", "En trámite"),
    EstadoPQRSD.asignada: ("en_tramite", "En trámite"),
    EstadoPQRSD.borrador_listo: ("en_tramite", "En trámite"),
    EstadoPQRSD.respondida: ("respondida", "Respondida"),
}


class LimitadorConsultas:
    """Ventana deslizante por clave (IP). Seguro entre hilos."""

    def __init__(self, maximo: int, ventana_segundos: float) -> None:
        self._maximo = maximo
        self._ventana = ventana_segundos
        self._intentos: dict[str, deque[float]] = defaultdict(deque)
        self._candado = threading.Lock()

    def permitir(self, clave: str) -> bool:
        ahora = time.monotonic()
        with self._candado:
            intentos = self._intentos[clave]
            while intentos and ahora - intentos[0] > self._ventana:
                intentos.popleft()
            if len(intentos) >= self._maximo:
                return False
            intentos.append(ahora)
            return True

    def reiniciar(self) -> None:
        with self._candado:
            self._intentos.clear()


limitador = LimitadorConsultas(MAX_CONSULTAS_VENTANA, VENTANA_SEGUNDOS)


class SalidaEstado(BaseModel):
    radicado: str
    estado: str  # recibida | en_tramite | respondida
    etiqueta: str
    fecha_radicacion: datetime
    fecha_vencimiento: date | None  # nula mientras no se calcule el plazo


def _ip_del_cliente(peticion: Request) -> str:
    # nginx pone la IP real en X-Real-IP; sin proxy se usa la del socket.
    return peticion.headers.get("x-real-ip") or (
        peticion.client.host if peticion.client else "desconocida"
    )


@router.get("/{radicado}", response_model=SalidaEstado)
def consultar_estado(radicado: str, peticion: Request, sesion_db: SesionDB) -> SalidaEstado:
    if not limitador.permitir(_ip_del_cliente(peticion)):
        raise HTTPException(status_code=429, detail=MENSAJE_LIMITE)

    # El radicado se guarda en mayúsculas; se tolera que lo escriban en minúsculas.
    pqrsd = sesion_db.scalars(
        select(PQRSD).where(PQRSD.radicado == radicado.strip().upper())
    ).first()
    if pqrsd is None:
        raise HTTPException(status_code=404, detail=MENSAJE_NO_ENCONTRADO)

    estado, etiqueta = ETAPAS_PUBLICAS[pqrsd.estado]
    return SalidaEstado(
        radicado=pqrsd.radicado,
        estado=estado,
        etiqueta=etiqueta,
        fecha_radicacion=pqrsd.fecha_radicacion,
        fecha_vencimiento=pqrsd.fecha_vencimiento,
    )

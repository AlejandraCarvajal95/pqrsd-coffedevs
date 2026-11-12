"""Radicación de PQRSD (US-007): POST /api/pqrsd.

Lo usan el formulario de radicación y el chat (canal "chat"). Guarda la
PQRSD con estado "recibida", devuelve el radicado de inmediato y dispara el
pipeline de IA en segundo plano.
"""

import logging
import re
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import obtener_sesion
from app.models import PQRSD, CanalPQRSD, EstadoPQRSD
from app.models import pqrsd as modelo_pqrsd
from app.pipeline import orquestador

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/pqrsd", tags=["pqrsd"])

SesionDB = Annotated[Session, Depends(obtener_sesion)]

# Límite de la descripción: controla el costo del clasificador y del borrador.
MAX_DESCRIPCION = 4000
INTENTOS_RADICADO = 5

PATRON_CORREO = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _texto_obligatorio(valor: str) -> str:
    valor = valor.strip()
    if not valor:
        raise ValueError("es obligatorio")
    return valor


class EntradaRadicacion(BaseModel):
    nombre_ciudadano: str = Field(max_length=200)
    contacto: str = Field(max_length=200, description="Correo o teléfono (ficticios)")
    asunto: str = Field(max_length=300)
    descripcion: str = Field(max_length=MAX_DESCRIPCION)
    canal: CanalPQRSD = CanalPQRSD.formulario

    _obligatorios = field_validator("nombre_ciudadano", "asunto", "descripcion")(
        _texto_obligatorio
    )

    @field_validator("contacto")
    @classmethod
    def _contacto_valido(cls, valor: str) -> str:
        valor = _texto_obligatorio(valor)
        digitos = re.sub(r"\D", "", valor)
        es_telefono = re.fullmatch(r"[\d\s+()-]+", valor) and 7 <= len(digitos) <= 15
        if not (PATRON_CORREO.match(valor) or es_telefono):
            raise ValueError("debe ser un correo o un teléfono")
        return valor


class SalidaRadicacion(BaseModel):
    radicado: str
    estado: EstadoPQRSD
    fecha_radicacion: datetime
    mensaje: str


@router.post("", status_code=201, response_model=SalidaRadicacion)
def radicar(
    entrada: EntradaRadicacion, sesion_db: SesionDB, tareas: BackgroundTasks
) -> SalidaRadicacion:
    """Crea la PQRSD. El radicado es aleatorio; si choca con uno existente, se reintenta."""
    for _ in range(INTENTOS_RADICADO):
        pqrsd = PQRSD(
            radicado=modelo_pqrsd.generar_radicado(),
            nombre_ciudadano=entrada.nombre_ciudadano,
            contacto=entrada.contacto,
            asunto=entrada.asunto,
            descripcion=entrada.descripcion,
            canal=entrada.canal,
            estado=EstadoPQRSD.recibida,
        )
        try:
            with sesion_db.begin_nested():
                sesion_db.add(pqrsd)
                sesion_db.flush()
            break
        except IntegrityError:
            logger.warning("Radicado repetido; se genera otro")
    else:
        raise HTTPException(
            status_code=503, detail="No se pudo generar el radicado. Intente de nuevo."
        )

    sesion_db.commit()
    sesion_db.refresh(pqrsd)
    # Se lee el atributo en cada petición para que las pruebas puedan reemplazarlo.
    tareas.add_task(orquestador.procesar_pqrsd, pqrsd.id)
    return SalidaRadicacion(
        radicado=pqrsd.radicado,
        estado=pqrsd.estado,
        fecha_radicacion=pqrsd.fecha_radicacion,
        mensaje=(
            "Su PQRSD fue radicada. Guarde este número de radicado para consultar su estado."
        ),
    )

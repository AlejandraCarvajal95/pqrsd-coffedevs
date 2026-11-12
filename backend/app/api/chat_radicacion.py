"""Chat de radicación (US-008), bajo /api/chat/radicacion.

- POST /api/chat/radicacion/mensaje    un mensaje del ciudadano -> respuesta y campos extraídos
- POST /api/chat/radicacion/confirmar  el ciudadano confirma el resumen -> se radica la PQRSD

Confirmar usa la misma función que el formulario (api/pqrsd.radicar): mismas
validaciones, mismo radicado, mismo pipeline en segundo plano, canal "chat".
"""

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field, ValidationError, field_validator
from sqlalchemy.orm import Session

from app.api import pqrsd as api_pqrsd
from app.db import obtener_sesion
from app.models import CanalPQRSD
from app.pipeline import radicacion_chat

router = APIRouter(prefix="/chat/radicacion", tags=["chat-radicacion"])

SesionDB = Annotated[Session, Depends(obtener_sesion)]

MENSAJE_SESION_DESCONOCIDA = (
    "No encontramos esta conversación. Puede haber expirado: inicie una nueva."
)
MENSAJE_FALTAN_DATOS = "Todavía faltan datos para radicar: {faltantes}."
ETIQUETAS = {
    "nombre_ciudadano": "su nombre",
    "contacto": "un correo o teléfono de contacto",
    "hechos": "lo que ocurrió",
}


class EntradaMensaje(BaseModel):
    sesion_id: str | None = Field(default=None, max_length=64)
    mensaje: str = Field(min_length=1, max_length=1000)

    @field_validator("mensaje")
    @classmethod
    def _no_vacio(cls, valor: str) -> str:
        valor = valor.strip()
        if not valor:
            raise ValueError("el mensaje no puede estar vacío")
        return valor


class RadicacionPrevia(BaseModel):
    """Lo que se ve en el resumen y lo que precarga el formulario si se pasa a él."""

    nombre_ciudadano: str
    contacto: str
    asunto: str
    descripcion: str


class SalidaMensaje(BaseModel):
    sesion_id: str
    respuesta: str
    campos: dict[str, str]
    faltantes: list[str]
    listo_para_confirmar: bool
    limite_alcanzado: bool
    radicado: str | None
    resumen: RadicacionPrevia


class EntradaConfirmar(BaseModel):
    sesion_id: str = Field(max_length=64)


@router.post("/mensaje", response_model=SalidaMensaje)
def mensaje(entrada: EntradaMensaje) -> SalidaMensaje:
    respuesta = radicacion_chat.conversar(entrada.sesion_id, entrada.mensaje)
    return SalidaMensaje(
        sesion_id=respuesta.sesion_id,
        respuesta=respuesta.respuesta,
        campos=respuesta.campos,
        faltantes=respuesta.faltantes,
        listo_para_confirmar=respuesta.listo_para_confirmar,
        limite_alcanzado=respuesta.limite_alcanzado,
        radicado=respuesta.radicado,
        resumen=RadicacionPrevia(**radicacion_chat.datos_de_radicacion(respuesta.campos)),
    )


@router.post("/confirmar", response_model=api_pqrsd.SalidaRadicacion, status_code=201)
def confirmar(
    entrada: EntradaConfirmar, sesion_db: SesionDB, tareas: BackgroundTasks
) -> api_pqrsd.SalidaRadicacion:
    sesion = radicacion_chat.almacen.obtener(entrada.sesion_id)
    if sesion is None:
        raise HTTPException(status_code=404, detail=MENSAJE_SESION_DESCONOCIDA)

    # Si ya se radicó (p. ej. doble clic) se devuelve el mismo radicado: no se duplica.
    if sesion.radicacion is not None:
        return api_pqrsd.SalidaRadicacion(**sesion.radicacion)

    faltantes = sesion.faltantes()
    if faltantes:
        pendientes = ", ".join(ETIQUETAS[campo] for campo in faltantes)
        raise HTTPException(
            status_code=409, detail=MENSAJE_FALTAN_DATOS.format(faltantes=pendientes)
        )

    try:
        datos = api_pqrsd.EntradaRadicacion(
            **radicacion_chat.datos_de_radicacion(sesion.campos), canal=CanalPQRSD.chat
        )
    except ValidationError:
        raise HTTPException(
            status_code=422,
            detail="Los datos reunidos no son válidos. Revíselos o use el formulario.",
        ) from None

    salida = api_pqrsd.radicar(datos, sesion_db, tareas)
    sesion.radicacion = salida.model_dump(mode="json")
    return salida

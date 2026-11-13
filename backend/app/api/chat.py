"""Chat de desvío de consultas (US-009), bajo /api/chat.

- POST /api/chat/consulta    pregunta del ciudadano -> respuesta con fuentes
- POST /api/chat/resultado   el ciudadano dice si se resolvió su duda
- POST /api/chat/continuar   prepara (sin crearla) una PQRSD con lo conversado
- GET  /api/chat/metricas    cuántas consultas se resolvieron sin radicar

metricas es pública por ahora (solo cifras agregadas); US-022 la restringirá.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import obtener_sesion
from app.models import CoberturaDesvio, ConsultaDesvio, ResultadoDesvio
from app.pipeline import desvio

router = APIRouter(prefix="/chat", tags=["chat"])

SesionDB = Annotated[Session, Depends(obtener_sesion)]

MENSAJE_SESION_DESCONOCIDA = (
    "No encontramos esta conversación. Puede haber expirado: inicie una nueva consulta."
)


class EntradaConsulta(BaseModel):
    sesion_id: str | None = Field(default=None, max_length=64)
    mensaje: str = Field(min_length=1, max_length=1000)

    @field_validator("mensaje")
    @classmethod
    def _no_vacio(cls, valor: str) -> str:
        valor = valor.strip()
        if not valor:
            raise ValueError("el mensaje no puede estar vacío")
        return valor


class FuenteSalida(BaseModel):
    etiqueta: str
    documento: str
    seccion: str
    fragmento_id: str


class SalidaConsulta(BaseModel):
    sesion_id: str
    respuesta: str
    cobertura: CoberturaDesvio
    fuentes: list[FuenteSalida]
    ofrecer_radicar: bool
    pregunta_resuelto: bool


class EntradaResultado(BaseModel):
    sesion_id: str = Field(max_length=64)
    resolvio: bool


class SalidaResultado(BaseModel):
    sesion_id: str
    resultado: ResultadoDesvio


class EntradaContinuar(BaseModel):
    sesion_id: str = Field(max_length=64)


class RadicacionSugeridaSalida(BaseModel):
    asunto: str
    descripcion: str
    canal: str


class SalidaContinuar(BaseModel):
    mensaje: str
    radicacion_sugerida: RadicacionSugeridaSalida


class SalidaMetricas(BaseModel):
    consultas_total: int
    con_respuesta: int
    sin_contexto: int
    resueltas_sin_radicar: int
    continuaron_a_pqrsd: int
    tasa_desvio: float


def _sesion_o_404(sesion_id: str) -> desvio.SesionChat:
    sesion = desvio.almacen_sesiones.obtener(sesion_id)
    if sesion is None:
        raise HTTPException(status_code=404, detail=MENSAJE_SESION_DESCONOCIDA)
    return sesion


def _marcar_ultima(sesion_db: Session, sesion_id: str, resultado: ResultadoDesvio) -> bool:
    """Pone el resultado en la última consulta de la sesión. False si no hay ninguna."""
    ultima = sesion_db.scalars(
        select(ConsultaDesvio)
        .where(ConsultaDesvio.sesion_id == sesion_id)
        .order_by(ConsultaDesvio.creada_en.desc())
        .limit(1)
    ).first()
    if ultima is None:
        return False
    ultima.resultado = resultado
    return True


@router.post("/consulta", response_model=SalidaConsulta)
def consulta(entrada: EntradaConsulta, sesion_db: SesionDB) -> SalidaConsulta:
    respuesta = desvio.consultar(sesion_db, entrada.sesion_id, entrada.mensaje)
    sesion_db.commit()
    return SalidaConsulta(
        sesion_id=respuesta.sesion_id,
        respuesta=respuesta.respuesta,
        cobertura=respuesta.cobertura,
        fuentes=[FuenteSalida(**vars(fuente)) for fuente in respuesta.fuentes],
        ofrecer_radicar=respuesta.ofrecer_radicar,
        pregunta_resuelto=respuesta.pregunta_resuelto,
    )


@router.post("/resultado", response_model=SalidaResultado)
def resultado(entrada: EntradaResultado, sesion_db: SesionDB) -> SalidaResultado:
    _sesion_o_404(entrada.sesion_id)
    valor = ResultadoDesvio.resuelta if entrada.resolvio else ResultadoDesvio.no_resuelta
    if not _marcar_ultima(sesion_db, entrada.sesion_id, valor):
        raise HTTPException(status_code=409, detail="Esta conversación aún no tiene consultas.")
    sesion_db.commit()
    return SalidaResultado(sesion_id=entrada.sesion_id, resultado=valor)


@router.post("/continuar", response_model=SalidaContinuar)
def continuar(entrada: EntradaContinuar, sesion_db: SesionDB) -> SalidaContinuar:
    """Prepara asunto y descripción. NO crea la PQRSD ni llama a Claude."""
    sesion = _sesion_o_404(entrada.sesion_id)
    sugerida = desvio.sugerir_radicacion(sesion)
    if sugerida is None:
        raise HTTPException(
            status_code=409,
            detail="Aún no hay mensajes en esta conversación para preparar una PQRSD.",
        )
    _marcar_ultima(sesion_db, entrada.sesion_id, ResultadoDesvio.continuo)
    sesion_db.commit()
    return SalidaContinuar(
        mensaje=desvio.MENSAJE_CONTINUAR,
        radicacion_sugerida=RadicacionSugeridaSalida(**vars(sugerida)),
    )


@router.get("/metricas", response_model=SalidaMetricas)
def metricas(sesion_db: SesionDB) -> SalidaMetricas:
    def contar(*condiciones) -> int:
        consulta = select(func.count()).select_from(ConsultaDesvio).where(*condiciones)
        return sesion_db.scalar(consulta)

    total = contar()
    resueltas = contar(ConsultaDesvio.resultado == ResultadoDesvio.resuelta)
    return SalidaMetricas(
        consultas_total=total,
        con_respuesta=contar(ConsultaDesvio.cobertura != CoberturaDesvio.ninguna),
        sin_contexto=contar(ConsultaDesvio.cobertura == CoberturaDesvio.ninguna),
        resueltas_sin_radicar=resueltas,
        continuaron_a_pqrsd=contar(ConsultaDesvio.resultado == ResultadoDesvio.continuo),
        tasa_desvio=round(resueltas / total, 4) if total else 0.0,
    )

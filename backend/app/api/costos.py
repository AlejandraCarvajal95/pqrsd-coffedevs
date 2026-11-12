"""Contador de gasto de IA (US-015): GET /api/costos.

Pendiente con US-022: restringirlo a usuarios del equipo cuando exista el
acceso por roles. Solo expone cifras agregadas, nunca claves ni contenidos.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.config import configuracion
from app.db import obtener_sesion
from app.pipeline.costos import ErrorIA, LimiteExcedido, gasto_por_tarea, gasto_total

router = APIRouter(prefix="/costos", tags=["costos"])


@router.get("")
def resumen_de_gasto(sesion: Annotated[Session, Depends(obtener_sesion)]) -> dict:
    """Gasto estimado acumulado en USD, total y por tarea (clasificador, chat, generador…)."""
    total = float(gasto_total(sesion))
    return {
        "total_usd": round(total, 6),
        "alerta_usd": configuracion.gasto_alerta_usd,
        "tope_usd": configuracion.gasto_tope_usd,
        "alerta": total >= configuracion.gasto_alerta_usd,
        "por_tarea": gasto_por_tarea(sesion),
    }


def registrar_manejadores(app: FastAPI) -> None:
    """Convierte los errores de costos, IA y validación en respuestas JSON con mensaje claro."""

    @app.exception_handler(LimiteExcedido)
    async def _limite_excedido(_: Request, error: LimiteExcedido) -> JSONResponse:
        estado = 413 if error.codigo == "entrada_larga" else 429
        return JSONResponse(
            status_code=estado, content={"detail": error.mensaje, "codigo": error.codigo}
        )

    @app.exception_handler(RequestValidationError)
    async def _datos_invalidos(_: Request, error: RequestValidationError) -> JSONResponse:
        # Sin el valor recibido: solo los nombres de los campos con error.
        campos = sorted(
            {".".join(str(p) for p in d["loc"] if p != "body") for d in error.errors()} - {""}
        )
        detalle = "Datos inválidos"
        if "mensaje" in campos:
            detalle = "El mensaje debe tener entre 1 y 1000 caracteres."
        elif campos:
            detalle = f"Datos inválidos en: {', '.join(campos)}."
        return JSONResponse(
            status_code=422, content={"detail": detalle, "codigo": "datos_invalidos"}
        )

    @app.exception_handler(ErrorIA)
    async def _error_ia(_: Request, error: ErrorIA) -> JSONResponse:
        return JSONResponse(status_code=503, content={"detail": str(error), "codigo": "error_ia"})

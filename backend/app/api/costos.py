"""Contador de gasto de IA (US-015): GET /api/costos.

Pendiente con US-022: restringirlo a usuarios del equipo cuando exista el
acceso por roles. Solo expone cifras agregadas, nunca claves ni contenidos.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI, Request
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
    """Convierte los errores de costos e IA en respuestas JSON con mensaje claro."""

    @app.exception_handler(LimiteExcedido)
    async def _limite_excedido(_: Request, error: LimiteExcedido) -> JSONResponse:
        estado = 413 if error.codigo == "entrada_larga" else 429
        return JSONResponse(
            status_code=estado, content={"detail": error.mensaje, "codigo": error.codigo}
        )

    @app.exception_handler(ErrorIA)
    async def _error_ia(_: Request, error: ErrorIA) -> JSONResponse:
        return JSONResponse(status_code=503, content={"detail": str(error), "codigo": "error_ia"})

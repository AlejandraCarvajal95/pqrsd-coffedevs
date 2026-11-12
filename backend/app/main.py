"""Aplicación FastAPI de PQRSD Coffee Devs.

nginx reenvía /api/... al backend sin quitar el prefijo, por eso todas las
rutas viven bajo un APIRouter con prefix="/api".
"""

from fastapi import APIRouter, FastAPI

from app.db import base_disponible

app = FastAPI(
    title="PQRSD Coffee Devs",
    # La documentación también queda bajo /api para que nginx la exponga.
    docs_url="/api/docs",
    redoc_url=None,
    openapi_url="/api/openapi.json",
)

api = APIRouter(prefix="/api")


@api.get("/health")
def salud() -> dict:
    """Estado del backend y de la conexión a la base."""
    return {"estado": "ok", "db": base_disponible()}


app.include_router(api)

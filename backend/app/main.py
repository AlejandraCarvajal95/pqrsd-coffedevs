"""Aplicación FastAPI de PQRSD Coffee Devs.

nginx reenvía /api/... al backend sin quitar el prefijo, por eso todas las
rutas viven bajo un APIRouter con prefix="/api".
"""

import logging
import threading
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from fastapi.concurrency import run_in_threadpool

from app.api import chat, costos, estado, pqrsd
from app.config import configuracion
from app.db import base_disponible, inicializar_base_de_datos
from app.pipeline import svm

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def ciclo_de_vida(_: FastAPI):
    # Reintenta la conexión, habilita pgvector y crea las tablas que falten.
    await run_in_threadpool(inicializar_base_de_datos)
    # Precarga en segundo plano: el backend responde de inmediato y /api/health no espera.
    if configuracion.precargar_modelos:
        threading.Thread(target=svm.precargar, name="precarga-modelos", daemon=True).start()
    yield


app = FastAPI(
    title="PQRSD Coffee Devs",
    lifespan=ciclo_de_vida,
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


api.include_router(costos.router)
api.include_router(chat.router)
api.include_router(pqrsd.router)
api.include_router(estado.router)
app.include_router(api)
costos.registrar_manejadores(app)

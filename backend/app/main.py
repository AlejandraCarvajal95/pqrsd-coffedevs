"""Aplicación FastAPI de PQRSD Coffee Devs.

nginx reenvía /api/... al backend sin quitar el prefijo, por eso todas las
rutas viven bajo un APIRouter con prefix="/api".
"""

import logging
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from fastapi.concurrency import run_in_threadpool

from app.db import base_disponible, inicializar_base_de_datos

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def ciclo_de_vida(_: FastAPI):
    # Reintenta la conexión, habilita pgvector y crea las tablas que falten.
    await run_in_threadpool(inicializar_base_de_datos)
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


app.include_router(api)

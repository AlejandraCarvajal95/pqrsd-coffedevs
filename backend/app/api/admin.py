"""Acceso al panel administrativo (US-022).

POST /api/admin/login valida usuario y clave y devuelve un token firmado que
el frontend envía en "Authorization: Bearer …". La dependencia requerir_admin
protege /api/bandeja y /api/metricas. Los endpoints del ciudadano (radicar,
chats, estado, health) siguen abiertos.

- El token no se guarda en el servidor: lleva el usuario y su vencimiento, y
  va firmado (HMAC-SHA256) con una llave derivada de la clave del panel. Si
  cambia la clave, los tokens anteriores dejan de servir.
- Usuario y clave vienen de ADMIN_USUARIO y ADMIN_CLAVE. Sin clave propia,
  solo APP_ENV=desarrollo acepta las credenciales de demostración; en
  cualquier otro entorno el panel queda cerrado (503) hasta configurarla.
- Hay un límite de intentos de acceso por IP.

Alcance de la demo: un solo usuario del equipo. Los roles por área de US-022
(empleado, jefe de área) quedan pendientes.
"""

import base64
import hashlib
import hmac
import logging
import time
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field

from app.api.estado import LimitadorConsultas
from app.config import configuracion

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])

# Credencial de demostración: solo vale con APP_ENV=desarrollo y sin ADMIN_CLAVE propia.
CLAVE_DEMO = "coffeedevs-demo"
ENTORNO_DEMO = "desarrollo"

MENSAJE_CREDENCIALES = "Usuario o clave incorrectos."
MENSAJE_SIN_SESION = "Inicie sesión para usar el panel."
MENSAJE_PANEL_CERRADO = (
    "El panel no está configurado en este servidor: defina ADMIN_CLAVE en el archivo .env."
)
MENSAJE_LIMITE = "Demasiados intentos de acceso. Espere un minuto e intente de nuevo."

limitador_acceso = LimitadorConsultas(maximo=10, ventana_segundos=60)


def clave_del_panel() -> str | None:
    """La clave vigente, o None si el panel está cerrado en este entorno."""
    if configuracion.admin_clave is not None:
        return configuracion.admin_clave.get_secret_value()
    return CLAVE_DEMO if configuracion.app_env == ENTORNO_DEMO else None


def usa_credenciales_demo() -> bool:
    return configuracion.admin_clave is None and configuracion.app_env == ENTORNO_DEMO


def _llave(clave: str) -> bytes:
    return hashlib.sha256(f"panel-admin|{clave}".encode()).digest()


def _firmar(carga: str, clave: str) -> str:
    return hmac.new(_llave(clave), carga.encode(), hashlib.sha256).hexdigest()


def crear_token(usuario: str, clave: str, ahora: float | None = None) -> tuple[str, int]:
    """Devuelve (token, instante de vencimiento en segundos Unix)."""
    vence = int((ahora or time.time()) + configuracion.admin_sesion_horas * 3600)
    carga = base64.urlsafe_b64encode(f"{usuario}|{vence}".encode()).decode()
    return f"{carga}.{_firmar(carga, clave)}", vence


def usuario_del_token(token: str, clave: str, ahora: float | None = None) -> str | None:
    """El usuario si el token es auténtico y no ha vencido; si no, None."""
    carga, _, firma = token.partition(".")
    if not carga or not hmac.compare_digest(firma, _firmar(carga, clave)):
        return None
    try:
        usuario, vence = base64.urlsafe_b64decode(carga.encode()).decode().rsplit("|", 1)
        vigente = int(vence) > (ahora or time.time())
    except (ValueError, UnicodeDecodeError):
        return None
    return usuario if vigente else None


def requerir_admin(authorization: Annotated[str | None, Header()] = None) -> str:
    """Dependencia de FastAPI: exige un token válido y devuelve el usuario."""
    clave = clave_del_panel()
    if clave is None:
        raise HTTPException(status_code=503, detail=MENSAJE_PANEL_CERRADO)
    esquema, _, token = (authorization or "").partition(" ")
    usuario = usuario_del_token(token.strip(), clave) if esquema.lower() == "bearer" else None
    if usuario is None:
        raise HTTPException(
            status_code=401,
            detail=MENSAJE_SIN_SESION,
            headers={"WWW-Authenticate": "Bearer"},
        )
    return usuario


UsuarioAdmin = Annotated[str, Depends(requerir_admin)]


class EntradaLogin(BaseModel):
    usuario: str = Field(max_length=100)
    clave: str = Field(max_length=200)


def _ip_del_cliente(peticion: Request) -> str:
    return peticion.headers.get("x-real-ip") or (
        peticion.client.host if peticion.client else "desconocida"
    )


@router.get("/modo")
def modo() -> dict:
    """Dice al frontend si el panel está disponible y si usa las credenciales de demo."""
    demo = usa_credenciales_demo()
    return {
        "disponible": clave_del_panel() is not None,
        "credenciales_demo": demo,
        "usuario_demo": configuracion.admin_usuario if demo else None,
        "clave_demo": CLAVE_DEMO if demo else None,
    }


@router.post("/login")
def login(entrada: EntradaLogin, peticion: Request) -> dict:
    if not limitador_acceso.permitir(_ip_del_cliente(peticion)):
        raise HTTPException(status_code=429, detail=MENSAJE_LIMITE)
    clave = clave_del_panel()
    if clave is None:
        raise HTTPException(status_code=503, detail=MENSAJE_PANEL_CERRADO)
    # Se comparan los dos campos siempre, en tiempo constante.
    usuario_ok = hmac.compare_digest(
        entrada.usuario.strip().encode(), configuracion.admin_usuario.encode()
    )
    clave_ok = hmac.compare_digest(entrada.clave.encode(), clave.encode())
    if not (usuario_ok and clave_ok):
        logger.warning("Intento de acceso al panel rechazado")
        raise HTTPException(status_code=401, detail=MENSAJE_CREDENCIALES)
    token, vence = crear_token(configuracion.admin_usuario, clave)
    return {"token": token, "usuario": configuracion.admin_usuario, "vence": vence}


@router.get("/sesion")
def sesion(usuario: UsuarioAdmin) -> dict:
    """Permite al frontend comprobar que su token sigue vigente."""
    return {"usuario": usuario}

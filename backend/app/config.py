"""Configuración del backend leída únicamente desde variables de entorno.

Reglas:
- Ningún secreto vive en el código ni en el repositorio.
- Si falta una variable obligatoria el proceso termina con código 1 y un
  mensaje en español que nombra las variables faltantes (nunca sus valores).
- Los nombres de modelo de Claude NO se escriben en el código: llegan por
  MODELO_LIGERO y MODELO_BORRADOR.
"""

import sys
from functools import lru_cache

from pydantic import Field, SecretStr, ValidationError, field_validator
from pydantic_core import PydanticCustomError
from pydantic_settings import BaseSettings, SettingsConfigDict


class Configuracion(BaseSettings):
    # Los nombres de los campos coinciden con las variables de entorno
    # (sin distinguir mayúsculas y minúsculas).
    model_config = SettingsConfigDict(case_sensitive=False, extra="ignore")

    # --- Obligatorias (secretas: SecretStr evita que se impriman por accidente) ---
    anthropic_api_key: SecretStr
    db_url: SecretStr  # incluye la contraseña de la base, por eso también es secreta

    # --- Opcionales ---
    embedding_dim: int = Field(default=384, gt=0, le=2000)  # HNSW de pgvector admite hasta 2000
    modelo_ligero: str | None = None  # chat y clasificación
    modelo_borrador: str | None = None  # solo para el borrador final
    app_env: str = "desarrollo"

    @field_validator("anthropic_api_key", "db_url", mode="before")
    @classmethod
    def _no_vacia(cls, valor):
        # Una variable declarada pero vacía (ANTHROPIC_API_KEY=) cuenta como faltante.
        texto = valor.get_secret_value() if isinstance(valor, SecretStr) else valor
        if texto is None or (isinstance(texto, str) and not texto.strip()):
            raise PydanticCustomError("missing", "variable vacía")
        return valor

    @field_validator("modelo_ligero", "modelo_borrador", mode="before")
    @classmethod
    def _vacia_es_none(cls, valor):
        if isinstance(valor, str) and not valor.strip():
            return None
        return valor


def _salir_con_error(error: ValidationError) -> None:
    faltantes: list[str] = []
    invalidas: list[str] = []
    # include_input=False: nunca se muestra el valor recibido (podría ser un secreto).
    for detalle in error.errors(include_input=False, include_url=False):
        nombre = str(detalle["loc"][0]).upper() if detalle["loc"] else "?"
        if detalle["type"] == "missing":
            faltantes.append(nombre)
        else:
            invalidas.append(f"{nombre} ({detalle['msg']})")

    lineas = ["ERROR DE CONFIGURACIÓN: el backend no puede arrancar."]
    if faltantes:
        lineas.append("Faltan variables de entorno obligatorias: " + ", ".join(faltantes))
    if invalidas:
        lineas.append("Variables con valor inválido: " + "; ".join(invalidas))
    lineas.append("Revisa tu archivo .env (puedes partir de .env.example).")
    print("\n".join(lineas), file=sys.stderr, flush=True)
    sys.exit(1)


@lru_cache
def obtener_configuracion() -> Configuracion:
    try:
        return Configuracion()
    except ValidationError as error:
        _salir_con_error(error)
        raise  # inalcanzable; tranquiliza al verificador de tipos


# Se carga al importar el módulo: si falta algo, el backend falla al arrancar.
configuracion = obtener_configuracion()

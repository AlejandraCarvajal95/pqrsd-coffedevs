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

    # --- Embeddings (locales con fastembed: no consumen presupuesto de API) ---
    # Debe producir vectores de EMBEDDING_DIM dimensiones. Si se cambia, recargar
    # el conocimiento con --forzar.
    embedding_modelo: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    embedding_cache_dir: str | None = None  # dónde se guarda el modelo descargado
    # Carga los modelos SVM y el de embeddings al arrancar (en segundo plano), para que la
    # primera PQRSD no espere ~1 minuto. Las pruebas lo apagan.
    precargar_modelos: bool = True

    # --- RAG ---
    rag_top_k: int = Field(default=4, gt=0, le=20)
    # Similitud coseno mínima (0 a 1) para pasar un fragmento al generador. Calibrada
    # con los documentos de la demo: lo relevante queda sobre 0.31 y lo ajeno bajo 0.28.
    rag_umbral_similitud: float = Field(default=0.30, ge=0, le=1)

    # --- Control de costos de IA (US-015) ---
    max_mensajes_sesion: int = Field(default=12, gt=0)
    gasto_alerta_usd: float = Field(default=30.0, gt=0)
    gasto_tope_usd: float = Field(default=40.0, gt=0)  # al llegar aquí se bloquean las llamadas
    # Precios en USD por millón de tokens. Deben corresponder a MODELO_LIGERO y MODELO_BORRADOR.
    precio_ligero_entrada_usd_mtok: float = Field(default=0.10, ge=0)
    precio_ligero_salida_usd_mtok: float = Field(default=0.50, ge=0)
    precio_borrador_entrada_usd_mtok: float = Field(default=2.00, ge=0)
    precio_borrador_salida_usd_mtok: float = Field(default=10.00, ge=0)

    # --- Plazos y semáforo (US-016 y US-017) ---
    # Plazo general en días hábiles (el reto y la Ley 1755 de 2015 hablan de 15).
    plazo_dias_habiles: int = Field(default=15, gt=0, le=90)
    # Plazo distinto por tipo, en JSON: {"peticion": 15, "queja": 15}. Vacío = plazo general.
    plazos_por_tipo: dict[str, int] = Field(default_factory=dict)
    # Rojo: quedan estos días hábiles o menos (o ya venció). Amarillo: hasta estos días.
    semaforo_rojo_dias: int = Field(default=3, ge=0)
    semaforo_amarillo_dias: int = Field(default=7, ge=0)

    # --- Panel administrativo (US-022) ---
    admin_usuario: str = "admin"
    # Sin clave (o con el marcador de .env.example): en APP_ENV=desarrollo se usan las
    # credenciales de demostración; en cualquier otro entorno el panel queda cerrado.
    admin_clave: SecretStr | None = None
    admin_sesion_horas: int = Field(default=12, gt=0, le=72)

    @field_validator("plazos_por_tipo", mode="before")
    @classmethod
    def _plazos_vacios(cls, valor):
        if valor is None or (isinstance(valor, str) and not valor.strip()):
            return {}
        return valor

    @field_validator("plazos_por_tipo")
    @classmethod
    def _plazos_positivos(cls, valor: dict[str, int]) -> dict[str, int]:
        if any(dias <= 0 for dias in valor.values()):
            raise ValueError("los plazos por tipo deben ser mayores que cero")
        return valor

    @field_validator("admin_clave", mode="before")
    @classmethod
    def _clave_sin_definir(cls, valor):
        texto = valor.get_secret_value() if isinstance(valor, SecretStr) else valor
        if texto is None or (isinstance(texto, str) and texto.strip() in ("", "cambiar-esto")):
            return None
        return valor

    @field_validator("anthropic_api_key", "db_url", mode="before")
    @classmethod
    def _no_vacia(cls, valor):
        # Una variable declarada pero vacía (ANTHROPIC_API_KEY=) cuenta como faltante.
        texto = valor.get_secret_value() if isinstance(valor, SecretStr) else valor
        if texto is None or (isinstance(texto, str) and not texto.strip()):
            raise PydanticCustomError("missing", "variable vacía")
        return valor

    @field_validator("modelo_ligero", "modelo_borrador", "embedding_cache_dir", mode="before")
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

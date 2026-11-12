"""Chat de radicación con extracción de campos (US-008).

El ciudadano cuenta su caso en lenguaje natural; el agente (modelo liviano)
extrae los campos de la PQRSD, detecta los que faltan y los pide. Cuando los
obligatorios están completos, el ciudadano confirma y se radica con el mismo
flujo del formulario (POST /api/pqrsd, canal "chat").

Reglas que mantienen el control en el código y no en el modelo:
1. Qué falta lo decide el código (OBLIGATORIOS), no lo que diga el modelo.
2. El contacto se valida con las mismas reglas del formulario; si no sirve,
   se descarta y se le pide de nuevo al ciudadano.
3. Los valores del modelo se recortan a los largos que acepta la radicación.
4. Si el modelo responde algo ilegible, se pide reformular y los campos ya
   reunidos no se pierden.
5. Al superar el tope de mensajes por sesión no se llama al modelo: se ofrece
   radicar con lo reunido o pasar al formulario.

El historial vive en memoria, igual que en desvio.py: se pierde al reiniciar
el backend.
"""

import json
import re
import threading
import uuid
from collections import OrderedDict
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from pydantic import ValidationError

from app.pipeline import costos
from app.pipeline.costos import LimiteExcedido, Tarea

RUTA_PROMPT = Path(__file__).parent / "prompts" / "radicacion.md"

MAX_SESIONES = 10_000
MENSAJES_PREVIOS_EN_PROMPT = 4  # 2 turnos; el estado completo viaja en <campos_actuales>
LARGO_RESPUESTA = 800

# Largos máximos de cada campo. nombre, contacto y asunto coinciden con la
# radicación; "hechos" deja espacio para fecha y producto dentro de los 4000.
LARGOS = {
    "nombre_ciudadano": 200,
    "contacto": 200,
    "asunto": 300,
    "hechos": 2500,
    "fecha_hechos": 100,
    "producto": 200,
}
CAMPOS = tuple(LARGOS)
OBLIGATORIOS = ("nombre_ciudadano", "contacto", "hechos")
LARGO_ASUNTO_AUTOMATICO = 80

MENSAJE_REFORMULAR = (
    "No logré entender bien su mensaje. ¿Puede contarme de nuevo qué ocurrió, con otras palabras?"
)
MENSAJE_CONTACTO_INVALIDO = (
    "El dato de contacto debe ser un correo electrónico o un teléfono válido. "
    "¿Me lo puede escribir de nuevo?"
)
MENSAJE_LISTO = "Ya tengo lo necesario. Revise el resumen y, si está bien, confirme para radicar."
MENSAJE_LIMITE_COMPLETO = (
    "Esta conversación llegó al máximo de mensajes permitido. Ya tengo los datos necesarios: "
    "puede radicar su PQRSD con lo que me contó o pasar al formulario para ajustarla."
)
MENSAJE_LIMITE_INCOMPLETO = (
    "Esta conversación llegó al máximo de mensajes permitido y todavía faltan datos. "
    "Pase al formulario: ya lo llené con lo que me contó, solo complete lo que falta."
)
MENSAJE_YA_RADICADA = (
    "Su PQRSD ya fue radicada con el número {radicado}. "
    "Si tiene otro caso, inicie una conversación nueva."
)


# ---------------------------------------------------------------------------
# Sesiones en memoria
# ---------------------------------------------------------------------------


@dataclass
class SesionRadicacion:
    campos: dict[str, str] = field(default_factory=dict)
    # Pares (mensaje del ciudadano, respuesta que se le mostró), en orden.
    historial: list[tuple[str, str]] = field(default_factory=list)
    radicacion: dict | None = None  # resultado de radicar; evita duplicados al reconfirmar

    def faltantes(self) -> list[str]:
        return [campo for campo in OBLIGATORIOS if not self.campos.get(campo)]


class AlmacenRadicacion:
    """Sesiones de radicación acotadas en cantidad. Seguro entre hilos."""

    def __init__(self, max_sesiones: int = MAX_SESIONES):
        self._sesiones: OrderedDict[str, SesionRadicacion] = OrderedDict()
        self._candado = threading.Lock()
        self._max_sesiones = max_sesiones

    def nueva(self) -> str:
        sesion_id = str(uuid.uuid4())
        with self._candado:
            self._sesiones[sesion_id] = SesionRadicacion()
            while len(self._sesiones) > self._max_sesiones:
                self._sesiones.popitem(last=False)
        return sesion_id

    def obtener(self, sesion_id: str | None) -> SesionRadicacion | None:
        if sesion_id is None:
            return None
        with self._candado:
            sesion = self._sesiones.get(sesion_id)
            if sesion is not None:
                self._sesiones.move_to_end(sesion_id)
            return sesion

    def reiniciar(self) -> None:
        with self._candado:
            self._sesiones.clear()


almacen = AlmacenRadicacion()


# ---------------------------------------------------------------------------
# Resultado de un turno
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RespuestaRadicacion:
    sesion_id: str
    respuesta: str
    campos: dict[str, str]
    faltantes: list[str]
    listo_para_confirmar: bool
    limite_alcanzado: bool = False
    radicado: str | None = None


@lru_cache
def prompt_sistema() -> str:
    return RUTA_PROMPT.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Validación y armado de la radicación
# ---------------------------------------------------------------------------


def contacto_valido(valor: str) -> bool:
    """Misma regla del formulario: se prueba con el modelo de entrada de la radicación."""
    from app.api.pqrsd import EntradaRadicacion  # import local: api importa pipeline

    try:
        EntradaRadicacion(nombre_ciudadano="x", contacto=valor, asunto="x", descripcion="x")
    except ValidationError:
        return False
    return True


def asunto_de(campos: dict[str, str]) -> str:
    return campos.get("asunto") or campos.get("hechos", "")[:LARGO_ASUNTO_AUTOMATICO]


def descripcion_de(campos: dict[str, str]) -> str:
    """Hechos más fecha y producto, en el orden que lee mejor quien responde."""
    partes = [campos.get("hechos", "")]
    if campos.get("fecha_hechos"):
        partes.append(f"Fecha de los hechos: {campos['fecha_hechos']}")
    if campos.get("producto"):
        partes.append(f"Producto o servicio: {campos['producto']}")
    return "\n\n".join(parte for parte in partes if parte)


def datos_de_radicacion(campos: dict[str, str]) -> dict[str, str]:
    """Lo que se muestra como resumen y lo que precarga el formulario."""
    return {
        "nombre_ciudadano": campos.get("nombre_ciudadano", ""),
        "contacto": campos.get("contacto", ""),
        "asunto": asunto_de(campos),
        "descripcion": descripcion_de(campos),
    }


# ---------------------------------------------------------------------------
# Salida del modelo
# ---------------------------------------------------------------------------


def interpretar_salida(texto: str) -> tuple[dict, str] | None:
    """Lee {"campos": {...}, "respuesta": "..."}. Tolera cercos de código y texto alrededor."""
    limpio = re.sub(r"```(?:json)?", "", texto).strip()
    inicio, fin = limpio.find("{"), limpio.rfind("}")
    if inicio == -1 or fin <= inicio:
        return None
    try:
        datos = json.loads(limpio[inicio : fin + 1])
    except json.JSONDecodeError:
        return None
    if not isinstance(datos, dict):
        return None
    respuesta = datos.get("respuesta")
    if not isinstance(respuesta, str) or not respuesta.strip():
        return None
    campos = datos.get("campos")
    return (campos if isinstance(campos, dict) else {}), respuesta.strip()[:LARGO_RESPUESTA]


def fusionar_campos(sesion: SesionRadicacion, propuestos: dict) -> bool:
    """Aplica lo que propuso el modelo. Devuelve False si el contacto propuesto no sirve.

    Solo se aceptan los campos conocidos, como texto no vacío, recortado a su largo.
    El valor nuevo reemplaza al anterior: así el ciudadano puede corregir.
    """
    contacto_ok = True
    for nombre in CAMPOS:
        valor = propuestos.get(nombre)
        if not isinstance(valor, str):
            continue
        valor = valor.strip()[: LARGOS[nombre]]
        if not valor:
            continue
        if nombre == "contacto" and not contacto_valido(valor):
            contacto_ok = False
            continue
        sesion.campos[nombre] = valor
    return contacto_ok


def _armar_mensajes(sesion: SesionRadicacion, mensaje: str) -> list[dict]:
    mensajes: list[dict] = []
    for pregunta, respuesta in sesion.historial[-MENSAJES_PREVIOS_EN_PROMPT // 2 :]:
        mensajes.append({"role": "user", "content": pregunta})
        mensajes.append({"role": "assistant", "content": respuesta})
    mensajes.append(
        {
            "role": "user",
            "content": (
                f"<campos_actuales>\n{json.dumps(sesion.campos, ensure_ascii=False)}\n"
                f"</campos_actuales>\n\n<mensaje>\n{mensaje}\n</mensaje>"
            ),
        }
    )
    return mensajes


def _respuesta(
    sesion_id: str, sesion: SesionRadicacion, texto: str, **extra
) -> RespuestaRadicacion:
    faltantes = sesion.faltantes()
    return RespuestaRadicacion(
        sesion_id=sesion_id,
        respuesta=texto,
        campos=dict(sesion.campos),
        faltantes=faltantes,
        listo_para_confirmar=not faltantes,
        **extra,
    )


# ---------------------------------------------------------------------------
# Un turno de la conversación
# ---------------------------------------------------------------------------


def conversar(sesion_id: str | None, mensaje: str) -> RespuestaRadicacion:
    """Procesa un mensaje del ciudadano. Si la sesión es nula o desconocida, abre una nueva."""
    sesion = almacen.obtener(sesion_id)
    if sesion is None:
        sesion_id = almacen.nueva()
        sesion = almacen.obtener(sesion_id)

    if sesion.radicacion is not None:
        texto = MENSAJE_YA_RADICADA.format(radicado=sesion.radicacion["radicado"])
        return _respuesta(sesion_id, sesion, texto, radicado=sesion.radicacion["radicado"])

    try:
        salida = costos.llamar_claude(
            Tarea.chat,
            _armar_mensajes(sesion, mensaje),
            sistema=[
                {"type": "text", "text": prompt_sistema(), "cache_control": {"type": "ephemeral"}}
            ],
            sesion_chat=sesion_id,
        )
    except LimiteExcedido as error:
        if error.codigo != "mensajes_sesion":
            raise
        texto = MENSAJE_LIMITE_INCOMPLETO if sesion.faltantes() else MENSAJE_LIMITE_COMPLETO
        return _respuesta(sesion_id, sesion, texto, limite_alcanzado=True)

    interpretada = None if salida.rechazada else interpretar_salida(salida.texto)
    if interpretada is None:
        sesion.historial.append((mensaje, MENSAJE_REFORMULAR))
        return _respuesta(sesion_id, sesion, MENSAJE_REFORMULAR)

    propuestos, texto = interpretada
    contacto_ok = fusionar_campos(sesion, propuestos)
    if not contacto_ok:
        texto = f"{texto}\n\n{MENSAJE_CONTACTO_INVALIDO}"
    if not sesion.faltantes() and contacto_ok:
        texto = f"{texto}\n\n{MENSAJE_LISTO}"
    sesion.historial.append((mensaje, texto))
    return _respuesta(sesion_id, sesion, texto)

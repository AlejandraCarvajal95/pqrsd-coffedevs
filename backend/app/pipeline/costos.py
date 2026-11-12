"""Control de costos de IA (US-015). Toda llamada a Claude pasa por llamar_claude().

Qué garantiza:
1. Enrutamiento de modelos: clasificador, chat y edicion usan MODELO_LIGERO;
   solo generador (el borrador final) usa MODELO_BORRADOR.
2. Límites: max_tokens tope por tarea, tamaño máximo de la entrada y número
   máximo de mensajes por sesión de chat. Si se superan, se lanza
   LimiteExcedido con un mensaje claro y NO se llama a la API.
3. Contador de gasto: cada llamada queda en consumos_ia con su costo estimado.
   La fila se guarda en una sesión propia: aunque la petición falle después,
   el gasto queda registrado.
4. Alerta: desde GASTO_ALERTA_USD (30) cada llamada escribe una advertencia en
   el log y marca la respuesta con alerta_presupuesto=True. Desde
   GASTO_TOPE_USD (40) se bloquean las llamadas.

Ejemplo:

    respuesta = llamar_claude(
        Tarea.clasificador,
        sistema=prompt_sistema,
        mensajes=[{"role": "user", "content": texto_pqrsd}],
        pqrsd_id=pqrsd.id,
    )
    respuesta.texto, respuesta.tokens_entrada, respuesta.costo_usd
"""

import enum
import logging
import threading
import uuid
from collections import OrderedDict
from dataclasses import dataclass
from decimal import Decimal

import anthropic
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import configuracion
from app.db import SesionLocal
from app.models import ConsumoIA

logger = logging.getLogger(__name__)

# Las lecturas de caché cuestan ~0.1x la entrada (0.05x en Sonnet 5.5) y las
# escrituras 1.25x (TTL de 5 minutos). Con 0.1x la estimación queda del lado alto.
FACTOR_ESCRITURA_CACHE = Decimal("1.25")
FACTOR_LECTURA_CACHE = Decimal("0.1")
UN_MILLON = Decimal(1_000_000)


class Tarea(enum.StrEnum):
    clasificador = "clasificador"
    chat = "chat"
    generador = "generador"
    edicion = "edicion"


class RolModelo(enum.StrEnum):
    ligero = "ligero"
    borrador = "borrador"


@dataclass(frozen=True)
class PoliticaTarea:
    rol: RolModelo
    max_tokens: int  # tope de salida por llamada
    max_caracteres_entrada: int  # sistema + mensajes
    esfuerzo: str  # output_config.effort: menos esfuerzo, menos tokens de razonamiento


POLITICAS: dict[Tarea, PoliticaTarea] = {
    Tarea.clasificador: PoliticaTarea(RolModelo.ligero, 400, 12_000, "low"),
    Tarea.chat: PoliticaTarea(RolModelo.ligero, 700, 12_000, "low"),
    Tarea.edicion: PoliticaTarea(RolModelo.ligero, 1_500, 16_000, "low"),
    Tarea.generador: PoliticaTarea(RolModelo.borrador, 2_000, 24_000, "medium"),
}


class LimiteExcedido(Exception):
    """Se superó un límite de costo. El mensaje se puede mostrar al usuario."""

    def __init__(self, codigo: str, mensaje: str):
        super().__init__(mensaje)
        self.codigo = codigo
        self.mensaje = mensaje


class ErrorIA(Exception):
    """La API de Claude no respondió bien. El mensaje se puede mostrar al usuario."""


@dataclass(frozen=True)
class RespuestaIA:
    texto: str
    tarea: Tarea
    modelo: str
    tokens_entrada: int  # incluye los de caché, para borradores.tokens_entrada
    tokens_salida: int
    costo_usd: Decimal
    stop_reason: str | None
    truncada: bool  # se llegó a max_tokens: el texto puede estar incompleto
    rechazada: bool  # stop_reason == "refusal": no usar el texto
    alerta_presupuesto: bool
    gasto_total_usd: Decimal


# ---------------------------------------------------------------------------
# Modelos y precios
# ---------------------------------------------------------------------------


def modelo_para(tarea: Tarea) -> str:
    rol = POLITICAS[tarea].rol
    modelo = (
        configuracion.modelo_ligero if rol is RolModelo.ligero else configuracion.modelo_borrador
    )
    if not modelo:
        variable = "MODELO_LIGERO" if rol is RolModelo.ligero else "MODELO_BORRADOR"
        raise ErrorIA(f"Falta la variable {variable} para la tarea {tarea}.")
    return modelo


def _precios(rol: RolModelo) -> tuple[Decimal, Decimal]:
    if rol is RolModelo.ligero:
        entrada = configuracion.precio_ligero_entrada_usd_mtok
        salida = configuracion.precio_ligero_salida_usd_mtok
    else:
        entrada = configuracion.precio_borrador_entrada_usd_mtok
        salida = configuracion.precio_borrador_salida_usd_mtok
    return Decimal(str(entrada)), Decimal(str(salida))


def calcular_costo(
    tarea: Tarea,
    tokens_entrada: int,
    tokens_salida: int,
    tokens_cache_escritura: int = 0,
    tokens_cache_lectura: int = 0,
) -> Decimal:
    """Costo estimado en USD. tokens_entrada son los no cacheados (usage.input_tokens)."""
    precio_entrada, precio_salida = _precios(POLITICAS[tarea].rol)
    costo = (
        tokens_entrada * precio_entrada
        + tokens_cache_escritura * precio_entrada * FACTOR_ESCRITURA_CACHE
        + tokens_cache_lectura * precio_entrada * FACTOR_LECTURA_CACHE
        + tokens_salida * precio_salida
    ) / UN_MILLON
    return costo.quantize(Decimal("0.000001"))


# ---------------------------------------------------------------------------
# Límite de mensajes por sesión de chat (en memoria del proceso)
# ---------------------------------------------------------------------------


class ContadorMensajes:
    """Cuenta los mensajes por sesión de chat.

    Vive en memoria: se reinicia si se reinicia el backend, lo que basta para
    la demo (uvicorn corre con un solo proceso). Guarda como máximo
    `max_sesiones` sesiones; descarta las más antiguas.
    """

    def __init__(self, max_sesiones: int = 10_000):
        self._conteos: OrderedDict[str, int] = OrderedDict()
        self._candado = threading.Lock()
        self._max_sesiones = max_sesiones

    def registrar(self, sesion_chat: str, limite: int | None = None) -> int:
        """Suma un mensaje. Si ya se llegó al límite, lanza LimiteExcedido sin sumar."""
        limite = limite or configuracion.max_mensajes_sesion
        with self._candado:
            usados = self._conteos.get(sesion_chat, 0)
            if usados >= limite:
                raise LimiteExcedido(
                    "mensajes_sesion",
                    f"Esta conversación llegó al máximo de {limite} mensajes. "
                    "Puedes radicar tu PQRSD con la información que ya diste "
                    "o usar el formulario de radicación.",
                )
            self._conteos[sesion_chat] = usados + 1
            self._conteos.move_to_end(sesion_chat)
            while len(self._conteos) > self._max_sesiones:
                self._conteos.popitem(last=False)
            return usados + 1

    def restantes(self, sesion_chat: str, limite: int | None = None) -> int:
        limite = limite or configuracion.max_mensajes_sesion
        with self._candado:
            return max(limite - self._conteos.get(sesion_chat, 0), 0)

    def reiniciar(self, sesion_chat: str | None = None) -> None:
        with self._candado:
            if sesion_chat is None:
                self._conteos.clear()
            else:
                self._conteos.pop(sesion_chat, None)


contador_mensajes = ContadorMensajes()


# ---------------------------------------------------------------------------
# Contador de gasto
# ---------------------------------------------------------------------------

# Fábrica de sesiones del contador. Las pruebas la reemplazan.
fabrica_sesion = SesionLocal


def gasto_total(sesion: Session) -> Decimal:
    total = sesion.scalar(select(func.coalesce(func.sum(ConsumoIA.costo_usd), 0)))
    return Decimal(total)


def gasto_por_tarea(sesion: Session) -> list[dict]:
    filas = sesion.execute(
        select(
            ConsumoIA.tarea,
            func.count().label("llamadas"),
            func.sum(ConsumoIA.tokens_entrada).label("tokens_entrada"),
            func.sum(ConsumoIA.tokens_salida).label("tokens_salida"),
            func.sum(ConsumoIA.costo_usd).label("costo_usd"),
        )
        .group_by(ConsumoIA.tarea)
        .order_by(ConsumoIA.tarea)
    ).all()
    return [
        {
            "tarea": fila.tarea,
            "llamadas": fila.llamadas,
            "tokens_entrada": int(fila.tokens_entrada or 0),
            "tokens_salida": int(fila.tokens_salida or 0),
            "costo_usd": float(fila.costo_usd or 0),
        }
        for fila in filas
    ]


def _registrar_consumo(consumo: ConsumoIA) -> Decimal:
    """Guarda el consumo y devuelve el gasto total acumulado."""
    with fabrica_sesion() as sesion:
        sesion.add(consumo)
        sesion.commit()
        return gasto_total(sesion)


def verificar_presupuesto() -> Decimal:
    """Lanza LimiteExcedido si ya se llegó al tope. Devuelve el gasto actual."""
    with fabrica_sesion() as sesion:
        total = gasto_total(sesion)
    if total >= Decimal(str(configuracion.gasto_tope_usd)):
        logger.error("Presupuesto de IA agotado: %.4f USD", total)
        raise LimiteExcedido(
            "presupuesto_agotado",
            "Se alcanzó el presupuesto de IA del evento. "
            "La solicitud quedó registrada y la atenderá una persona.",
        )
    return total


def _alertar_si_corresponde(total: Decimal) -> bool:
    if total >= Decimal(str(configuracion.gasto_alerta_usd)):
        logger.warning(
            "ALERTA DE PRESUPUESTO: gasto estimado de IA %.4f USD (alerta en %.2f, tope %.2f)",
            total,
            configuracion.gasto_alerta_usd,
            configuracion.gasto_tope_usd,
        )
        return True
    return False


# ---------------------------------------------------------------------------
# Cliente de Claude
# ---------------------------------------------------------------------------

_cliente: anthropic.Anthropic | None = None


def obtener_cliente() -> anthropic.Anthropic:
    global _cliente
    if _cliente is None:
        _cliente = anthropic.Anthropic(
            api_key=configuracion.anthropic_api_key.get_secret_value(),
            max_retries=2,
            timeout=60.0,
        )
    return _cliente


def _caracteres(sistema: str | list | None, mensajes: list[dict]) -> int:
    def largo(contenido) -> int:
        if isinstance(contenido, str):
            return len(contenido)
        if isinstance(contenido, list):  # bloques de contenido
            return sum(len(b.get("text", "")) if isinstance(b, dict) else 0 for b in contenido)
        return 0

    return largo(sistema) + sum(largo(m.get("content")) for m in mensajes)


def llamar_claude(
    tarea: Tarea,
    mensajes: list[dict],
    sistema: str | list | None = None,
    max_tokens: int | None = None,
    sesion_chat: str | None = None,
    pqrsd_id: uuid.UUID | None = None,
    **opciones,
) -> RespuestaIA:
    """Llama a Claude respetando los límites de la tarea y registra el gasto.

    - max_tokens: si se omite, se usa el tope de la tarea; si se pide más, LimiteExcedido.
    - sesion_chat: identificador de la conversación; cuenta para el límite de mensajes.
    - opciones: parámetros extra de messages.create (p. ej. output_config, thinking).
    """
    politica = POLITICAS[tarea]
    if max_tokens is None:
        max_tokens = politica.max_tokens
    if max_tokens > politica.max_tokens:
        raise LimiteExcedido(
            "max_tokens",
            f"La tarea {tarea} admite como máximo {politica.max_tokens} tokens de salida.",
        )
    if _caracteres(sistema, mensajes) > politica.max_caracteres_entrada:
        raise LimiteExcedido(
            "entrada_larga",
            "El texto es demasiado largo para procesarlo. "
            "Resume tu solicitud e inténtalo de nuevo.",
        )

    modelo = modelo_para(tarea)
    verificar_presupuesto()
    if sesion_chat is not None:
        contador_mensajes.registrar(sesion_chat)

    parametros = {"model": modelo, "max_tokens": max_tokens, "messages": mensajes}
    if sistema is not None:
        parametros["system"] = sistema
    parametros["output_config"] = {"effort": politica.esfuerzo}
    parametros.update(opciones)

    try:
        respuesta = obtener_cliente().messages.create(**parametros)
    except anthropic.RateLimitError:
        logger.warning("Claude: límite de peticiones (429) en la tarea %s", tarea)
        raise ErrorIA(
            "El servicio de IA está ocupado. Intenta de nuevo en unos segundos."
        ) from None
    except anthropic.APIStatusError as error:
        # Solo el código: el cuerpo del error podría repetir el contenido enviado.
        logger.error("Claude respondió %s en la tarea %s", error.status_code, tarea)
        raise ErrorIA("El servicio de IA no pudo procesar la solicitud.") from None
    except anthropic.APIConnectionError:
        logger.error("Sin conexión con la API de Claude en la tarea %s", tarea)
        raise ErrorIA("No hay conexión con el servicio de IA. Intenta más tarde.") from None

    uso = respuesta.usage
    entrada = uso.input_tokens or 0
    salida = uso.output_tokens or 0
    cache_escritura = getattr(uso, "cache_creation_input_tokens", None) or 0
    cache_lectura = getattr(uso, "cache_read_input_tokens", None) or 0
    costo = calcular_costo(tarea, entrada, salida, cache_escritura, cache_lectura)

    total = _registrar_consumo(
        ConsumoIA(
            tarea=tarea.value,
            modelo=modelo,
            tokens_entrada=entrada,
            tokens_salida=salida,
            tokens_cache_escritura=cache_escritura,
            tokens_cache_lectura=cache_lectura,
            costo_usd=costo,
            pqrsd_id=pqrsd_id,
        )
    )
    alerta = _alertar_si_corresponde(total)

    truncada = respuesta.stop_reason == "max_tokens"
    rechazada = respuesta.stop_reason == "refusal"
    if truncada:
        logger.warning("Respuesta truncada por max_tokens=%d en la tarea %s", max_tokens, tarea)
    if rechazada:
        logger.warning("Claude declinó responder en la tarea %s", tarea)

    texto = "".join(
        bloque.text for bloque in respuesta.content if getattr(bloque, "type", None) == "text"
    )
    return RespuestaIA(
        texto="" if rechazada else texto,
        tarea=tarea,
        modelo=modelo,
        tokens_entrada=entrada + cache_escritura + cache_lectura,
        tokens_salida=salida,
        costo_usd=costo,
        stop_reason=respuesta.stop_reason,
        truncada=truncada,
        rechazada=rechazada,
        alerta_presupuesto=alerta,
        gasto_total_usd=total,
    )

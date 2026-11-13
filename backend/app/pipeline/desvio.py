"""Desvío de consultas resueltas por la base de conocimiento (US-009).

El ciudadano pregunta en el chat; si la base de conocimiento tiene la
respuesta, el agente la da citando sus fuentes y no hace falta radicar.

Reglas que evitan respuestas inventadas:
1. Si el RAG no encuentra contexto suficiente, NO se llama a Claude: se
   responde un mensaje fijo y se ofrece radicar.
2. Claude solo recibe los fragmentos recuperados y debe citarlos con [F#].
3. Se descarta la respuesta (y se usa el mensaje fijo) si el JSON es
   inválido, si la cobertura es "ninguna" o si no cita ningún fragmento
   recuperado. Las etiquetas que no corresponden a un fragmento se borran.

El historial de cada conversación vive en memoria (AlmacenSesiones), igual
que el conteo de mensajes de costos.py: se pierde al reiniciar el backend.
"""

import re
import threading
import uuid
from collections import OrderedDict
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from sqlalchemy.orm import Session

from app.models import CoberturaDesvio, ConsultaDesvio
from app.models.consulta_desvio import LARGO_MAXIMO_PREGUNTA
from app.pipeline import costos, rag
from app.pipeline.costos import LimiteExcedido, Tarea
from app.pipeline.json_ia import extraer_objeto_json

RUTA_PROMPT = Path(__file__).parent / "prompts" / "desvio.md"

MAX_SESIONES = 10_000
MAX_TURNOS_SESION = 12
TURNOS_PREVIOS_EN_PROMPT = 3
LARGO_BUSQUEDA = 500
LARGO_ASUNTO = 80
LARGO_DESCRIPCION = 4000  # igual al máximo de POST /api/pqrsd

MENSAJE_SIN_CONTEXTO = (
    "No encontré información suficiente en la base de conocimiento del banco para "
    "responder esa duda, y prefiero no darle una respuesta sin respaldo. "
    "Si lo desea, puede radicar una PQRSD para que una persona la atienda."
)
MENSAJE_PARCIAL = (
    "Parte de su consulta no está cubierta por la información disponible. "
    "Si lo desea, puede radicar una PQRSD para que una persona la atienda."
)
MENSAJE_LIMITE_SESION = (
    "Esta conversación llegó al máximo de mensajes permitido. "
    "Puede continuar con una PQRSD y usaremos lo que ya nos contó."
)
MENSAJE_CONTINUAR = (
    "Preparamos una PQRSD con lo que nos contó. Revise el asunto y la descripción, "
    "corríjalos si hace falta y confirme para radicarla."
)
LINEA_NO_RESUELTO = "La respuesta automática del chat no resolvió la duda del ciudadano."

PATRON_ETIQUETA = re.compile(r"\[F(\d+)\]")


# ---------------------------------------------------------------------------
# Sesiones en memoria
# ---------------------------------------------------------------------------


@dataclass
class Turno:
    pregunta: str
    respuesta: str | None = None  # lo que se le mostró al ciudadano


@dataclass
class SesionChat:
    turnos: list[Turno] = field(default_factory=list)
    primer_mensaje: str | None = None  # se conserva aunque se descarten turnos viejos

    def mensajes_ciudadano(self) -> list[str]:
        return [turno.pregunta for turno in self.turnos]


class AlmacenSesiones:
    """Historial por sesión, acotado en sesiones y en turnos. Seguro entre hilos."""

    def __init__(self, max_sesiones: int = MAX_SESIONES, max_turnos: int = MAX_TURNOS_SESION):
        self._sesiones: OrderedDict[str, SesionChat] = OrderedDict()
        self._candado = threading.Lock()
        self._max_sesiones = max_sesiones
        self._max_turnos = max_turnos

    def nueva(self) -> str:
        sesion_id = str(uuid.uuid4())
        with self._candado:
            self._sesiones[sesion_id] = SesionChat()
            self._recortar()
        return sesion_id

    def obtener(self, sesion_id: str | None) -> SesionChat | None:
        if sesion_id is None:
            return None
        with self._candado:
            sesion = self._sesiones.get(sesion_id)
            if sesion is not None:
                self._sesiones.move_to_end(sesion_id)
            return sesion

    def agregar_pregunta(self, sesion_id: str, pregunta: str) -> Turno:
        with self._candado:
            sesion = self._sesiones[sesion_id]
            if sesion.primer_mensaje is None:
                sesion.primer_mensaje = pregunta
            turno = Turno(pregunta=pregunta)
            sesion.turnos.append(turno)
            del sesion.turnos[: -self._max_turnos]
            self._sesiones.move_to_end(sesion_id)
            return turno

    def reiniciar(self) -> None:
        with self._candado:
            self._sesiones.clear()

    def _recortar(self) -> None:
        while len(self._sesiones) > self._max_sesiones:
            self._sesiones.popitem(last=False)


almacen_sesiones = AlmacenSesiones()


# ---------------------------------------------------------------------------
# Resultado de una consulta
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Fuente:
    etiqueta: str
    documento: str
    seccion: str
    fragmento_id: str


@dataclass(frozen=True)
class RespuestaDesvio:
    sesion_id: str
    respuesta: str
    cobertura: CoberturaDesvio
    fuentes: tuple[Fuente, ...] = ()
    ofrecer_radicar: bool = False
    pregunta_resuelto: bool = False


@lru_cache
def prompt_sistema() -> str:
    return RUTA_PROMPT.read_text(encoding="utf-8")


def texto_de_busqueda(sesion: SesionChat) -> str:
    """Los dos últimos mensajes del ciudadano, para entender seguimientos.

    Si pasan de 500 caracteres se conserva el final: el mensaje más reciente pesa más.
    """
    texto = "\n".join(sesion.mensajes_ciudadano()[-2:])
    return texto[-LARGO_BUSQUEDA:]


def _mensaje_usuario(resultado: rag.ResultadoRAG, pregunta: str) -> str:
    return (
        "<fragmentos>\n"
        f"{resultado.como_contexto()}\n"
        "</fragmentos>\n\n"
        "<pregunta>\n"
        f"{pregunta}\n"
        "</pregunta>"
    )


def _armar_mensajes(sesion: SesionChat, resultado: rag.ResultadoRAG) -> list[dict]:
    """Hasta 3 turnos previos completos y, al final, fragmentos + pregunta actual.

    Todo lo que escribe el ciudadano y los fragmentos van en el rol de usuario.
    Los turnos previos entran del más reciente al más antiguo mientras quepan
    en el tope de entrada de la tarea chat, para no provocar un 413.
    """
    *previos, actual = sesion.turnos
    final = _mensaje_usuario(resultado, actual.pregunta)
    disponible = (
        costos.POLITICAS[Tarea.chat].max_caracteres_entrada - len(prompt_sistema()) - len(final)
    )
    completos = [turno for turno in previos if turno.respuesta][-TURNOS_PREVIOS_EN_PROMPT:]
    incluidos: list[Turno] = []
    for turno in reversed(completos):
        largo = len(turno.pregunta) + len(turno.respuesta)
        if largo > disponible:
            break
        disponible -= largo
        incluidos.insert(0, turno)

    mensajes: list[dict] = []
    for turno in incluidos:
        mensajes.append({"role": "user", "content": turno.pregunta})
        mensajes.append({"role": "assistant", "content": turno.respuesta})
    mensajes.append({"role": "user", "content": final})
    return mensajes


def interpretar_salida(texto: str) -> tuple[CoberturaDesvio, str] | None:
    """Lee {"cobertura": ..., "respuesta": ...}. Tolera cercos de código y texto alrededor."""
    datos = extraer_objeto_json(texto)
    if datos is None:
        return None
    respuesta = datos.get("respuesta")
    try:
        cobertura = CoberturaDesvio(datos.get("cobertura"))
    except ValueError:
        return None
    if not isinstance(respuesta, str):
        return None
    return cobertura, respuesta.strip()


def depurar_citas(
    respuesta: str, resultado: rag.ResultadoRAG
) -> tuple[str, tuple[Fuente, ...]]:
    """Borra las etiquetas que no son de un fragmento recuperado y arma las fuentes citadas."""
    total = len(resultado.fragmentos)
    citadas: list[int] = []

    def reemplazar(coincidencia: re.Match) -> str:
        numero = int(coincidencia.group(1))
        if 1 <= numero <= total:
            if numero not in citadas:
                citadas.append(numero)
            return coincidencia.group(0)
        return ""

    texto = PATRON_ETIQUETA.sub(reemplazar, respuesta)
    texto = re.sub(r"[ \t]{2,}", " ", texto)
    texto = re.sub(r"\s+([.,;:])", r"\1", texto).strip()

    fuentes = tuple(
        Fuente(
            etiqueta=f"F{numero}",
            documento=f"{resultado.fragmentos[numero - 1].documento}.md",
            seccion=resultado.fragmentos[numero - 1].seccion,
            fragmento_id=str(resultado.fragmentos[numero - 1].id),
        )
        for numero in citadas
    )
    return texto, fuentes


def _registrar(
    sesion_db: Session,
    sesion_id: str,
    pregunta: str,
    cobertura: CoberturaDesvio,
    fuentes: tuple[Fuente, ...] = (),
) -> None:
    documentos = list(dict.fromkeys(fuente.documento for fuente in fuentes))
    sesion_db.add(
        ConsultaDesvio(
            sesion_id=sesion_id,
            pregunta=pregunta[:LARGO_MAXIMO_PREGUNTA],
            cobertura=cobertura,
            documentos=documentos,
        )
    )
    sesion_db.flush()


def _sin_respaldo(sesion_db, sesion_id, turno, mensaje=MENSAJE_SIN_CONTEXTO) -> RespuestaDesvio:
    turno.respuesta = mensaje
    _registrar(sesion_db, sesion_id, turno.pregunta, CoberturaDesvio.ninguna)
    return RespuestaDesvio(
        sesion_id=sesion_id,
        respuesta=mensaje,
        cobertura=CoberturaDesvio.ninguna,
        ofrecer_radicar=True,
    )


def consultar(sesion_db: Session, sesion_id: str | None, mensaje: str) -> RespuestaDesvio:
    """Responde una duda del ciudadano con la base de conocimiento.

    Si sesion_id es nulo o desconocido (p. ej. tras reiniciar el backend) se
    abre una sesión nueva. No hace commit: lo hace el endpoint.
    """
    sesion = almacen_sesiones.obtener(sesion_id)
    if sesion is None:
        sesion_id = almacen_sesiones.nueva()
        sesion = almacen_sesiones.obtener(sesion_id)
    turno = almacen_sesiones.agregar_pregunta(sesion_id, mensaje)

    resultado = rag.recuperar(sesion_db, texto_de_busqueda(sesion))
    if not resultado.suficiente:
        return _sin_respaldo(sesion_db, sesion_id, turno)

    try:
        salida = costos.llamar_claude(
            Tarea.chat,
            _armar_mensajes(sesion, resultado),
            sistema=[
                {"type": "text", "text": prompt_sistema(), "cache_control": {"type": "ephemeral"}}
            ],
            sesion_chat=sesion_id,
        )
    except LimiteExcedido as error:
        if error.codigo != "mensajes_sesion":
            raise
        return _sin_respaldo(sesion_db, sesion_id, turno, MENSAJE_LIMITE_SESION)

    interpretada = None if salida.rechazada else interpretar_salida(salida.texto)
    if interpretada is None:
        return _sin_respaldo(sesion_db, sesion_id, turno)
    cobertura, respuesta = interpretada
    if cobertura is CoberturaDesvio.ninguna:
        return _sin_respaldo(sesion_db, sesion_id, turno)

    respuesta, fuentes = depurar_citas(respuesta, resultado)
    if not fuentes or not respuesta:
        return _sin_respaldo(sesion_db, sesion_id, turno)

    parcial = cobertura is CoberturaDesvio.parcial
    if parcial:
        respuesta = f"{respuesta}\n\n{MENSAJE_PARCIAL}"
    turno.respuesta = respuesta
    _registrar(sesion_db, sesion_id, turno.pregunta, cobertura, fuentes)
    return RespuestaDesvio(
        sesion_id=sesion_id,
        respuesta=respuesta,
        cobertura=cobertura,
        fuentes=fuentes,
        ofrecer_radicar=parcial,
        pregunta_resuelto=not parcial,
    )


# ---------------------------------------------------------------------------
# Continuar hacia una PQRSD (no la crea: el ciudadano confirma después)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RadicacionSugerida:
    asunto: str
    descripcion: str
    canal: str = "chat"


def sugerir_radicacion(sesion: SesionChat) -> RadicacionSugerida | None:
    """Arma asunto y descripción con lo que escribió el ciudadano. None si no hay historial."""
    mensajes = sesion.mensajes_ciudadano()
    if not mensajes:
        return None
    primero = sesion.primer_mensaje or mensajes[0]
    cuerpo = "Mensajes del ciudadano en el chat:\n" + "\n".join(f"- {m}" for m in mensajes)
    cierre = f"\n\n{LINEA_NO_RESUELTO}"
    # La radicación acepta hasta LARGO_DESCRIPCION caracteres: se recorta el cuerpo.
    espacio = LARGO_DESCRIPCION - len(cierre)
    if len(cuerpo) > espacio:
        cuerpo = cuerpo[: espacio - 1].rstrip() + "…"
    return RadicacionSugerida(asunto=primero[:LARGO_ASUNTO], descripcion=cuerpo + cierre)

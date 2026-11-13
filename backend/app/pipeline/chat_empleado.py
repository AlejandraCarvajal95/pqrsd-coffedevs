"""Chat del empleado para ajustar el borrador conversando (US-021).

El funcionario escribe una instrucción ("hazlo más empático", "explica el
plazo") y el modelo de borrador devuelve una respuesta breve y, si aplica,
la carta completa entre <borrador_propuesto>…</borrador_propuesto> para
aplicarla al editor con un clic. Nada se guarda en el borrador hasta que la
persona lo aplica y guarda: texto_original nunca se toca.

Fuentes y etiquetas:
- Las etiquetas del borrador ([F1], [F2]…) siguen significando lo mismo que
  en borradores.citas. A esos fragmentos se suman los que el RAG recupera
  para la instrucción nueva, numerados a continuación.
- Las etiquetas que no corresponden a una fuente se borran de la respuesta y
  de la propuesta. Las fuentes nuevas que la propuesta usa se agregan a
  borradores.citas, para que el panel pueda mostrarlas.

Costo: usa la tarea "edicion" de costos.py (modelo de borrador). Solo viajan
el caso, el borrador actual, la instrucción y los dos últimos turnos, no todo
el historial. El historial vive en el frontend; el número de instrucciones
por conversación se limita con MAX_MENSAJES_SESION.
"""

import logging
import re
import uuid
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import configuracion
from app.models import PQRSD, Borrador, FragmentoConocimiento
from app.models.pqrsd import ZONA_COLOMBIA
from app.pipeline import costos, rag
from app.pipeline.costos import ErrorIA, LimiteExcedido, Tarea
from app.pipeline.desvio import PATRON_ETIQUETA
from app.pipeline.generador import MESES

logger = logging.getLogger(__name__)

RUTA_PROMPT = Path(__file__).parent / "prompts" / "chat_empleado.md"

INICIO_PROPUESTA = "<borrador_propuesto>"
FIN_PROPUESTA = "</borrador_propuesto>"

ROL_EMPLEADO = "empleado"
ROL_ASISTENTE = "asistente"
TURNOS_PREVIOS_EN_PROMPT = 2  # pares instrucción-respuesta
LARGO_TURNO_PREVIO = 1500

SIN_FRAGMENTOS = (
    "No hay fragmentos de la base de conocimiento para este caso. No cite fuentes ni "
    "agregue normas, plazos, cifras o políticas."
)
MENSAJE_LIMITE = (
    "Esta conversación llegó al máximo de {limite} instrucciones. Aplique la última "
    "propuesta o siga editando el borrador a mano."
)
MENSAJE_SIN_RESPUESTA = "El asistente no pudo responder. Intente con otra instrucción."
MENSAJE_CORTADA = (
    "La propuesta quedó incompleta por su longitud. Pida un cambio más puntual "
    "(por ejemplo, sobre un solo párrafo)."
)


@dataclass(frozen=True)
class Fuente:
    etiqueta: str
    fragmento_id: str
    documento: str
    seccion: str
    similitud: float
    contenido: str | None  # None si el fragmento ya no está en la base
    nueva: bool = False  # no estaba en borradores.citas

    def cita(self) -> dict:
        """Formato de borradores.citas."""
        return {
            "etiqueta": self.etiqueta,
            "fragmento_id": self.fragmento_id,
            "documento": self.documento,
            "seccion": self.seccion,
            "similitud": round(self.similitud, 4),
        }

    def para_el_panel(self) -> dict:
        return {**self.cita(), "contenido": self.contenido, "nueva": self.nueva}


@dataclass(frozen=True)
class RespuestaChat:
    respuesta: str
    borrador_propuesto: str | None
    fuentes: list[dict]  # las que usa la propuesta (o la respuesta, si no hay propuesta)
    mensajes_restantes: int


@lru_cache
def prompt_sistema() -> str:
    return RUTA_PROMPT.read_text(encoding="utf-8")


def _numero(etiqueta: str) -> int | None:
    coincidencia = re.fullmatch(r"F(\d+)", str(etiqueta))
    return int(coincidencia.group(1)) if coincidencia else None


def reunir_fuentes(
    sesion: Session, pqrsd: PQRSD, borrador: Borrador, instruccion: str
) -> list[Fuente]:
    """Las fuentes del borrador (con su etiqueta) más las que el RAG trae para la instrucción."""
    citas = [cita for cita in (borrador.citas or []) if _numero(cita.get("etiqueta")) is not None]
    ids: list[uuid.UUID] = []
    for cita in citas:
        try:
            ids.append(uuid.UUID(str(cita.get("fragmento_id"))))
        except ValueError:
            continue
    contenidos: dict[str, str] = {}
    if ids:
        filas = sesion.execute(
            select(FragmentoConocimiento.id, FragmentoConocimiento.contenido).where(
                FragmentoConocimiento.id.in_(ids)
            )
        ).all()
        contenidos = {str(fila.id): fila.contenido for fila in filas}

    fuentes = [
        Fuente(
            etiqueta=cita["etiqueta"],
            fragmento_id=str(cita.get("fragmento_id")),
            documento=str(cita.get("documento", "")),
            seccion=str(cita.get("seccion", "")),
            similitud=float(cita.get("similitud") or 0),
            contenido=contenidos.get(str(cita.get("fragmento_id"))),
        )
        for cita in citas
    ]
    presentes = {fuente.fragmento_id for fuente in fuentes}
    siguiente = max((_numero(fuente.etiqueta) for fuente in fuentes), default=0) + 1

    # La instrucción va primero: el modelo de embeddings solo "ve" el inicio del texto.
    resultado = rag.recuperar(
        sesion, f"{instruccion}\n{pqrsd.asunto}\n{pqrsd.descripcion}", con_aprendizajes=True
    )
    for fragmento in resultado.fragmentos:
        if str(fragmento.id) in presentes:
            continue
        fuentes.append(
            Fuente(
                etiqueta=f"F{siguiente}",
                fragmento_id=str(fragmento.id),
                documento=fragmento.documento,
                seccion=fragmento.seccion,
                similitud=fragmento.similitud,
                contenido=fragmento.contenido,
                nueva=True,
            )
        )
        siguiente += 1
    return fuentes


def depurar_etiquetas(texto: str, permitidas: set[str]) -> tuple[str, list[str]]:
    """Borra las etiquetas [F#] que no son de una fuente conocida.

    Devuelve el texto limpio y las etiquetas válidas que usa, en orden de aparición.
    """
    usadas: list[str] = []

    def reemplazar(coincidencia: re.Match) -> str:
        etiqueta = f"F{int(coincidencia.group(1))}"
        if etiqueta not in permitidas:
            return ""
        if etiqueta not in usadas:
            usadas.append(etiqueta)
        return f"[{etiqueta}]"

    limpio = PATRON_ETIQUETA.sub(reemplazar, texto)
    limpio = re.sub(r"[ \t]{2,}", " ", limpio)
    limpio = re.sub(r"[ \t]+([.,;:])", r"\1", limpio)
    return limpio.strip(), usadas


def interpretar(texto: str) -> tuple[str, str | None, bool]:
    """Separa la respuesta al funcionario de la carta propuesta.

    Devuelve (respuesta, propuesta o None, incompleta). `incompleta` indica que
    el bloque se abrió y no se cerró (la salida se cortó): no se propone nada.
    """
    inicio = texto.find(INICIO_PROPUESTA)
    if inicio == -1:
        return texto.strip(), None, False
    fin = texto.find(FIN_PROPUESTA, inicio)
    if fin == -1:
        return texto[:inicio].strip(), None, True
    propuesta = texto[inicio + len(INICIO_PROPUESTA) : fin].strip()
    antes, despues = texto[:inicio].strip(), texto[fin + len(FIN_PROPUESTA) :].strip()
    respuesta = "\n\n".join(parte for parte in (antes, despues) if parte)
    return respuesta, propuesta or None, False


def _fecha_larga(momento: datetime) -> str:
    fecha = momento.astimezone(ZONA_COLOMBIA).date()
    return f"{fecha.day} de {MESES[fecha.month - 1]} de {fecha.year}"


def _bloque_fragmentos(fuentes: list[Fuente]) -> str:
    visibles = [fuente for fuente in fuentes if fuente.contenido]
    if not visibles:
        return SIN_FRAGMENTOS
    return "\n\n".join(
        f"[{f.etiqueta}] Fuente: {f.documento} › {f.seccion}\n{f.contenido}" for f in visibles
    )


def mensaje_usuario(
    pqrsd: PQRSD, fuentes: list[Fuente], borrador_actual: str, instruccion: str
) -> str:
    """Caso, fragmentos, borrador e instrucción. Del ciudadano solo va el nombre."""
    fraude = {None: "sin determinar", True: "sí", False: "no"}[pqrsd.riesgo_fraude]
    caso = [
        f"Radicado: {pqrsd.radicado}",
        f"Fecha de hoy: {_fecha_larga(datetime.now(ZONA_COLOMBIA))}",
        f"Tipo: {pqrsd.tipo or 'sin determinar'}",
        f"Área: {pqrsd.area or 'sin determinar'}",
        f"Tema: {(pqrsd.tema or 'sin determinar').replace('_', ' ')}",
        f"Sentimiento: {pqrsd.sentimiento or 'sin determinar'}",
        f"Riesgo de fraude: {fraude}",
        f"Ciudadano: {pqrsd.nombre_ciudadano}",
        f"Asunto: {pqrsd.asunto}",
        f"Descripción: {pqrsd.descripcion}",
    ]
    return (
        "<caso>\n" + "\n".join(caso) + "\n</caso>\n\n"
        f"<fragmentos>\n{_bloque_fragmentos(fuentes)}\n</fragmentos>\n\n"
        f"<borrador_actual>\n{borrador_actual}\n</borrador_actual>\n\n"
        f"<instruccion>\n{instruccion}\n</instruccion>"
    )


def _turnos_previos(historial: list[dict]) -> list[tuple[str, str]]:
    """Los últimos pares (instrucción, respuesta) completos del historial, recortados."""
    pares: list[tuple[str, str]] = []
    pendiente: str | None = None
    for turno in historial:
        texto = str(turno.get("texto", "")).strip()
        if turno.get("rol") == ROL_EMPLEADO:
            pendiente = texto
        elif turno.get("rol") == ROL_ASISTENTE and pendiente and texto:
            pares.append((pendiente[:LARGO_TURNO_PREVIO], texto[:LARGO_TURNO_PREVIO]))
            pendiente = None
    return pares[-TURNOS_PREVIOS_EN_PROMPT:]


def _armar_mensajes(
    pqrsd: PQRSD,
    fuentes: list[Fuente],
    borrador_actual: str,
    instruccion: str,
    historial: list[dict],
) -> tuple[list[dict], list[Fuente]]:
    """Mensajes para el modelo dentro del tope de entrada de la tarea.

    Si no cabe, primero se quitan las fuentes nuevas menos parecidas y después
    los turnos previos. Las fuentes que ya cita el borrador nunca se quitan.
    """
    limite = costos.POLITICAS[Tarea.edicion].max_caracteres_entrada - len(prompt_sistema())
    previos = _turnos_previos(historial)
    fuentes = list(fuentes)

    def largo() -> int:
        final = len(mensaje_usuario(pqrsd, fuentes, borrador_actual, instruccion))
        return final + sum(len(pregunta) + len(respuesta) for pregunta, respuesta in previos)

    while largo() > limite:
        if fuentes and fuentes[-1].nueva:
            fuentes.pop()
        elif previos:
            previos.pop(0)
        else:
            break  # llamar_claude responderá "entrada_larga" con un mensaje claro

    mensajes: list[dict] = []
    for pregunta, respuesta in previos:
        mensajes.append({"role": "user", "content": pregunta})
        mensajes.append({"role": "assistant", "content": respuesta})
    mensajes.append(
        {"role": "user", "content": mensaje_usuario(pqrsd, fuentes, borrador_actual, instruccion)}
    )
    return mensajes, fuentes


def conversar(
    sesion: Session,
    pqrsd: PQRSD,
    borrador: Borrador,
    instruccion: str,
    historial: list[dict] | None = None,
    borrador_actual: str | None = None,
) -> RespuestaChat:
    """Un turno del chat. No hace commit; solo puede cambiar borradores.citas.

    Lanza LimiteExcedido (límite de instrucciones, entrada muy larga o
    presupuesto agotado) y ErrorIA (la API no respondió o el modelo declinó).
    """
    historial = historial or []
    limite = configuracion.max_mensajes_sesion
    usados = sum(1 for turno in historial if turno.get("rol") == ROL_EMPLEADO)
    if usados >= limite:
        raise LimiteExcedido("mensajes_sesion", MENSAJE_LIMITE.format(limite=limite))

    texto_actual = borrador_actual if borrador_actual is not None else borrador.texto_actual
    fuentes = reunir_fuentes(sesion, pqrsd, borrador, instruccion)
    mensajes, fuentes = _armar_mensajes(pqrsd, fuentes, texto_actual, instruccion, historial)

    salida = costos.llamar_claude(
        Tarea.edicion,
        mensajes,
        sistema=[
            {"type": "text", "text": prompt_sistema(), "cache_control": {"type": "ephemeral"}}
        ],
        pqrsd_id=pqrsd.id,
    )
    if salida.rechazada or not salida.texto.strip():
        logger.warning("Chat del empleado sin respuesta para %s", pqrsd.radicado)
        raise ErrorIA(MENSAJE_SIN_RESPUESTA)

    respuesta, propuesta, incompleta = interpretar(salida.texto)
    permitidas = {fuente.etiqueta for fuente in fuentes}
    respuesta, usadas_respuesta = depurar_etiquetas(respuesta, permitidas)
    usadas = usadas_respuesta
    if propuesta is not None:
        propuesta, usadas = depurar_etiquetas(propuesta, permitidas)
        propuesta = propuesta or None
    if incompleta or (salida.truncada and propuesta is None):
        respuesta = f"{respuesta}\n\n{MENSAJE_CORTADA}".strip()

    por_etiqueta = {fuente.etiqueta: fuente for fuente in fuentes}
    if propuesta is not None:
        # Las fuentes nuevas de la propuesta quedan en el borrador para que el panel las muestre.
        ya_guardadas = {cita.get("etiqueta") for cita in (borrador.citas or [])}
        nuevas = [
            por_etiqueta[etiqueta].cita() for etiqueta in usadas if etiqueta not in ya_guardadas
        ]
        if nuevas:
            borrador.citas = [*(borrador.citas or []), *nuevas]
            sesion.flush()

    logger.info(
        "Chat del empleado en %s: propuesta %s, %d fuentes, %d tokens de salida",
        pqrsd.radicado, "sí" if propuesta else "no", len(usadas), salida.tokens_salida,
    )
    return RespuestaChat(
        respuesta=respuesta or "Listo.",
        borrador_propuesto=propuesta,
        fuentes=[por_etiqueta[etiqueta].para_el_panel() for etiqueta in usadas],
        mensajes_restantes=max(limite - usados - 1, 0),
    )

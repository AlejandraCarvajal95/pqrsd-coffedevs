"""Paso 3 del pipeline: borrador de respuesta con citas (US-012 y US-013).

Con la PQRSD ya clasificada:
1. El RAG (pipeline/rag.py) recupera los fragmentos de normativa y políticas.
2. El modelo más capaz (MODELO_BORRADOR, tarea "generador" de costos.py)
   redacta la carta con el prompt de prompts/borrador_pqrsd.md y cita cada
   afirmación con la etiqueta del fragmento: [F1], [F2]…
3. El borrador se guarda en `borradores` con sus citas y sus tokens, y la
   PQRSD pasa a "borrador_listo" para que una persona lo revise.

Reglas que evitan respuestas inventadas:
- El modelo solo recibe los fragmentos que superaron el umbral del RAG. Si no
  hay ninguno, se le dice de forma expresa y el borrador lleva un aviso para
  el analista: no hay soporte en la base de conocimiento.
- Las etiquetas que no corresponden a un fragmento recuperado se borran
  (misma depuración que el chat de desvío).
- Si hay fragmentos pero el borrador no cita ninguno, también lleva aviso.
- Si la API falla, el modelo declina o se agotó el presupuesto, NO se crea
  borrador: la PQRSD sigue "clasificada" y la atiende una persona.
Nunca se envía nada al ciudadano: el borrador siempre espera aprobación humana.
"""

import logging
from datetime import date, datetime
from functools import lru_cache
from pathlib import Path

from sqlalchemy.orm import Session

from app.models import PQRSD, Borrador, EstadoPQRSD
from app.models.pqrsd import ZONA_COLOMBIA
from app.pipeline import costos, rag
from app.pipeline.costos import ErrorIA, LimiteExcedido, Tarea
from app.pipeline.desvio import depurar_citas

logger = logging.getLogger(__name__)

RUTA_PROMPT = Path(__file__).parent / "prompts" / "borrador_pqrsd.md"

MESES = (
    "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
    "septiembre", "octubre", "noviembre", "diciembre",
)  # fmt: skip

# Lo que recibe el modelo cuando el RAG no encontró nada sobre el umbral.
AVISO_SIN_FRAGMENTOS = (
    "No se encontró información pertinente en la base de conocimiento para esta PQRSD. "
    "No cite ninguna fuente ni escriba normas, plazos, cifras o políticas. "
    "Incluya la nota interna e indique qué debe validar el analista."
)

# Avisos que agrega el sistema (no el modelo) al inicio del borrador.
INICIO_AVISO = "[AVISO AUTOMÁTICO DEL SISTEMA]"
FIN_AVISO = "[FIN DEL AVISO]"
AVISO_SIN_CONTEXTO = (
    "Sin contexto suficiente: la base de conocimiento no tiene fragmentos pertinentes para "
    "esta PQRSD. El borrador no tiene respaldo normativo; una persona debe responder de fondo."
)
AVISO_SIN_CITAS = (
    "El borrador no cita ninguno de los fragmentos recuperados. Verifique cada afirmación "
    "contra la normativa y las políticas antes de aprobar."
)
AVISO_TRUNCADO = (
    "El borrador se cortó por el límite de longitud: revise el final y complételo."
)


@lru_cache
def prompt_sistema() -> str:
    return RUTA_PROMPT.read_text(encoding="utf-8")


def _fecha_larga(fecha: date) -> str:
    return f"{fecha.day} de {MESES[fecha.month - 1]} de {fecha.year}"


def _texto_de_fraude(riesgo: bool | None) -> str:
    if riesgo is None:
        return "sin determinar"
    return "sí" if riesgo else "no"


def mensaje_usuario(pqrsd: PQRSD, resultado: rag.ResultadoRAG) -> str:
    """Clasificación, PQRSD y fragmentos, en bloques etiquetados.

    Del ciudadano solo va el nombre (para el saludo): el contacto no hace falta
    para redactar y no se envía a la API.
    """
    hoy = datetime.now(ZONA_COLOMBIA).date()
    radicada = pqrsd.fecha_radicacion
    radicacion = radicada.astimezone(ZONA_COLOMBIA).date() if radicada else hoy
    clasificacion = [
        f"Radicado: {pqrsd.radicado}",
        f"Fecha de radicación: {_fecha_larga(radicacion)}",
        f"Fecha de hoy: {_fecha_larga(hoy)}",
    ]
    if pqrsd.fecha_vencimiento is not None:
        clasificacion.append(
            f"Fecha límite de respuesta: {_fecha_larga(pqrsd.fecha_vencimiento)}"
        )
    clasificacion += [
        f"Tipo: {pqrsd.tipo or 'sin determinar'}",
        f"Área: {pqrsd.area or 'sin determinar'}",
        f"Tema: {(pqrsd.tema or 'sin determinar').replace('_', ' ')}",
        f"Sentimiento: {pqrsd.sentimiento or 'sin determinar'}",
        f"Riesgo de fraude: {_texto_de_fraude(pqrsd.riesgo_fraude)}",
    ]
    fragmentos = resultado.como_contexto() if resultado.suficiente else AVISO_SIN_FRAGMENTOS
    return (
        "<clasificacion>\n" + "\n".join(clasificacion) + "\n</clasificacion>\n\n"
        "<pqrsd>\n"
        f"Ciudadano: {pqrsd.nombre_ciudadano}\n"
        f"Asunto: {pqrsd.asunto}\n"
        f"Descripción: {pqrsd.descripcion}\n"
        "</pqrsd>\n\n"
        f"<fragmentos>\n{fragmentos}\n</fragmentos>"
    )


def _ajustar_al_limite(pqrsd: PQRSD, resultado: rag.ResultadoRAG) -> rag.ResultadoRAG:
    """Quita los fragmentos menos parecidos (los últimos) si la entrada pasa del tope.

    Se quitan del final para que [F1], [F2]… conserven su número.
    """
    limite = costos.POLITICAS[Tarea.generador].max_caracteres_entrada
    while resultado.fragmentos and (
        len(prompt_sistema()) + len(mensaje_usuario(pqrsd, resultado)) > limite
    ):
        restantes = resultado.fragmentos[:-1]
        resultado = rag.ResultadoRAG(
            estado=rag.CON_CONTEXTO if restantes else rag.SIN_CONTEXTO, fragmentos=restantes
        )
    return resultado


def _depurar(texto: str, resultado: rag.ResultadoRAG) -> tuple[str, list[dict]]:
    """Borra las etiquetas sin fragmento y arma borradores.citas con las que sí se usaron.

    Cada cita lleva su etiqueta ("F2") para enlazarla con el texto del borrador.
    """
    limpio, fuentes = depurar_citas(texto, resultado)
    citas = []
    for fuente in fuentes:
        fragmento = resultado.fragmentos[int(fuente.etiqueta[1:]) - 1]
        citas.append({"etiqueta": fuente.etiqueta, **fragmento.cita()})
    return limpio, citas


def _con_avisos(texto: str, avisos: list[str]) -> str:
    if not avisos:
        return texto
    lineas = "\n".join(f"- {aviso}" for aviso in avisos)
    return f"{INICIO_AVISO}\n{lineas}\n{FIN_AVISO}\n\n{texto}"


def generar_borrador(sesion: Session, pqrsd: PQRSD) -> Borrador | None:
    """Redacta y guarda el borrador de una PQRSD clasificada. No hace commit.

    Con éxito: crea el Borrador (texto_original = texto_actual) y deja la PQRSD
    en "borrador_listo". Devuelve None, sin tocar la PQRSD, si la API no
    responde, el modelo declina o se agotó el presupuesto.
    """
    resultado = rag.recuperar(sesion, f"{pqrsd.asunto}\n{pqrsd.descripcion}")
    resultado = _ajustar_al_limite(pqrsd, resultado)

    try:
        respuesta = costos.llamar_claude(
            Tarea.generador,
            [{"role": "user", "content": mensaje_usuario(pqrsd, resultado)}],
            sistema=[
                {"type": "text", "text": prompt_sistema(), "cache_control": {"type": "ephemeral"}}
            ],
            pqrsd_id=pqrsd.id,
        )
    except (ErrorIA, LimiteExcedido) as error:
        motivo = getattr(error, "codigo", type(error).__name__)
        logger.error("No se pudo generar el borrador de %s: %s", pqrsd.radicado, motivo)
        return None

    if respuesta.rechazada or not respuesta.texto.strip():
        logger.warning(
            "Borrador vacío o declinado para %s (stop_reason=%s)",
            pqrsd.radicado, respuesta.stop_reason,
        )
        return None

    texto, citas = _depurar(respuesta.texto, resultado)
    avisos: list[str] = []
    if not resultado.suficiente:
        avisos.append(AVISO_SIN_CONTEXTO)
    elif not citas:
        avisos.append(AVISO_SIN_CITAS)
    if respuesta.truncada:
        avisos.append(AVISO_TRUNCADO)
    texto = _con_avisos(texto, avisos)

    borrador = Borrador(
        pqrsd_id=pqrsd.id,
        texto_original=texto,
        texto_actual=texto,
        citas=citas,
        modelo=respuesta.modelo,
        tokens_entrada=respuesta.tokens_entrada,
        tokens_salida=respuesta.tokens_salida,
    )
    sesion.add(borrador)
    pqrsd.estado = EstadoPQRSD.borrador_listo
    sesion.flush()
    logger.info(
        "Borrador de %s listo: %d citas, contexto %s, %d tokens de salida",
        pqrsd.radicado, len(citas), "suficiente" if resultado.suficiente else "insuficiente",
        respuesta.tokens_salida,
    )
    return borrador

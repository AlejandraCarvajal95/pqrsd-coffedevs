"""Bandeja del empleado (US-017, US-019 y US-020): /api/bandeja, solo con sesión del panel.

- Lista las PQRSD por urgencia (vencimiento más cercano primero) con su
  semáforo y sus días hábiles restantes, y permite filtrarlas.
- Muestra el detalle con la clasificación, el borrador y las fuentes citadas.
- Una persona confirma o corrige la clasificación, edita el borrador y lo
  aprueba. Solo la aprobación deja la PQRSD en "respondida"; el envío al
  ciudadano es simulado (cambia lo que ve en /estado).

texto_original nunca se modifica: las ediciones van a texto_actual con
Borrador.editar y cada acción queda en `revisiones`. No se puede aprobar un
texto que conserve avisos del sistema, notas internas o campos por completar.

También aquí (US-021 y US-023): el chat para ajustar el borrador conversando
(pipeline/chat_empleado.py) y el registro de aprendizajes del equipo como
.md de la base de conocimiento (pipeline/retroalimentacion.py).
"""

import csv
import io
import re
import uuid
from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.api.admin import UsuarioAdmin
from app.db import obtener_sesion
from app.models import (
    PQRSD,
    AccionRevision,
    Borrador,
    EstadoPQRSD,
    FragmentoConocimiento,
    Revision,
    TipoPQRSD,
)
from app.pipeline import (
    chat_empleado,
    dias_habiles,
    generador,
    orquestador,
    retroalimentacion,
)
from app.pipeline.clasificador import AREAS
from app.pipeline.desvio import PATRON_ETIQUETA

router = APIRouter(prefix="/bandeja", tags=["bandeja"])

SesionDB = Annotated[Session, Depends(obtener_sesion)]

MAX_BORRADOR = 12_000
SALTO = chr(10)
BOM = chr(0xFEFF)  # marca de orden de bytes: Excel abre el CSV con tildes
NOTA_INTERNA = "[NOTA INTERNA"
CAMPO_POR_COMPLETAR = "[COMPLETAR"
FIRMA_SIN_COMPLETAR = ("[Nombre del funcionario]", "[Cargo]")

MENSAJE_NO_ENCONTRADA = "No existe una PQRSD con ese número de radicado."
MENSAJE_SIN_BORRADOR = "Esta PQRSD todavía no tiene borrador."
MENSAJE_YA_RESPONDIDA = "Esta PQRSD ya fue respondida y no admite cambios."

COLUMNAS_CSV = (
    "radicado", "fecha_radicacion", "fecha_vencimiento", "estado", "tipo", "area", "tema",
    "sentimiento", "riesgo_fraude", "semaforo", "dias_habiles_restantes", "fecha_respuesta",
    "respuesta_final",
)  # fmt: skip


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------


def _buscar(sesion: Session, radicado: str) -> PQRSD:
    pqrsd = sesion.scalars(
        select(PQRSD).where(PQRSD.radicado == radicado.strip().upper())
    ).first()
    if pqrsd is None:
        raise HTTPException(status_code=404, detail=MENSAJE_NO_ENCONTRADA)
    return pqrsd


def _borrador_vigente(sesion: Session, pqrsd: PQRSD) -> Borrador | None:
    """El borrador más reciente de la PQRSD."""
    return sesion.scalars(
        select(Borrador)
        .where(Borrador.pqrsd_id == pqrsd.id)
        .order_by(Borrador.creado_en.desc(), Borrador.id.desc())
        .limit(1)
    ).first()


def _urgencia(pqrsd: PQRSD) -> dict:
    """Semáforo y días hábiles restantes. Una PQRSD respondida ya no tiene urgencia."""
    if pqrsd.estado == EstadoPQRSD.respondida:
        return {"semaforo": None, "dias_habiles_restantes": None, "vencida": False}
    estado = dias_habiles.semaforo(pqrsd.fecha_vencimiento)
    return {
        "semaforo": estado.color,
        "dias_habiles_restantes": estado.dias_restantes,
        "vencida": estado.vencida,
    }


def avisos_del_sistema(texto: str) -> list[str]:
    """Los avisos que el generador puso al inicio del borrador."""
    inicio = texto.find(generador.INICIO_AVISO)
    fin = texto.find(generador.FIN_AVISO)
    if inicio == -1 or fin < inicio:
        return []
    bloque = texto[inicio + len(generador.INICIO_AVISO) : fin]
    return [linea.strip()[2:] for linea in bloque.splitlines() if linea.strip().startswith("- ")]


def bloqueos_de_aprobacion(texto: str) -> list[str]:
    """Lo que impide aprobar: nada interno ni incompleto puede llegar al ciudadano."""
    bloqueos = []
    if not texto.strip():
        bloqueos.append("El texto de la respuesta está vacío.")
    if generador.INICIO_AVISO in texto or generador.FIN_AVISO in texto:
        bloqueos.append("Retire el aviso automático del sistema.")
    if NOTA_INTERNA in texto:
        bloqueos.append("Retire la nota interna para el analista.")
    if CAMPO_POR_COMPLETAR in texto:
        bloqueos.append("Complete los campos marcados con [COMPLETAR: …].")
    if any(marca in texto for marca in FIRMA_SIN_COMPLETAR):
        bloqueos.append("Complete la firma: nombre y cargo de quien responde.")
    return bloqueos


def texto_para_el_ciudadano(texto: str) -> str:
    """Quita las etiquetas [F#]: son para quien revisa, no para la respuesta final."""
    limpio = PATRON_ETIQUETA.sub("", texto)
    limpio = re.sub(r"[ \t]{2,}", " ", limpio)
    return re.sub(r"[ \t]+([.,;:])", r"\1", limpio).strip()


def _respuestas(sesion: Session, ids: list[uuid.UUID]) -> dict[uuid.UUID, Revision]:
    """La revisión que aprobó cada PQRSD (la más reciente)."""
    if not ids:
        return {}
    filas = sesion.scalars(
        select(Revision)
        .where(Revision.pqrsd_id.in_(ids), Revision.accion == AccionRevision.aprobado)
        .order_by(Revision.creado_en, Revision.id)
    ).all()
    return {revision.pqrsd_id: revision for revision in filas}


def _resumen(pqrsd: PQRSD, con_borrador: bool, respuesta: Revision | None) -> dict:
    return {
        "radicado": pqrsd.radicado,
        "asunto": pqrsd.asunto,
        "nombre_ciudadano": pqrsd.nombre_ciudadano,
        "canal": pqrsd.canal,
        "estado": pqrsd.estado,
        "tipo": pqrsd.tipo,
        "area": pqrsd.area,
        "tema": pqrsd.tema,
        "sentimiento": pqrsd.sentimiento,
        "riesgo_fraude": pqrsd.riesgo_fraude,
        "confianza": pqrsd.confianza,
        "fecha_radicacion": pqrsd.fecha_radicacion,
        "fecha_vencimiento": pqrsd.fecha_vencimiento,
        **_urgencia(pqrsd),
        "requiere_revision": pqrsd.estado == EstadoPQRSD.pendiente_revision_clasificacion,
        "tiene_borrador": con_borrador,
        "fecha_respuesta": respuesta.creado_en if respuesta else None,
    }


def _clave_de_urgencia(item: dict) -> tuple:
    # Sin fecha de vencimiento van al final; a igual fecha, la más antigua primero.
    vencimiento = item["fecha_vencimiento"]
    return (vencimiento is None, vencimiento or datetime.max.date(), item["fecha_radicacion"])


def consultar_bandeja(
    sesion: Session,
    *,
    area: str | None = None,
    estado: EstadoPQRSD | None = None,
    tipo: TipoPQRSD | None = None,
    semaforo: str | None = None,
    riesgo_fraude: bool | None = None,
    q: str | None = None,
    incluir_respondidas: bool = False,
    con_respuesta: bool = False,
) -> list[dict]:
    """PQRSD filtradas y ordenadas por urgencia. La usan la lista, el CSV y las métricas.

    con_respuesta agrega a cada una el texto final aprobado (para el CSV).
    """
    consulta = select(PQRSD)
    if estado is not None:
        consulta = consulta.where(PQRSD.estado == estado)
    elif not incluir_respondidas:
        consulta = consulta.where(PQRSD.estado != EstadoPQRSD.respondida)
    if area:
        consulta = consulta.where(PQRSD.area == area)
    if tipo is not None:
        consulta = consulta.where(PQRSD.tipo == tipo)
    if riesgo_fraude is not None:
        consulta = consulta.where(PQRSD.riesgo_fraude.is_(riesgo_fraude))
    if q and q.strip():
        patron = f"%{q.strip()}%"
        consulta = consulta.where(
            or_(
                PQRSD.radicado.ilike(patron),
                PQRSD.asunto.ilike(patron),
                PQRSD.descripcion.ilike(patron),
                PQRSD.nombre_ciudadano.ilike(patron),
            )
        )
    filas = sesion.scalars(consulta).all()
    ids = [pqrsd.id for pqrsd in filas]
    con_borrador: set[uuid.UUID] = set()
    if ids:
        con_borrador = set(
            sesion.scalars(select(Borrador.pqrsd_id).where(Borrador.pqrsd_id.in_(ids)))
        )
    respuestas = _respuestas(sesion, ids)
    items = []
    for pqrsd in filas:
        respuesta = respuestas.get(pqrsd.id)
        item = _resumen(pqrsd, pqrsd.id in con_borrador, respuesta)
        if con_respuesta:
            item["respuesta_final"] = respuesta.texto_final if respuesta else None
        items.append(item)
    if semaforo:
        items = [item for item in items if item["semaforo"] == semaforo]
    return sorted(items, key=_clave_de_urgencia)


# ---------------------------------------------------------------------------
# Lista y exportación
# ---------------------------------------------------------------------------


@router.get("")
def listar(
    sesion: SesionDB,
    _: UsuarioAdmin,
    area: str | None = None,
    estado: EstadoPQRSD | None = None,
    tipo: TipoPQRSD | None = None,
    semaforo: Annotated[str | None, Query(pattern="^(verde|amarillo|rojo)$")] = None,
    riesgo_fraude: bool | None = None,
    q: Annotated[str | None, Query(max_length=120)] = None,
    incluir_respondidas: bool = False,
) -> dict:
    """PQRSD por urgencia. Sin `estado`, las respondidas solo salen si se piden."""
    items = consultar_bandeja(
        sesion, area=area, estado=estado, tipo=tipo, semaforo=semaforo,
        riesgo_fraude=riesgo_fraude, q=q, incluir_respondidas=incluir_respondidas,
    )  # fmt: skip
    return {
        "total": len(items),
        "items": items,
        "opciones": {
            "areas": list(AREAS),
            "tipos": [valor.value for valor in TipoPQRSD],
            "estados": [valor.value for valor in EstadoPQRSD],
        },
    }


def _celda(valor) -> str:
    """Texto de una celda. Evita que Excel interprete el contenido como fórmula."""
    if valor is None:
        return ""
    if isinstance(valor, bool):
        return "sí" if valor else "no"
    if isinstance(valor, int | float):
        return str(valor)  # un número negativo no es una fórmula
    texto = valor.isoformat() if hasattr(valor, "isoformat") else str(valor)
    return f"'{texto}" if texto.startswith(("=", "+", "-", "@")) else texto


# Va antes de /{radicado} para que "exportar" no se tome como un radicado.
@router.get("/exportar/csv")
def exportar_csv(sesion: SesionDB, _: UsuarioAdmin) -> Response:
    """Todas las PQRSD en CSV (sin nombre ni contacto del ciudadano)."""
    items = consultar_bandeja(sesion, incluir_respondidas=True, con_respuesta=True)

    salida = io.StringIO()
    escritor = csv.writer(salida, lineterminator=SALTO)
    escritor.writerow(COLUMNAS_CSV)
    for item in items:
        escritor.writerow(_celda(item[columna]) for columna in COLUMNAS_CSV)

    nombre = f"pqrsd_{dias_habiles.fecha_colombia():%Y%m%d}.csv"
    return Response(
        content=BOM + salida.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{nombre}"'},
    )


# ---------------------------------------------------------------------------
# Detalle
# ---------------------------------------------------------------------------


def _citas_con_fragmento(sesion: Session, citas: list[dict]) -> list[dict]:
    """Agrega a cada cita el texto exacto del fragmento que la respalda."""
    ids = []
    for cita in citas:
        try:
            ids.append(uuid.UUID(str(cita.get("fragmento_id"))))
        except ValueError:
            continue
    contenidos: dict[uuid.UUID, str] = {}
    if ids:
        filas = sesion.execute(
            select(FragmentoConocimiento.id, FragmentoConocimiento.contenido).where(
                FragmentoConocimiento.id.in_(ids)
            )
        ).all()
        contenidos = {fila.id: fila.contenido for fila in filas}
    return [
        {**cita, "contenido": contenidos.get(_uuid_o_none(cita.get("fragmento_id")))}
        for cita in citas
    ]


def _uuid_o_none(valor) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(valor))
    except ValueError:
        return None


def _detalle(sesion: Session, pqrsd: PQRSD) -> dict:
    borrador = _borrador_vigente(sesion, pqrsd)
    respuesta = _respuestas(sesion, [pqrsd.id]).get(pqrsd.id)
    revisiones = sesion.scalars(
        select(Revision).where(Revision.pqrsd_id == pqrsd.id).order_by(Revision.creado_en)
    ).all()
    detalle_clasificacion = pqrsd.clasificacion_detalle or {}
    claude = detalle_clasificacion.get("claude") or {}
    return {
        **_resumen(pqrsd, borrador is not None, respuesta),
        "contacto": pqrsd.contacto,
        "descripcion": pqrsd.descripcion,
        "clasificacion": {
            "tipo": pqrsd.tipo,
            "area": pqrsd.area,
            "tema": pqrsd.tema,
            "sentimiento": pqrsd.sentimiento,
            "riesgo_fraude": pqrsd.riesgo_fraude,
            "confianza": pqrsd.confianza,
            "justificacion": claude.get("justificacion"),
            "motivos_revision": detalle_clasificacion.get("motivos_revision") or [],
            "tipos_candidatos": detalle_clasificacion.get("tipos_candidatos") or [],
            "revision_humana": detalle_clasificacion.get("revision_humana"),
        },
        "borrador": None
        if borrador is None
        else {
            "id": borrador.id,
            "texto_original": borrador.texto_original,
            "texto_actual": borrador.texto_actual,
            "editado": borrador.texto_actual != borrador.texto_original,
            "avisos": avisos_del_sistema(borrador.texto_actual),
            "bloqueos_aprobacion": bloqueos_de_aprobacion(borrador.texto_actual),
            "citas": _citas_con_fragmento(sesion, borrador.citas or []),
            "modelo": borrador.modelo,
            "tokens_entrada": borrador.tokens_entrada,
            "tokens_salida": borrador.tokens_salida,
            "creado_en": borrador.creado_en,
        },
        "respuesta": None
        if respuesta is None
        else {
            "texto_final": respuesta.texto_final,
            "revisor": respuesta.revisor,
            "fecha": respuesta.creado_en,
        },
        "revisiones": [
            {"accion": r.accion, "revisor": r.revisor, "fecha": r.creado_en} for r in revisiones
        ],
        "opciones": {"areas": list(AREAS), "tipos": [valor.value for valor in TipoPQRSD]},
    }


@router.get("/{radicado}")
def detalle(radicado: str, sesion: SesionDB, _: UsuarioAdmin) -> dict:
    return _detalle(sesion, _buscar(sesion, radicado))


# ---------------------------------------------------------------------------
# Acciones de la persona que revisa
# ---------------------------------------------------------------------------


class EntradaClasificacion(BaseModel):
    tipo: TipoPQRSD
    area: str

    @field_validator("area")
    @classmethod
    def _area_valida(cls, valor: str) -> str:
        if valor not in AREAS:
            raise ValueError("no es un área del banco")
        return valor


class EntradaBorrador(BaseModel):
    texto: str = Field(min_length=1, max_length=MAX_BORRADOR)

    @field_validator("texto")
    @classmethod
    def _no_vacio(cls, valor: str) -> str:
        if not valor.strip():
            raise ValueError("no puede estar vacío")
        return valor


class EntradaAprobacion(BaseModel):
    # Opcional: el texto final si la persona lo editó y aprueba en un solo paso.
    texto: str | None = Field(default=None, max_length=MAX_BORRADOR)


def _editar(borrador: Borrador, texto: str, revisor: str) -> None:
    """Edición con hora propia: creado_en por defecto es la hora de inicio de la
    transacción, y editar y aprobar en la misma petición quedarían empatados."""
    borrador.editar(texto, revisor=revisor).creado_en = datetime.now(UTC)


def _exigir_abierta(pqrsd: PQRSD) -> None:
    if pqrsd.estado == EstadoPQRSD.respondida:
        raise HTTPException(status_code=409, detail=MENSAJE_YA_RESPONDIDA)


@router.patch("/{radicado}/clasificacion")
def confirmar_clasificacion(
    radicado: str,
    entrada: EntradaClasificacion,
    sesion: SesionDB,
    usuario: UsuarioAdmin,
    tareas: BackgroundTasks,
) -> dict:
    """Una persona confirma o corrige tipo y área. Si no hay borrador, se manda a redactar."""
    pqrsd = _buscar(sesion, radicado)
    _exigir_abierta(pqrsd)
    con_borrador = _borrador_vigente(sesion, pqrsd) is not None

    anterior = {"tipo": pqrsd.tipo, "area": pqrsd.area, "estado": pqrsd.estado}
    pqrsd.tipo = entrada.tipo
    pqrsd.area = entrada.area
    pqrsd.estado = EstadoPQRSD.borrador_listo if con_borrador else EstadoPQRSD.clasificada
    # El plazo depende del tipo: con el tipo confirmado se recalcula el vencimiento.
    pqrsd.fecha_vencimiento = dias_habiles.calcular_vencimiento(
        pqrsd.fecha_radicacion, [entrada.tipo]
    )
    # Se reasigna el diccionario completo para que SQLAlchemy detecte el cambio del JSONB.
    pqrsd.clasificacion_detalle = {
        **(pqrsd.clasificacion_detalle or {}),
        "motivos_revision": [],
        "revision_humana": {
            "revisor": usuario,
            "fecha": datetime.now(dias_habiles.ZONA_COLOMBIA).isoformat(timespec="seconds"),
            "tipo_anterior": anterior["tipo"],
            "area_anterior": anterior["area"],
        },
    }
    sesion.commit()

    if not con_borrador:
        tareas.add_task(orquestador.redactar_borrador, pqrsd.id)
    return {**_detalle(sesion, pqrsd), "borrador_en_proceso": not con_borrador}


@router.post("/{radicado}/borrador/generar", status_code=202)
def generar_borrador(
    radicado: str, sesion: SesionDB, _: UsuarioAdmin, tareas: BackgroundTasks
) -> dict:
    """Pide el borrador de una PQRSD clasificada que se quedó sin él (p. ej. falló la API)."""
    pqrsd = _buscar(sesion, radicado)
    _exigir_abierta(pqrsd)
    if pqrsd.estado != EstadoPQRSD.clasificada:
        raise HTTPException(
            status_code=409, detail="Primero confirme la clasificación de esta PQRSD."
        )
    if _borrador_vigente(sesion, pqrsd) is not None:
        raise HTTPException(status_code=409, detail="Esta PQRSD ya tiene un borrador.")
    tareas.add_task(orquestador.redactar_borrador, pqrsd.id)
    return {"radicado": pqrsd.radicado, "borrador_en_proceso": True}


@router.put("/{radicado}/borrador")
def editar_borrador(
    radicado: str, entrada: EntradaBorrador, sesion: SesionDB, usuario: UsuarioAdmin
) -> dict:
    """Guarda la edición en texto_actual; texto_original no cambia."""
    pqrsd = _buscar(sesion, radicado)
    _exigir_abierta(pqrsd)
    borrador = _borrador_vigente(sesion, pqrsd)
    if borrador is None:
        raise HTTPException(status_code=404, detail=MENSAJE_SIN_BORRADOR)
    if entrada.texto != borrador.texto_actual:
        _editar(borrador, entrada.texto, usuario)
        sesion.commit()
    return _detalle(sesion, pqrsd)


@router.post("/{radicado}/aprobar")
def aprobar(
    radicado: str,
    sesion: SesionDB,
    usuario: UsuarioAdmin,
    entrada: EntradaAprobacion | None = None,
) -> dict:
    """Aprueba la respuesta: la PQRSD pasa a "respondida" y queda quién aprobó y cuándo."""
    pqrsd = _buscar(sesion, radicado)
    _exigir_abierta(pqrsd)
    borrador = _borrador_vigente(sesion, pqrsd)
    if borrador is None:
        raise HTTPException(status_code=409, detail=MENSAJE_SIN_BORRADOR)

    texto = entrada.texto if entrada and entrada.texto is not None else borrador.texto_actual
    bloqueos = bloqueos_de_aprobacion(texto)
    if bloqueos:
        raise HTTPException(status_code=422, detail="Antes de aprobar: " + " ".join(bloqueos))
    if texto != borrador.texto_actual:
        _editar(borrador, texto, usuario)

    borrador.revisiones.append(
        Revision(
            pqrsd_id=pqrsd.id,
            accion=AccionRevision.aprobado,
            texto_final=texto_para_el_ciudadano(texto),
            revisor=usuario,
            creado_en=datetime.now(UTC),
        )
    )
    pqrsd.estado = EstadoPQRSD.respondida
    sesion.commit()
    return _detalle(sesion, pqrsd)


# ---------------------------------------------------------------------------
# Chat del empleado para ajustar el borrador (US-021)
# ---------------------------------------------------------------------------


class TurnoChat(BaseModel):
    rol: Literal["empleado", "asistente"]
    texto: str = Field(max_length=6000)


class EntradaChat(BaseModel):
    mensaje: str = Field(min_length=1, max_length=1000)
    # La conversación vive en el frontend y llega completa en cada turno.
    historial: list[TurnoChat] = Field(default_factory=list, max_length=60)
    # Lo que la persona tiene en el editor (puede tener cambios sin guardar).
    borrador_actual: str | None = Field(default=None, max_length=MAX_BORRADOR)

    @field_validator("mensaje")
    @classmethod
    def _con_texto(cls, valor: str) -> str:
        if not valor.strip():
            raise ValueError("no puede estar vacío")
        return valor.strip()


@router.post("/{radicado}/chat")
def chat_del_empleado(
    radicado: str, entrada: EntradaChat, sesion: SesionDB, _: UsuarioAdmin
) -> dict:
    """Un turno del chat: respuesta breve y, si aplica, la carta propuesta completa.

    No cambia el texto del borrador: la persona decide si aplica la propuesta.
    Los errores de costos e IA (límite de instrucciones, presupuesto, API) los
    convierten en respuestas claras los manejadores de api/costos.py.
    """
    pqrsd = _buscar(sesion, radicado)
    _exigir_abierta(pqrsd)
    borrador = _borrador_vigente(sesion, pqrsd)
    if borrador is None:
        raise HTTPException(status_code=409, detail=MENSAJE_SIN_BORRADOR)

    salida = chat_empleado.conversar(
        sesion,
        pqrsd,
        borrador,
        entrada.mensaje,
        historial=[turno.model_dump() for turno in entrada.historial],
        borrador_actual=entrada.borrador_actual,
    )
    sesion.commit()  # solo pudo cambiar borradores.citas (fuentes nuevas de la propuesta)
    return {
        "respuesta_asistente": salida.respuesta,
        "borrador_propuesto": salida.borrador_propuesto,
        "fuentes": salida.fuentes,
        "mensajes_restantes": salida.mensajes_restantes,
    }


# ---------------------------------------------------------------------------
# Aprendizajes del equipo en la base de conocimiento (US-023)
# ---------------------------------------------------------------------------


class EntradaRetroalimentacion(BaseModel):
    titulo: str = Field(min_length=3, max_length=120)
    contenido: str = Field(min_length=10, max_length=3000)
    area: str | None = Field(default=None, max_length=120)

    @field_validator("titulo", "contenido")
    @classmethod
    def _con_texto(cls, valor: str) -> str:
        if not valor.strip():
            raise ValueError("no puede estar vacío")
        return valor.strip()

    @field_validator("area")
    @classmethod
    def _area_valida(cls, valor: str | None) -> str | None:
        if valor is None or not valor.strip():
            return None
        if valor not in AREAS:
            raise ValueError("no es un área del banco")
        return valor


@router.post("/{radicado}/retroalimentacion", status_code=201)
def guardar_retroalimentacion(
    radicado: str, entrada: EntradaRetroalimentacion, sesion: SesionDB, usuario: UsuarioAdmin
) -> dict:
    """Guarda un criterio aprendido como .md y lo indexa de inmediato en pgvector.

    Se puede usar durante la revisión o después de aprobar. No toca la PQRSD.
    """
    pqrsd = _buscar(sesion, radicado)
    try:
        aprendizaje = retroalimentacion.guardar_aprendizaje(
            sesion,
            radicado=pqrsd.radicado,
            titulo=entrada.titulo,
            contenido=entrada.contenido,
            area=entrada.area or pqrsd.area,
            autor=usuario,
        )
    except retroalimentacion.ErrorRetroalimentacion as error:
        raise HTTPException(status_code=503, detail=str(error)) from None
    sesion.commit()
    return {
        "archivo": aprendizaje.archivo,
        "documento": aprendizaje.documento,
        "fragmentos_indexados": aprendizaje.fragmentos_indexados,
        "total_fragmentos": aprendizaje.total_fragmentos,
        "mensaje": "Aprendizaje guardado. La base de conocimiento ya lo tiene disponible.",
    }

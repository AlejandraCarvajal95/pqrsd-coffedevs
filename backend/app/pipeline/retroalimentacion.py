"""Aprendizajes del equipo como documentos de la base de conocimiento (US-023).

Cuando una persona corrige un borrador y quiere que el criterio sirva para
casos futuros, lo registra aquí. Se guarda como un `.md` en
data/conocimiento/retroalimentacion/ y se indexa de inmediato en pgvector,
sin tocar los demás fragmentos: el siguiente borrador o respuesta del chat
ya puede recuperarlo y citarlo.

- El archivo es la fuente de verdad: data/scripts/cargar_conocimiento.py
  también lee esa carpeta, así que una recarga completa no pierde nada.
- El nombre del archivo lo arma el sistema (fecha, radicado y un resumen del
  título); nada de lo que escribe la persona llega a la ruta.
- Los encabezados Markdown del contenido se convierten en texto plano para
  que el aprendizaje sea una sola sección citable.
- Si el archivo se guarda y la indexación falla, el archivo se borra: no
  quedan aprendizajes a medias.

En Docker la carpeta se monta con escritura (docker-compose.yml). En Linux el
backend corre con un usuario sin privilegios: la carpeta del servidor debe
permitirle escribir (ver README).
"""

import logging
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import configuracion
from app.models import FragmentoConocimiento
from app.models.pqrsd import ZONA_COLOMBIA
from app.pipeline.conocimiento import ResumenCarga, fragmentar_markdown, sincronizar_documento
from app.pipeline.generador import MESES

logger = logging.getLogger(__name__)

PREFIJO = "retro"
AREA_GENERAL = "General"
LARGO_RESUMEN_NOMBRE = 40
MAX_VARIANTES_NOMBRE = 50

MENSAJE_SIN_ESCRITURA = (
    "No se pudo guardar el aprendizaje: la carpeta de retroalimentación no admite escritura. "
    "Revise el montaje y los permisos de data/conocimiento/retroalimentacion (ver README)."
)


class ErrorRetroalimentacion(Exception):
    """No se pudo guardar el aprendizaje. El mensaje se puede mostrar a la persona."""


@dataclass(frozen=True)
class Aprendizaje:
    archivo: str
    documento: str
    fragmentos_indexados: int
    total_fragmentos: int


def resumir_para_nombre(texto: str) -> str:
    """"Reversión de cobros dobles" -> "reversion-de-cobros-dobles" (solo a-z, 0-9 y guiones)."""
    ascii_ = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().lower()
    resumen = re.sub(r"[^a-z0-9]+", "-", ascii_).strip("-")
    return resumen[:LARGO_RESUMEN_NOMBRE].strip("-") or "aprendizaje"


def _una_linea(texto: str) -> str:
    return re.sub(r"\s+", " ", texto.replace("#", " ")).strip()


def _sin_encabezados(texto: str) -> str:
    """Quita los '#' iniciales de cada línea y las líneas en blanco repetidas."""
    lineas = [re.sub(r"^\s*#+\s*", "", linea).rstrip() for linea in texto.strip().splitlines()]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lineas)).strip()


def armar_markdown(
    *, titulo: str, contenido: str, area: str, radicado: str, autor: str, momento: datetime
) -> str:
    fecha = momento.astimezone(ZONA_COLOMBIA).date()
    fecha_larga = f"{fecha.day} de {MESES[fecha.month - 1]} de {fecha.year}"
    return (
        f"# Aprendizaje del equipo: {titulo}\n\n"
        f"## {titulo}\n\n"
        f"Área: {area}. Criterio interno de Banco Andino Ficticio registrado por {autor} "
        f"el {fecha_larga}, a partir del radicado {radicado}.\n\n"
        f"{contenido}\n"
    )


def _crear_archivo(directorio: Path, base: str, texto: str) -> Path:
    """Crea el archivo sin sobrescribir uno existente (agrega -2, -3… si hace falta)."""
    try:
        directorio.mkdir(parents=True, exist_ok=True)
        for variante in range(1, MAX_VARIANTES_NOMBRE + 1):
            sufijo = "" if variante == 1 else f"-{variante}"
            ruta = directorio / f"{base}{sufijo}.md"
            try:
                with ruta.open("x", encoding="utf-8", newline="\n") as archivo:
                    archivo.write(texto)
                return ruta
            except FileExistsError:
                continue
    except OSError as error:
        logger.error("No se pudo escribir en la carpeta de retroalimentación: %s", error)
        raise ErrorRetroalimentacion(MENSAJE_SIN_ESCRITURA) from None
    raise ErrorRetroalimentacion("Ya hay demasiados aprendizajes con ese nombre para hoy.")


def guardar_aprendizaje(
    sesion: Session,
    *,
    radicado: str,
    titulo: str,
    contenido: str,
    area: str | None,
    autor: str,
    directorio: Path | None = None,
    momento: datetime | None = None,
) -> Aprendizaje:
    """Escribe el .md y sincroniza sus fragmentos en pgvector. No hace commit."""
    titulo = _una_linea(titulo)
    contenido = _sin_encabezados(contenido)
    if not titulo or not contenido:
        raise ErrorRetroalimentacion("El aprendizaje necesita un título y un contenido.")

    momento = momento or datetime.now(ZONA_COLOMBIA)
    directorio = directorio or Path(configuracion.retroalimentacion_dir)
    fecha = momento.astimezone(ZONA_COLOMBIA)
    base = f"{PREFIJO}_{fecha:%Y%m%d}_{radicado}_{resumir_para_nombre(titulo)}"
    texto = armar_markdown(
        titulo=titulo,
        contenido=contenido,
        area=area or AREA_GENERAL,
        radicado=radicado,
        autor=autor,
        momento=momento,
    )

    ruta = _crear_archivo(directorio, base, texto)
    documento = ruta.stem
    try:
        fragmentos = fragmentar_markdown(texto, documento)
        sincronizar_documento(sesion, documento, fragmentos, ResumenCarga())
    except Exception:
        ruta.unlink(missing_ok=True)  # sin índice no debe quedar el archivo
        logger.exception("Falló la indexación del aprendizaje %s", documento)
        raise

    total = sesion.scalar(select(func.count()).select_from(FragmentoConocimiento)) or 0
    logger.info("Aprendizaje %s indexado: %d fragmentos", documento, len(fragmentos))
    return Aprendizaje(
        archivo=ruta.name,
        documento=documento,
        fragmentos_indexados=len(fragmentos),
        total_fragmentos=total,
    )

"""Carga de la base de conocimiento en pgvector (US-005).

Divide cada Markdown por sus encabezados `##` (y `###` dentro de ellos), arma
fragmentos cortos que caben en la ventana del modelo de embeddings y los
sincroniza con la tabla fragmentos_conocimiento.

Idempotencia: cada fragmento se identifica por (documento, seccion, indice),
que es la restricción única de la tabla. Al cargar de nuevo:
- si el contenido no cambió, no se hace nada (ni se recalcula el embedding);
- si cambió, se actualiza la fila (conserva su id);
- si un fragmento ya no existe en el archivo, se borra.
El script de data/scripts/cargar_conocimiento.py usa este módulo.
"""

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import FragmentoConocimiento
from app.pipeline import embeddings

logger = logging.getLogger(__name__)

# El modelo por defecto trunca a 128 tokens (unos 450-550 caracteres en
# español). Con ~700 caracteres el título, la sección y el inicio del
# fragmento siempre quedan dentro de lo que el modelo "ve".
MAX_CARACTERES = 700
SECCION_ENCABEZADO = "Encabezado"  # texto antes del primer "##"
SEPARADOR_SECCION = " › "
LARGO_MAXIMO_SECCION = 300  # tamaño de la columna seccion


@dataclass(frozen=True)
class FragmentoMarkdown:
    documento: str
    titulo_documento: str
    seccion: str
    indice: int
    contenido: str

    def texto_para_embedding(self) -> str:
        """Lo que se convierte en vector: incluye el contexto del documento y la sección."""
        return f"{self.titulo_documento}. {self.seccion}.\n{self.contenido}"


def _limpiar_titulo(texto: str) -> str:
    # Quita negritas y escapes que deja la exportación desde Google Docs (\-, \.).
    return re.sub(r"\s+", " ", texto.replace("**", "").replace("\\", "")).strip()


def _partir_bloque(bloque: str, max_caracteres: int) -> list[str]:
    """Parte un bloque más largo que el máximo. Las tablas repiten su encabezado."""
    if len(bloque) <= max_caracteres:
        return [bloque]
    lineas = bloque.split("\n")
    es_tabla = len(lineas) > 2 and all(linea.lstrip().startswith("|") for linea in lineas)
    cabecera = lineas[:2] if es_tabla else []
    cuerpo = lineas[2:] if es_tabla else lineas

    piezas: list[str] = []
    actual: list[str] = list(cabecera)
    for linea in cuerpo:
        # Una sola línea gigante se corta por palabras.
        while len(linea) > max_caracteres:
            corte = linea.rfind(" ", 0, max_caracteres)
            corte = corte if corte > 0 else max_caracteres
            piezas.append(linea[:corte].strip())
            linea = linea[corte:].strip()
        candidato = "\n".join([*actual, linea])
        if len(candidato) > max_caracteres and len(actual) > len(cabecera):
            piezas.append("\n".join(actual))
            actual = [*cabecera, linea]
        else:
            actual.append(linea)
    if len(actual) > len(cabecera):
        piezas.append("\n".join(actual))
    return piezas


def _empaquetar(lineas: list[str], max_caracteres: int) -> list[str]:
    """Agrupa párrafos (separados por línea en blanco) sin pasar del máximo."""
    texto = "\n".join(lineas).strip()
    if not texto:
        return []
    bloques: list[str] = []
    for bloque in re.split(r"\n\s*\n", texto):
        bloque = bloque.strip()
        if bloque:
            bloques.extend(_partir_bloque(bloque, max_caracteres))

    trozos: list[str] = []
    actual = ""
    for bloque in bloques:
        candidato = f"{actual}\n\n{bloque}" if actual else bloque
        if actual and len(candidato) > max_caracteres:
            trozos.append(actual)
            actual = bloque
        else:
            actual = candidato
    if actual:
        trozos.append(actual)
    return trozos


def fragmentar_markdown(
    texto: str, documento: str, max_caracteres: int = MAX_CARACTERES
) -> list[FragmentoMarkdown]:
    """Divide un Markdown en fragmentos citables.

    - `# Título` (el primero) es el título del documento.
    - Cada `## Sección` abre una sección; cada `### Subsección` se cita como
      "Sección › Subsección".
    - El índice cuenta los fragmentos dentro de cada sección, empezando en 0.
    """
    titulo = documento
    # Lista ordenada de (nombre de sección, líneas).
    secciones: list[tuple[str, list[str]]] = [(SECCION_ENCABEZADO, [])]
    seccion_principal = SECCION_ENCABEZADO
    titulo_visto = False

    for linea in texto.splitlines():
        if linea.startswith("# ") and not titulo_visto:
            titulo = _limpiar_titulo(linea[2:]) or documento
            titulo_visto = True
        elif linea.startswith("## "):
            seccion_principal = _limpiar_titulo(linea[3:])
            secciones.append((seccion_principal, []))
        elif linea.startswith("### "):
            nombre = f"{seccion_principal}{SEPARADOR_SECCION}{_limpiar_titulo(linea[4:])}"
            secciones.append((nombre, []))
        else:
            secciones[-1][1].append(linea)

    fragmentos: list[FragmentoMarkdown] = []
    vistos: dict[str, int] = {}
    for nombre, lineas in secciones:
        nombre = nombre[:LARGO_MAXIMO_SECCION]
        for contenido in _empaquetar(lineas, max_caracteres):
            # Si dos secciones se llaman igual, el índice sigue contando (sin choques).
            indice = vistos.get(nombre, 0)
            vistos[nombre] = indice + 1
            fragmentos.append(
                FragmentoMarkdown(
                    documento=documento,
                    titulo_documento=titulo,
                    seccion=nombre,
                    indice=indice,
                    contenido=contenido,
                )
            )
    return fragmentos


@dataclass
class ResumenCarga:
    documentos: list[str] = field(default_factory=list)
    nuevos: int = 0
    actualizados: int = 0
    sin_cambios: int = 0
    eliminados: int = 0
    embeddings_calculados: int = 0

    def __str__(self) -> str:
        return (
            f"{len(self.documentos)} documentos: {self.nuevos} fragmentos nuevos, "
            f"{self.actualizados} actualizados, {self.sin_cambios} sin cambios, "
            f"{self.eliminados} eliminados ({self.embeddings_calculados} embeddings calculados)"
        )


def sincronizar_documento(
    sesion: Session,
    documento: str,
    fragmentos: list[FragmentoMarkdown],
    resumen: ResumenCarga,
    forzar: bool = False,
) -> None:
    """Deja en la base exactamente los fragmentos dados para este documento.

    Con forzar=True recalcula todos los embeddings (por ejemplo, si se cambió
    EMBEDDING_MODELO). No hace commit.
    """
    existentes = {
        (fila.seccion, fila.indice): fila
        for fila in sesion.scalars(
            select(FragmentoConocimiento).where(FragmentoConocimiento.documento == documento)
        )
    }
    pendientes = [
        frag
        for frag in fragmentos
        if forzar
        or (frag.seccion, frag.indice) not in existentes
        or existentes[(frag.seccion, frag.indice)].contenido != frag.contenido
    ]
    resumen.sin_cambios += len(fragmentos) - len(pendientes)

    vectores = embeddings.generar_embeddings([frag.texto_para_embedding() for frag in pendientes])
    resumen.embeddings_calculados += len(vectores)

    for frag, vector in zip(pendientes, vectores, strict=True):
        fila = existentes.get((frag.seccion, frag.indice))
        if fila is None:
            sesion.add(
                FragmentoConocimiento(
                    documento=documento,
                    seccion=frag.seccion,
                    indice=frag.indice,
                    contenido=frag.contenido,
                    embedding=vector,
                )
            )
            resumen.nuevos += 1
        else:
            fila.contenido = frag.contenido
            fila.embedding = vector
            resumen.actualizados += 1

    claves_nuevas = {(frag.seccion, frag.indice) for frag in fragmentos}
    for clave, fila in existentes.items():
        if clave not in claves_nuevas:
            sesion.delete(fila)
            resumen.eliminados += 1
    sesion.flush()


def cargar_directorio(
    sesion: Session,
    directorio: Path,
    forzar: bool = False,
    eliminar_huerfanos: bool = False,
) -> ResumenCarga:
    """Sincroniza todos los .md del directorio. No hace commit.

    Con eliminar_huerfanos=True borra los fragmentos de documentos cuyo
    archivo ya no está en el directorio.
    """
    archivos = sorted(directorio.glob("*.md"))
    if not archivos:
        raise FileNotFoundError(f"No hay archivos .md en {directorio}")

    resumen = ResumenCarga()
    for archivo in archivos:
        documento = archivo.stem
        fragmentos = fragmentar_markdown(archivo.read_text(encoding="utf-8"), documento)
        sincronizar_documento(sesion, documento, fragmentos, resumen, forzar=forzar)
        resumen.documentos.append(documento)
        logger.info("%s: %d fragmentos", documento, len(fragmentos))

    if eliminar_huerfanos:
        resultado = sesion.execute(
            delete(FragmentoConocimiento).where(
                FragmentoConocimiento.documento.not_in(resumen.documentos)
            )
        )
        resumen.eliminados += resultado.rowcount or 0
    return resumen

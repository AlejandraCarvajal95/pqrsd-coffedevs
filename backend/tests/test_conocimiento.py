"""US-005: fragmentación de los Markdown y carga idempotente en pgvector."""

from pathlib import Path

from sqlalchemy import func, select

from app.models import FragmentoConocimiento
from app.pipeline.conocimiento import (
    SECCION_ENCABEZADO,
    cargar_directorio,
    fragmentar_markdown,
)

DIRECTORIO_CONOCIMIENTO = Path(__file__).resolve().parents[2] / "data" / "conocimiento"

MARKDOWN = """# Banco de Prueba — Políticas

**Aviso:** documento ficticio.

## 1. Cuota de manejo

La cuota de manejo se cobra cada mes.

## 2. Contrato

### Cláusula 1. Objeto
El banco otorga un cupo de crédito.

### Cláusula 2. Cancelación
El titular puede cancelar la tarjeta sin costo.
"""


def _contar(sesion, documento: str) -> int:
    consulta = select(func.count()).where(FragmentoConocimiento.documento == documento)
    return sesion.scalar(consulta)


def test_fragmenta_por_secciones_y_subsecciones():
    fragmentos = fragmentar_markdown(MARKDOWN, "politicas_prueba")
    secciones = [f.seccion for f in fragmentos]
    assert secciones == [
        SECCION_ENCABEZADO,
        "1. Cuota de manejo",
        "2. Contrato › Cláusula 1. Objeto",
        "2. Contrato › Cláusula 2. Cancelación",
    ]
    assert all(f.titulo_documento == "Banco de Prueba — Políticas" for f in fragmentos)
    assert all(f.documento == "politicas_prueba" for f in fragmentos)
    # El embedding incluye título y sección para no perder contexto.
    assert "Cláusula 2. Cancelación" in fragmentos[-1].texto_para_embedding()


def test_secciones_largas_se_parten_y_las_tablas_repiten_encabezado():
    filas = "\n".join(f"| clave_{n} | Tipo {n} | 15 días hábiles |" for n in range(40))
    texto = f"# Doc\n\n## Plazos\n\n| Clave | Tipo | Plazo |\n| --- | --- | --- |\n{filas}\n"
    fragmentos = fragmentar_markdown(texto, "tabla", max_caracteres=400)
    assert len(fragmentos) > 1
    assert [f.indice for f in fragmentos] == list(range(len(fragmentos)))
    for fragmento in fragmentos:
        assert len(fragmento.contenido) <= 400
        assert fragmento.contenido.startswith("| Clave | Tipo | Plazo |")
    contenido_total = "\n".join(f.contenido for f in fragmentos)
    assert all(f"clave_{n} " in contenido_total for n in range(40))


def test_los_documentos_reales_se_fragmentan_sin_pasar_el_maximo():
    for archivo in DIRECTORIO_CONOCIMIENTO.glob("*.md"):
        fragmentos = fragmentar_markdown(archivo.read_text(encoding="utf-8"), archivo.stem)
        assert fragmentos, archivo.name
        assert all(len(f.contenido) <= 700 for f in fragmentos), archivo.name
        claves = [(f.seccion, f.indice) for f in fragmentos]
        assert len(claves) == len(set(claves)), f"claves repetidas en {archivo.name}"


def test_carga_idempotente(sesion, embedder_falso, tmp_path):
    (tmp_path / "politicas_prueba.md").write_text(MARKDOWN, encoding="utf-8")

    primera = cargar_directorio(sesion, tmp_path)
    total = _contar(sesion, "politicas_prueba")
    assert primera.nuevos == total == 4
    assert primera.embeddings_calculados == 4

    # Segunda corrida: no duplica ni recalcula embeddings.
    segunda = cargar_directorio(sesion, tmp_path)
    assert _contar(sesion, "politicas_prueba") == total
    assert segunda.nuevos == segunda.actualizados == segunda.embeddings_calculados == 0
    assert segunda.sin_cambios == total

    # Cada fragmento conserva documento y sección para citarlo.
    fila = sesion.scalars(
        select(FragmentoConocimiento).where(
            FragmentoConocimiento.seccion == "2. Contrato › Cláusula 2. Cancelación"
        )
    ).one()
    assert fila.documento == "politicas_prueba"
    assert "cancelar la tarjeta" in fila.contenido


def test_cambios_en_el_archivo_actualizan_y_eliminan(sesion, embedder_falso, tmp_path):
    archivo = tmp_path / "politicas_prueba.md"
    archivo.write_text(MARKDOWN, encoding="utf-8")
    cargar_directorio(sesion, tmp_path)
    id_original = sesion.scalars(
        select(FragmentoConocimiento.id).where(
            FragmentoConocimiento.seccion == "1. Cuota de manejo"
        )
    ).one()

    modificado = MARKDOWN.replace("se cobra cada mes", "se cobra cada trimestre")
    modificado = modificado.split("### Cláusula 2.")[0]  # se elimina la cláusula 2
    archivo.write_text(modificado, encoding="utf-8")
    resumen = cargar_directorio(sesion, tmp_path)

    assert resumen.actualizados == 1
    assert resumen.eliminados == 1
    assert resumen.embeddings_calculados == 1
    fila = sesion.get(FragmentoConocimiento, id_original)  # conserva su id
    assert "trimestre" in fila.contenido
    assert _contar(sesion, "politicas_prueba") == 3


def test_eliminar_huerfanos(sesion, embedder_falso, tmp_path):
    (tmp_path / "a.md").write_text(MARKDOWN, encoding="utf-8")
    (tmp_path / "b.md").write_text(MARKDOWN, encoding="utf-8")
    cargar_directorio(sesion, tmp_path)
    (tmp_path / "b.md").unlink()

    cargar_directorio(sesion, tmp_path)
    assert _contar(sesion, "b") == 4  # sin la opción, no se borra nada
    cargar_directorio(sesion, tmp_path, eliminar_huerfanos=True)
    assert _contar(sesion, "b") == 0
    assert _contar(sesion, "a") == 4

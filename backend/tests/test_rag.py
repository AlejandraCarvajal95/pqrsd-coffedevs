"""US-012: recuperación RAG con umbral y caché de consultas."""

import pytest
from sqlalchemy import select

from app.models import CacheEmbeddingConsulta
from app.pipeline.conocimiento import cargar_directorio
from app.pipeline.rag import CON_CONTEXTO, SIN_CONTEXTO, normalizar_consulta, recuperar

MARKDOWN = """# Banco de Prueba

## Cuota de manejo

La cuota de manejo de la tarjeta de crédito se cobra cada mes aunque la tarjeta no se use.

## Reporte en centrales de riesgo

Antes de reportar un incumplimiento en una central de riesgo el banco envía una comunicación previa.

## Seguro de vida

El seguro de vida de saldo deudor se puede cancelar en cualquier momento.
"""


@pytest.fixture
def conocimiento(sesion, embedder_falso, tmp_path):
    (tmp_path / "banco_prueba.md").write_text(MARKDOWN, encoding="utf-8")
    cargar_directorio(sesion, tmp_path)
    embedder_falso.clear()
    return sesion


def test_devuelve_fragmentos_relevantes_con_su_fuente(conocimiento, embedder_falso):
    resultado = recuperar(
        conocimiento, "Me cobraron la cuota de manejo de la tarjeta y no la uso", umbral=0.3
    )
    assert resultado.estado == CON_CONTEXTO
    assert resultado.suficiente
    primero = resultado.fragmentos[0]
    assert primero.seccion == "Cuota de manejo"
    assert primero.documento == "banco_prueba"
    # Ordenados de más a menos parecido y todos sobre el umbral.
    similitudes = [f.similitud for f in resultado.fragmentos]
    assert similitudes == sorted(similitudes, reverse=True)
    assert all(s >= 0.3 for s in similitudes)

    cita = resultado.citas()[0]
    assert cita["documento"] == "banco_prueba" and cita["seccion"] == "Cuota de manejo"
    assert "[F1] Fuente: banco_prueba › Cuota de manejo" in resultado.como_contexto()


def test_sin_fragmentos_sobre_el_umbral_es_sin_contexto(conocimiento):
    resultado = recuperar(conocimiento, "receta del ajiaco santafereño con guascas", umbral=0.3)
    assert resultado.estado == SIN_CONTEXTO
    assert resultado.fragmentos == ()  # nada irrelevante llega al generador
    assert resultado.como_contexto() == SIN_CONTEXTO
    assert resultado.citas() == []


def test_texto_vacio_es_sin_contexto(conocimiento, embedder_falso):
    assert recuperar(conocimiento, "   ").estado == SIN_CONTEXTO
    assert embedder_falso == []


def test_la_misma_consulta_usa_la_cache(conocimiento, embedder_falso):
    consulta = "Quiero cancelar el seguro de vida"
    primera = recuperar(conocimiento, consulta, umbral=0.3)
    assert len(embedder_falso) == 1

    # Mismo texto con espacios distintos: no se vuelve a calcular el embedding.
    segunda = recuperar(conocimiento, "  Quiero   cancelar el\nseguro de vida ", umbral=0.3)
    assert len(embedder_falso) == 1
    assert [f.id for f in segunda.fragmentos] == [f.id for f in primera.fragmentos]

    fila = conocimiento.scalars(select(CacheEmbeddingConsulta)).one()
    conocimiento.refresh(fila)
    assert fila.usos == 2

    recuperar(conocimiento, "Otra consulta distinta sobre el seguro", umbral=0.3)
    assert len(embedder_falso) == 2


def test_normalizar_consulta():
    assert normalizar_consulta("  hola\n\n mundo\t ") == "hola mundo"

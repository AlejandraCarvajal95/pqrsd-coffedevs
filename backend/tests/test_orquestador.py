"""Pipeline completo tras radicar: clasificación híbrida -> RAG -> borrador (US-013).

Claude, el SVM y el modelo de embeddings son falsos: no se gasta presupuesto.
"""

import contextlib
import json

import pytest
from sqlalchemy import select

from app.config import configuracion
from app.models import PQRSD, Borrador, CanalPQRSD, ConsumoIA, EstadoPQRSD
from app.pipeline import dias_habiles, generador, orquestador, svm

CLASIFICACION = json.dumps(
    {
        "tipo": "reclamo",
        "area": "Tarjetas de Crédito",
        "confianza": 0.91,
        "justificacion": "Pide revertir un cobro.",
    }
)
CARTA = "La cuota de manejo se cobra una sola vez cada mes [F1]. Su caso está en estudio."


@pytest.fixture
def pipeline(ia_falsa, conocimiento_banco, monkeypatch):
    """Orquestador sobre la sesión de la prueba, con un SVM que coincide con Claude."""
    monkeypatch.setattr(
        orquestador, "fabrica_sesion", lambda: contextlib.nullcontext(ia_falsa.sesion)
    )
    capas = {"tipo": "reclamo", "area": "tarjetas", "sentimiento": "negativo", "fraude": "no"}
    ia_falsa.capas = capas
    monkeypatch.setattr(
        svm, "predecir", lambda capa, texto: svm.PrediccionCapa(capas[capa], 0.9, {})
    )
    monkeypatch.setattr(svm, "predecir_tema", lambda texto, area: None)
    return ia_falsa


def _radicar(sesion) -> PQRSD:
    pqrsd = PQRSD(
        nombre_ciudadano="Ciudadana Ficticia",
        contacto="ficticia@ejemplo.test",
        asunto="Cobro doble de la cuota de manejo de la tarjeta",
        descripcion="Me cobraron la cuota de manejo de la tarjeta dos veces en el mismo mes.",
        canal=CanalPQRSD.formulario,
    )
    sesion.add(pqrsd)
    sesion.commit()
    return pqrsd


def _borradores(sesion, pqrsd) -> list[Borrador]:
    return sesion.scalars(select(Borrador).where(Borrador.pqrsd_id == pqrsd.id)).all()


def test_radicada_queda_clasificada_y_con_borrador(pipeline):
    cliente = pipeline.usar(CLASIFICACION, CARTA)
    pqrsd = _radicar(pipeline.sesion)

    orquestador.procesar_pqrsd(pqrsd.id)
    pipeline.sesion.refresh(pqrsd)

    assert pqrsd.estado == EstadoPQRSD.borrador_listo
    assert (pqrsd.tipo, pqrsd.area) == ("reclamo", "Tarjetas de Crédito")
    assert pqrsd.sentimiento == "negativo" and pqrsd.riesgo_fraude is False

    (borrador,) = _borradores(pipeline.sesion, pqrsd)
    assert borrador.texto_original == borrador.texto_actual
    assert "[F1]" in borrador.texto_original
    assert [c["etiqueta"] for c in borrador.citas] == ["F1"]
    assert borrador.modelo == "modelo-borrador-de-prueba"

    # Primero el modelo liviano (clasificar) y solo después el más capaz (borrador).
    assert [llamada["model"] for llamada in cliente.llamadas] == [
        "modelo-ligero-de-prueba", "modelo-borrador-de-prueba",
    ]  # fmt: skip
    # El generador recibe la clasificación ya guardada.
    mensaje = cliente.llamadas[1]["messages"][0]["content"]
    assert "Tipo: reclamo" in mensaje and "Área: Tarjetas de Crédito" in mensaje
    tareas = pipeline.sesion.scalars(select(ConsumoIA.tarea).order_by(ConsumoIA.tarea)).all()
    assert tareas == ["clasificador", "generador"]


def test_si_falla_el_borrador_la_clasificacion_no_se_pierde(pipeline, monkeypatch):
    pipeline.usar(CLASIFICACION)
    pqrsd = _radicar(pipeline.sesion)

    def fallar(sesion, pqrsd):
        sesion.add(Borrador(pqrsd_id=pqrsd.id, texto_original="x", texto_actual="x", modelo="m"))
        sesion.flush()
        raise RuntimeError("fallo inesperado al generar")

    monkeypatch.setattr(generador, "generar_borrador", fallar)
    orquestador.procesar_pqrsd(pqrsd.id)  # no propaga el error
    pipeline.sesion.refresh(pqrsd)

    assert pqrsd.estado == EstadoPQRSD.clasificada
    assert pqrsd.area == "Tarjetas de Crédito" and pqrsd.tipo == "reclamo"
    assert _borradores(pipeline.sesion, pqrsd) == []  # lo que quedó a medias se deshace


def test_presupuesto_agotado_tras_clasificar_deja_la_pqrsd_clasificada(pipeline, monkeypatch):
    # El tope es tan bajo que la llamada del clasificador lo agota.
    monkeypatch.setattr(configuracion, "gasto_tope_usd", 0.0001)
    cliente = pipeline.usar(CLASIFICACION, CARTA)
    pqrsd = _radicar(pipeline.sesion)

    orquestador.procesar_pqrsd(pqrsd.id)
    pipeline.sesion.refresh(pqrsd)

    assert len(cliente.llamadas) == 1  # el modelo de borrador no se llegó a llamar
    assert pqrsd.estado == EstadoPQRSD.clasificada
    assert pqrsd.area == "Tarjetas de Crédito"
    assert _borradores(pipeline.sesion, pqrsd) == []


def test_error_de_la_api_en_el_borrador_deja_la_pqrsd_clasificada(pipeline):
    import anthropic
    import httpx

    sin_conexion = anthropic.APIConnectionError(
        request=httpx.Request("POST", "https://api.invalid/v1/messages")
    )
    cliente = pipeline.usar(CLASIFICACION, sin_conexion)
    pqrsd = _radicar(pipeline.sesion)

    orquestador.procesar_pqrsd(pqrsd.id)
    pipeline.sesion.refresh(pqrsd)

    assert len(cliente.llamadas) == 2
    assert pqrsd.estado == EstadoPQRSD.clasificada
    assert _borradores(pipeline.sesion, pqrsd) == []


def test_en_revision_de_clasificacion_no_se_genera_borrador(pipeline):
    # El SVM propone otro tipo con mucha confianza: va a revisión humana.
    pipeline.capas["tipo"] = "queja"
    cliente = pipeline.usar(CLASIFICACION, CARTA)
    pqrsd = _radicar(pipeline.sesion)

    orquestador.procesar_pqrsd(pqrsd.id)
    pipeline.sesion.refresh(pqrsd)

    assert pqrsd.estado == EstadoPQRSD.pendiente_revision_clasificacion
    assert len(cliente.llamadas) == 1  # solo el clasificador
    assert _borradores(pipeline.sesion, pqrsd) == []


def test_sin_contexto_el_borrador_llega_con_aviso(pipeline):
    pipeline.usar(CLASIFICACION, "Acusamos recibo de su solicitud; está en estudio.")
    pqrsd = PQRSD(
        nombre_ciudadano="Ciudadana Ficticia",
        contacto="ficticia@ejemplo.test",
        asunto="Receta del ajiaco",
        descripcion="Quisiera la receta del ajiaco santafereño con guascas.",
        canal=CanalPQRSD.formulario,
    )
    pipeline.sesion.add(pqrsd)
    pipeline.sesion.commit()

    orquestador.procesar_pqrsd(pqrsd.id)
    pipeline.sesion.refresh(pqrsd)

    (borrador,) = _borradores(pipeline.sesion, pqrsd)
    assert pqrsd.estado == EstadoPQRSD.borrador_listo
    assert borrador.citas == []
    assert generador.AVISO_SIN_CONTEXTO in borrador.texto_original


def test_al_clasificar_se_recalcula_el_vencimiento_segun_el_tipo(pipeline, monkeypatch):
    monkeypatch.setattr(configuracion, "plazos_por_tipo", {"reclamo": 10})
    pipeline.usar(CLASIFICACION, CARTA)
    pqrsd = _radicar(pipeline.sesion)
    assert pqrsd.fecha_vencimiento is None  # esta prueba no pasa por el endpoint de radicar

    orquestador.procesar_pqrsd(pqrsd.id)
    pipeline.sesion.refresh(pqrsd)

    radicada = dias_habiles.fecha_colombia(pqrsd.fecha_radicacion)
    assert pqrsd.fecha_vencimiento == dias_habiles.sumar_dias_habiles(radicada, 10)


def test_con_tipo_dudoso_el_vencimiento_usa_el_plazo_mas_corto(pipeline, monkeypatch):
    # Claude dice "reclamo" (15 días) y el SVM "queja" (5 días) con mucha confianza.
    monkeypatch.setattr(configuracion, "plazos_por_tipo", {"queja": 5})
    pipeline.capas["tipo"] = "queja"
    pipeline.usar(CLASIFICACION)
    pqrsd = _radicar(pipeline.sesion)

    orquestador.procesar_pqrsd(pqrsd.id)
    pipeline.sesion.refresh(pqrsd)

    assert pqrsd.estado == EstadoPQRSD.pendiente_revision_clasificacion
    radicada = dias_habiles.fecha_colombia(pqrsd.fecha_radicacion)
    assert pqrsd.fecha_vencimiento == dias_habiles.sumar_dias_habiles(radicada, 5)


def test_redactar_borrador_solo_actua_sobre_clasificadas_sin_borrador(pipeline):
    cliente = pipeline.usar(CARTA)
    pqrsd = _radicar(pipeline.sesion)
    orquestador.redactar_borrador(pqrsd.id)  # recibida: no hace nada
    assert cliente.llamadas == []

    pqrsd.estado = EstadoPQRSD.clasificada
    pqrsd.tipo, pqrsd.area = "reclamo", "Tarjetas de Crédito"
    pipeline.sesion.commit()
    orquestador.redactar_borrador(pqrsd.id)
    orquestador.redactar_borrador(pqrsd.id)  # ya tiene borrador: no repite la llamada
    pipeline.sesion.refresh(pqrsd)

    assert pqrsd.estado == EstadoPQRSD.borrador_listo
    assert len(_borradores(pipeline.sesion, pqrsd)) == 1 and len(cliente.llamadas) == 1

"""US-010: consultar el estado de una PQRSD por radicado (solo datos ficticios)."""

from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.api import estado
from app.db import obtener_sesion
from app.main import app
from app.models import PQRSD, CanalPQRSD, EstadoPQRSD


@pytest.fixture
def cliente(sesion):
    estado.limitador.reiniciar()
    app.dependency_overrides[obtener_sesion] = lambda: sesion
    yield TestClient(app), sesion
    app.dependency_overrides.clear()
    estado.limitador.reiniciar()


def _crear(sesion, **extra) -> PQRSD:
    pqrsd = PQRSD(
        nombre_ciudadano="Ciudadana Ficticia",
        contacto="ficticia@ejemplo.test",
        asunto="Cobro doble secreto-interno",
        descripcion="Me cobraron dos veces.",
        canal=CanalPQRSD.formulario,
        **extra,
    )
    sesion.add(pqrsd)
    sesion.flush()
    sesion.refresh(pqrsd)
    return pqrsd


def test_radicado_valido_muestra_estado_y_vencimiento(cliente):
    http, sesion = cliente
    pqrsd = _crear(sesion, fecha_vencimiento=date(2026, 12, 1))
    respuesta = http.get(f"/api/pqrsd/{pqrsd.radicado}")
    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert datos["radicado"] == pqrsd.radicado
    assert datos["estado"] == "recibida"
    assert datos["etiqueta"] == "Recibida"
    assert datos["fecha_vencimiento"] == "2026-12-01"
    assert datos["fecha_radicacion"]


def test_vencimiento_nulo_mientras_no_se_calcule(cliente):
    http, sesion = cliente
    pqrsd = _crear(sesion)
    assert http.get(f"/api/pqrsd/{pqrsd.radicado}").json()["fecha_vencimiento"] is None


def test_acepta_minusculas_y_espacios(cliente):
    http, sesion = cliente
    pqrsd = _crear(sesion)
    assert http.get(f"/api/pqrsd/{pqrsd.radicado.lower()}%20").status_code == 200


@pytest.mark.parametrize(
    "interno",
    [
        EstadoPQRSD.clasificada,
        EstadoPQRSD.pendiente_revision_clasificacion,
        EstadoPQRSD.asignada,
        EstadoPQRSD.borrador_listo,
    ],
)
def test_pasos_internos_se_ven_como_en_tramite(cliente, interno):
    http, sesion = cliente
    pqrsd = _crear(sesion, estado=interno)
    datos = http.get(f"/api/pqrsd/{pqrsd.radicado}").json()
    assert datos["estado"] == "en_tramite"
    assert datos["etiqueta"] == "En trámite"


def test_al_aprobar_la_respuesta_el_estado_es_respondida(cliente):
    http, sesion = cliente
    pqrsd = _crear(sesion)
    assert http.get(f"/api/pqrsd/{pqrsd.radicado}").json()["estado"] == "recibida"
    pqrsd.estado = EstadoPQRSD.respondida
    sesion.flush()
    datos = http.get(f"/api/pqrsd/{pqrsd.radicado}").json()
    assert datos["estado"] == "respondida"
    assert datos["etiqueta"] == "Respondida"


def test_no_expone_datos_internos_ni_personales(cliente):
    http, sesion = cliente
    pqrsd = _crear(sesion, area="Cartera", confianza=0.9)
    datos = http.get(f"/api/pqrsd/{pqrsd.radicado}").json()
    assert set(datos) == {"radicado", "estado", "etiqueta", "fecha_radicacion", "fecha_vencimiento"}
    cuerpo = str(datos)
    assert "secreto-interno" not in cuerpo
    assert "Ficticia" not in cuerpo


@pytest.mark.parametrize("radicado", ["PQRSD-2026-ZZZZZZ", "no-existe", "123", "PQRSD-2026-"])
def test_radicado_inexistente_da_el_mismo_404_generico(cliente, radicado):
    http, sesion = cliente
    existente = _crear(sesion)
    respuesta = http.get(f"/api/pqrsd/{radicado}")
    assert respuesta.status_code == 404
    assert respuesta.json()["detail"] == estado.MENSAJE_NO_ENCONTRADO
    assert existente.radicado not in respuesta.text


def test_limite_de_consultas_por_ip(cliente):
    http, _ = cliente
    for _ in range(estado.MAX_CONSULTAS_VENTANA):
        assert http.get("/api/pqrsd/PQRSD-2026-ZZZZZZ").status_code == 404
    respuesta = http.get("/api/pqrsd/PQRSD-2026-ZZZZZZ")
    assert respuesta.status_code == 429
    assert respuesta.json()["detail"] == estado.MENSAJE_LIMITE


def test_el_limite_es_por_ip(cliente):
    http, _ = cliente
    for _ in range(estado.MAX_CONSULTAS_VENTANA):
        http.get("/api/pqrsd/PQRSD-2026-ZZZZZZ", headers={"X-Real-IP": "10.0.0.1"})
    otra = http.get("/api/pqrsd/PQRSD-2026-ZZZZZZ", headers={"X-Real-IP": "10.0.0.2"})
    assert otra.status_code == 404

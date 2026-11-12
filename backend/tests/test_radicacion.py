"""US-007: radicar una PQRSD con formulario (solo datos ficticios)."""

import re

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.db import obtener_sesion
from app.main import app
from app.models import PQRSD
from app.models import pqrsd as modelo_pqrsd
from app.pipeline import orquestador

PATRON_RADICADO = re.compile(r"^PQRSD-\d{4}-[ABCDEFGHJKMNPQRSTUVWXYZ23456789]{6}$")

DATOS = {
    "nombre_ciudadano": "Ciudadana Ficticia",
    "contacto": "ficticia@ejemplo.test",
    "asunto": "Cobro de cuota de manejo",
    "descripcion": "Me cobraron la cuota de manejo dos veces en el mismo mes.",
}


@pytest.fixture
def cliente(sesion, monkeypatch):
    disparos: list = []
    monkeypatch.setattr(orquestador, "procesar_pqrsd", disparos.append)
    app.dependency_overrides[obtener_sesion] = lambda: sesion
    yield TestClient(app), disparos, sesion
    app.dependency_overrides.clear()


def _contar(sesion) -> int:
    return sesion.scalar(select(func.count()).select_from(PQRSD))


def test_radicar_crea_la_pqrsd_y_dispara_el_pipeline(cliente):
    http, disparos, sesion = cliente
    respuesta = http.post("/api/pqrsd", json=DATOS)
    assert respuesta.status_code == 201
    datos = respuesta.json()
    assert PATRON_RADICADO.match(datos["radicado"])
    assert datos["estado"] == "recibida"
    assert "radicado" in datos["mensaje"]

    pqrsd = sesion.scalars(select(PQRSD).where(PQRSD.radicado == datos["radicado"])).one()
    assert pqrsd.estado == "recibida"
    assert pqrsd.canal == "formulario"
    assert pqrsd.fecha_radicacion is not None
    assert pqrsd.tipo is None and pqrsd.area is None  # los define el clasificador
    assert disparos == [pqrsd.id]


def test_el_chat_usa_el_mismo_endpoint(cliente):
    http, _, sesion = cliente
    respuesta = http.post("/api/pqrsd", json={**DATOS, "canal": "chat"})
    assert respuesta.status_code == 201
    radicado = respuesta.json()["radicado"]
    assert sesion.scalars(select(PQRSD.canal).where(PQRSD.radicado == radicado)).one() == "chat"


@pytest.mark.parametrize("campo", ["nombre_ciudadano", "contacto", "asunto", "descripcion"])
@pytest.mark.parametrize("valor", ["", "   ", None])
def test_campo_obligatorio_vacio_no_guarda_nada(cliente, campo, valor):
    http, disparos, sesion = cliente
    antes = _contar(sesion)
    cuerpo = {**DATOS, campo: valor}
    if valor is None:
        del cuerpo[campo]
    respuesta = http.post("/api/pqrsd", json=cuerpo)
    assert respuesta.status_code == 422
    datos = respuesta.json()
    assert datos["campos"] == [campo]
    assert datos["detail"].startswith("Revise estos campos:")
    assert _contar(sesion) == antes
    assert disparos == []


@pytest.mark.parametrize("contacto", ["no-es-contacto", "123", "a@b"])
def test_contacto_invalido(cliente, contacto):
    http, _, _ = cliente
    respuesta = http.post("/api/pqrsd", json={**DATOS, "contacto": contacto})
    assert respuesta.status_code == 422
    assert respuesta.json()["campos"] == ["contacto"]


@pytest.mark.parametrize("contacto", ["ficticia@ejemplo.test", "+57 300 000 0000", "601-000-0000"])
def test_contacto_valido(cliente, contacto):
    http, _, _ = cliente
    assert http.post("/api/pqrsd", json={**DATOS, "contacto": contacto}).status_code == 201


def test_descripcion_demasiado_larga(cliente):
    http, _, sesion = cliente
    antes = _contar(sesion)
    respuesta = http.post("/api/pqrsd", json={**DATOS, "descripcion": "x" * 4001})
    assert respuesta.status_code == 422
    assert "x" * 4001 not in respuesta.text  # no se devuelve lo enviado
    assert _contar(sesion) == antes


def test_radicado_repetido_se_reintenta(cliente, monkeypatch):
    http, _, sesion = cliente
    primero = http.post("/api/pqrsd", json=DATOS).json()["radicado"]

    candidatos = iter([primero, "PQRSD-2026-ZZZZZZ"])
    monkeypatch.setattr(modelo_pqrsd, "generar_radicado", lambda: next(candidatos))
    respuesta = http.post("/api/pqrsd", json=DATOS)
    assert respuesta.status_code == 201
    assert respuesta.json()["radicado"] == "PQRSD-2026-ZZZZZZ"


def test_la_sugerencia_del_chat_cabe_en_la_radicacion(cliente):
    """La descripción que arma el chat de desvío nunca supera el máximo del endpoint."""
    from app.api.pqrsd import MAX_DESCRIPCION
    from app.pipeline import desvio

    sesion_chat = desvio.SesionChat()
    for numero in range(12):
        sesion_chat.turnos.append(desvio.Turno(pregunta=f"{numero} " + "x" * 990))
    sugerida = desvio.sugerir_radicacion(sesion_chat)
    assert len(sugerida.descripcion) <= MAX_DESCRIPCION
    assert sugerida.descripcion.endswith(desvio.LINEA_NO_RESUELTO)

    http, _, _ = cliente
    respuesta = http.post(
        "/api/pqrsd",
        json={**DATOS, "asunto": sugerida.asunto, "descripcion": sugerida.descripcion,
              "canal": "chat"},
    )
    assert respuesta.status_code == 201


def test_orquestador_no_falla_con_id_inexistente(sesion, monkeypatch):
    import contextlib
    import uuid

    monkeypatch.setattr(orquestador, "fabrica_sesion", lambda: contextlib.nullcontext(sesion))
    orquestador.procesar_pqrsd(uuid.uuid4())  # solo registra una advertencia

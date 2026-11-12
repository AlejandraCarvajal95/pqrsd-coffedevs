"""US-015: enrutamiento de modelos, límites, contador de gasto y alerta.

No se llama a la API real: el cliente de Claude se reemplaza por uno falso.
"""

import contextlib
import logging
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.config import configuracion
from app.models import ConsumoIA
from app.pipeline import costos
from app.pipeline.costos import (
    POLITICAS,
    ContadorMensajes,
    LimiteExcedido,
    RolModelo,
    Tarea,
    calcular_costo,
    llamar_claude,
)

MENSAJES = [{"role": "user", "content": "Texto ficticio de una PQRSD"}]


class ClienteFalso:
    def __init__(self, entrada=1000, salida=200, stop_reason="end_turn"):
        self.llamadas: list[dict] = []
        self._uso = SimpleNamespace(
            input_tokens=entrada,
            output_tokens=salida,
            cache_creation_input_tokens=0,
            cache_read_input_tokens=0,
        )
        self._stop_reason = stop_reason
        self.messages = self

    def create(self, **parametros):
        self.llamadas.append(parametros)
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text="respuesta ficticia")],
            usage=self._uso,
            stop_reason=self._stop_reason,
        )


@pytest.fixture
def entorno(sesion, monkeypatch):
    """Modelos ficticios, cliente falso y contador de gasto dentro de la sesión de prueba."""
    monkeypatch.setattr(configuracion, "modelo_ligero", "modelo-ligero-de-prueba")
    monkeypatch.setattr(configuracion, "modelo_borrador", "modelo-borrador-de-prueba")
    monkeypatch.setattr(costos, "fabrica_sesion", lambda: contextlib.nullcontext(sesion))
    cliente = ClienteFalso()
    monkeypatch.setattr(costos, "obtener_cliente", lambda: cliente)
    costos.contador_mensajes.reiniciar()
    yield SimpleNamespace(sesion=sesion, cliente=cliente)
    costos.contador_mensajes.reiniciar()


def test_solo_el_generador_usa_el_modelo_capaz():
    assert POLITICAS[Tarea.generador].rol is RolModelo.borrador
    for tarea in (Tarea.clasificador, Tarea.chat, Tarea.edicion):
        assert POLITICAS[tarea].rol is RolModelo.ligero


def test_calcular_costo(monkeypatch):
    monkeypatch.setattr(configuracion, "precio_ligero_entrada_usd_mtok", 1.0)
    monkeypatch.setattr(configuracion, "precio_ligero_salida_usd_mtok", 5.0)
    # 1M de entrada a 1 USD + 1M de salida a 5 USD.
    assert calcular_costo(Tarea.chat, 1_000_000, 1_000_000) == Decimal("6")
    # Caché: escritura 1.25x y lectura 0.1x del precio de entrada.
    assert calcular_costo(Tarea.chat, 0, 0, 1_000_000, 1_000_000) == Decimal("1.35")


def test_enruta_el_modelo_y_registra_el_gasto(entorno):
    clasificacion = llamar_claude(Tarea.clasificador, MENSAJES, sistema="Clasifica")
    borrador = llamar_claude(Tarea.generador, MENSAJES)

    modelos = [llamada["model"] for llamada in entorno.cliente.llamadas]
    assert modelos == ["modelo-ligero-de-prueba", "modelo-borrador-de-prueba"]
    assert entorno.cliente.llamadas[0]["max_tokens"] == POLITICAS[Tarea.clasificador].max_tokens
    assert entorno.cliente.llamadas[0]["system"] == "Clasifica"

    assert clasificacion.texto == "respuesta ficticia"
    assert clasificacion.tokens_entrada == 1000 and clasificacion.tokens_salida == 200
    assert borrador.costo_usd > clasificacion.costo_usd

    filas = entorno.sesion.scalars(select(ConsumoIA).order_by(ConsumoIA.tarea)).all()
    assert [f.tarea for f in filas] == ["clasificador", "generador"]
    assert sum(f.costo_usd for f in filas) == borrador.gasto_total_usd


def test_max_tokens_mayor_al_tope_no_llama_a_la_api(entorno):
    with pytest.raises(LimiteExcedido) as error:
        llamar_claude(Tarea.chat, MENSAJES, max_tokens=POLITICAS[Tarea.chat].max_tokens + 1)
    assert error.value.codigo == "max_tokens"
    assert entorno.cliente.llamadas == []


def test_entrada_demasiado_larga_no_llama_a_la_api(entorno):
    texto = "x" * (POLITICAS[Tarea.chat].max_caracteres_entrada + 1)
    with pytest.raises(LimiteExcedido) as error:
        llamar_claude(Tarea.chat, [{"role": "user", "content": texto}])
    assert error.value.codigo == "entrada_larga"
    assert entorno.cliente.llamadas == []


def test_limite_de_mensajes_por_sesion(entorno, monkeypatch):
    monkeypatch.setattr(configuracion, "max_mensajes_sesion", 2)
    llamar_claude(Tarea.chat, MENSAJES, sesion_chat="chat-1")
    llamar_claude(Tarea.chat, MENSAJES, sesion_chat="chat-1")
    with pytest.raises(LimiteExcedido) as error:
        llamar_claude(Tarea.chat, MENSAJES, sesion_chat="chat-1")
    assert error.value.codigo == "mensajes_sesion"
    assert "formulario" in error.value.mensaje
    assert len(entorno.cliente.llamadas) == 2
    # Otra conversación tiene su propio cupo.
    llamar_claude(Tarea.chat, MENSAJES, sesion_chat="chat-2")


def test_contador_descarta_sesiones_antiguas():
    contador = ContadorMensajes(max_sesiones=2)
    for sesion_chat in ("a", "b", "c"):
        contador.registrar(sesion_chat, limite=5)
    assert contador.restantes("a", limite=5) == 5  # "a" se descartó
    assert contador.restantes("c", limite=5) == 4


def test_alerta_al_llegar_al_umbral(entorno, monkeypatch, caplog):
    monkeypatch.setattr(configuracion, "gasto_alerta_usd", 0.000001)
    with caplog.at_level(logging.WARNING, logger="app.pipeline.costos"):
        respuesta = llamar_claude(Tarea.chat, MENSAJES)
    assert respuesta.alerta_presupuesto
    assert "ALERTA DE PRESUPUESTO" in caplog.text


def test_sin_alerta_bajo_el_umbral(entorno):
    assert not llamar_claude(Tarea.chat, MENSAJES).alerta_presupuesto


def test_tope_de_presupuesto_bloquea_las_llamadas(entorno, monkeypatch):
    llamar_claude(Tarea.generador, MENSAJES)
    monkeypatch.setattr(configuracion, "gasto_tope_usd", 0.000001)
    with pytest.raises(LimiteExcedido) as error:
        llamar_claude(Tarea.chat, MENSAJES)
    assert error.value.codigo == "presupuesto_agotado"
    assert len(entorno.cliente.llamadas) == 1


def test_respuesta_truncada_se_marca(entorno, monkeypatch):
    cliente = ClienteFalso(stop_reason="max_tokens")
    monkeypatch.setattr(costos, "obtener_cliente", lambda: cliente)
    assert llamar_claude(Tarea.chat, MENSAJES).truncada


def test_falta_el_modelo_da_error_claro(entorno, monkeypatch):
    monkeypatch.setattr(configuracion, "modelo_borrador", None)
    with pytest.raises(costos.ErrorIA, match="MODELO_BORRADOR"):
        llamar_claude(Tarea.generador, MENSAJES)


def test_endpoint_de_costos_y_mensaje_de_error(base_inicializada):
    from app.main import app

    with TestClient(app) as cliente:
        respuesta = cliente.get("/api/costos")
    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert set(datos) == {"total_usd", "alerta_usd", "tope_usd", "alerta", "por_tarea"}
    assert datos["alerta_usd"] == configuracion.gasto_alerta_usd

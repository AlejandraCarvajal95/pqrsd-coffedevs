"""US-009: desvío de consultas con la base de conocimiento.

No gasta presupuesto: el cliente de Claude es falso y rag.recuperar se
reemplaza para controlar exactamente qué fragmentos llegan.
"""

import contextlib
import json
import uuid
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.config import configuracion
from app.db import obtener_sesion
from app.main import app
from app.models import PQRSD, ConsultaDesvio
from app.pipeline import costos, desvio, rag
from app.pipeline.rag import CON_CONTEXTO, SIN_CONTEXTO, FragmentoRecuperado, ResultadoRAG

FRAGMENTOS = (
    FragmentoRecuperado(
        id=uuid.uuid4(),
        documento="faq_clientes",
        seccion="Pregunta 1. ¿Por qué me cobraron cuota de manejo si no usé la tarjeta?",
        contenido="La cuota de manejo se cobra mientras la tarjeta esté activa.",
        similitud=0.56,
    ),
    FragmentoRecuperado(
        id=uuid.uuid4(),
        documento="politica_y_contratos",
        seccion="4. Extracto de contrato › Cláusula 6. Cancelación de la tarjeta",
        contenido="La cancelación no genera cobro ni penalización.",
        similitud=0.44,
    ),
)
CON_FRAGMENTOS = ResultadoRAG(estado=CON_CONTEXTO, fragmentos=FRAGMENTOS)
VACIO = ResultadoRAG(estado=SIN_CONTEXTO, fragmentos=())


class ClienteFalso:
    """Imita client.messages.create y devuelve el texto que se le indique."""

    def __init__(self):
        self.texto = json.dumps(
            {"cobertura": "total", "respuesta": "Se cobra mientras esté activa [F1]."}
        )
        self.llamadas: list[dict] = []
        self.messages = self

    def create(self, **parametros):
        self.llamadas.append(parametros)
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text=self.texto)],
            usage=SimpleNamespace(
                input_tokens=900,
                output_tokens=80,
                cache_creation_input_tokens=0,
                cache_read_input_tokens=0,
            ),
            stop_reason="end_turn",
        )


@pytest.fixture
def entorno(sesion, monkeypatch):
    monkeypatch.setattr(configuracion, "modelo_ligero", "modelo-ligero-de-prueba")
    monkeypatch.setattr(costos, "fabrica_sesion", lambda: contextlib.nullcontext(sesion))
    cliente = ClienteFalso()
    monkeypatch.setattr(costos, "obtener_cliente", lambda: cliente)

    rag_falso = SimpleNamespace(resultado=CON_FRAGMENTOS, consultas=[])

    def recuperar(_sesion, texto, k=None, umbral=None):
        rag_falso.consultas.append(texto)
        return rag_falso.resultado

    monkeypatch.setattr(rag, "recuperar", recuperar)
    desvio.almacen_sesiones.reiniciar()
    costos.contador_mensajes.reiniciar()
    app.dependency_overrides[obtener_sesion] = lambda: sesion
    yield SimpleNamespace(
        sesion=sesion, cliente=cliente, rag=rag_falso, http=TestClient(app)
    )
    app.dependency_overrides.clear()
    desvio.almacen_sesiones.reiniciar()
    costos.contador_mensajes.reiniciar()


def _consultar(entorno, mensaje="¿Por qué me cobran la cuota de manejo?", sesion_id=None):
    respuesta = entorno.http.post(
        "/api/chat/consulta", json={"sesion_id": sesion_id, "mensaje": mensaje}
    )
    assert respuesta.status_code == 200, respuesta.text
    return respuesta.json()


def _responder(entorno, cobertura: str, respuesta: str) -> None:
    entorno.cliente.texto = json.dumps({"cobertura": cobertura, "respuesta": respuesta})


# --- Criterio 1: responde citando el documento de origen --------------------


def test_respuesta_con_contexto_cita_el_documento(entorno):
    datos = _consultar(entorno)
    assert datos["cobertura"] == "total"
    assert datos["pregunta_resuelto"] is True
    assert datos["ofrecer_radicar"] is False
    assert "[F1]" in datos["respuesta"]
    assert datos["fuentes"] == [
        {
            "etiqueta": "F1",
            "documento": "faq_clientes.md",
            "seccion": FRAGMENTOS[0].seccion,
            "fragmento_id": str(FRAGMENTOS[0].id),
        }
    ]
    uuid.UUID(datos["sesion_id"])  # el backend genera el identificador

    fila = entorno.sesion.scalars(select(ConsultaDesvio)).one()
    assert fila.cobertura == "total"
    assert fila.documentos == ["faq_clientes.md"]
    assert fila.resultado is None


def test_etiqueta_inexistente_se_elimina(entorno):
    _responder(entorno, "total", "Se cobra cada mes [F1] y hay descuentos [F9].")
    datos = _consultar(entorno)
    assert "[F9]" not in datos["respuesta"]
    assert "[F1]" in datos["respuesta"]
    assert [fuente["etiqueta"] for fuente in datos["fuentes"]] == ["F1"]


def test_cobertura_parcial_ofrece_radicar(entorno):
    _responder(entorno, "parcial", "La cancelación no cuesta [F2]. No tengo el plazo.")
    datos = _consultar(entorno)
    assert datos["cobertura"] == "parcial"
    assert datos["ofrecer_radicar"] is True
    assert datos["pregunta_resuelto"] is False
    assert desvio.MENSAJE_PARCIAL in datos["respuesta"]
    assert datos["fuentes"][0]["documento"] == "politica_y_contratos.md"


def test_cercos_de_codigo_se_toleran(entorno):
    entorno.cliente.texto = (
        '```json\n{"cobertura": "total", "respuesta": "Se cobra mensualmente [F1]."}\n```'
    )
    assert _consultar(entorno)["cobertura"] == "total"


def test_mensaje_y_fragmentos_van_en_el_rol_de_usuario(entorno):
    pregunta = "¿Por qué me cobran la cuota de manejo sin usar la tarjeta?"
    _consultar(entorno, pregunta)
    llamada = entorno.cliente.llamadas[0]
    sistema = "".join(bloque["text"] for bloque in llamada["system"])
    assert pregunta not in sistema
    assert FRAGMENTOS[0].contenido not in sistema
    assert llamada["system"][0]["cache_control"] == {"type": "ephemeral"}

    ultimo = llamada["messages"][-1]
    assert ultimo["role"] == "user"
    assert pregunta in ultimo["content"]
    assert FRAGMENTOS[0].contenido in ultimo["content"]
    assert "[F1] Fuente: faq_clientes" in ultimo["content"]
    assert llamada["model"] == "modelo-ligero-de-prueba"


def test_seguimiento_usa_los_dos_ultimos_mensajes_y_el_historial(entorno):
    primera = _consultar(entorno, "¿Cobran cuota de manejo?")
    _consultar(entorno, "¿Y si cancelo la tarjeta?", primera["sesion_id"])
    assert entorno.rag.consultas[-1] == "¿Cobran cuota de manejo?\n¿Y si cancelo la tarjeta?"
    mensajes = entorno.cliente.llamadas[-1]["messages"]
    assert [m["role"] for m in mensajes] == ["user", "assistant", "user"]
    assert mensajes[0]["content"] == "¿Cobran cuota de manejo?"


# --- Criterio 3: sin información suficiente, lo dice y no inventa -----------


def test_sin_contexto_no_llama_a_claude(entorno):
    entorno.rag.resultado = VACIO
    datos = _consultar(entorno, "¿Cuál es la receta del ajiaco?")
    assert datos["respuesta"] == desvio.MENSAJE_SIN_CONTEXTO
    assert datos["cobertura"] == "ninguna"
    assert datos["ofrecer_radicar"] is True
    assert datos["fuentes"] == []
    assert entorno.cliente.llamadas == []
    assert entorno.sesion.scalars(select(ConsultaDesvio)).one().cobertura == "ninguna"


@pytest.mark.parametrize(
    "texto",
    [
        json.dumps({"cobertura": "ninguna", "respuesta": ""}),
        "esto no es JSON",
        json.dumps({"cobertura": "total", "respuesta": "La cuota cuesta 50.000 pesos."}),
        json.dumps({"cobertura": "total", "respuesta": "Inventado [F7]."}),
        json.dumps({"cobertura": "otra", "respuesta": "Algo [F1]."}),
        json.dumps(["no", "es", "un", "objeto"]),
    ],
    ids=["ninguna", "json_invalido", "sin_citas", "cita_inexistente", "cobertura_rara", "lista"],
)
def test_respuestas_sin_respaldo_usan_el_mensaje_fijo(entorno, texto):
    entorno.cliente.texto = texto
    datos = _consultar(entorno)
    assert datos["respuesta"] == desvio.MENSAJE_SIN_CONTEXTO
    assert datos["cobertura"] == "ninguna"
    assert datos["ofrecer_radicar"] is True
    assert datos["fuentes"] == []


def test_limite_de_mensajes_ofrece_radicar(entorno, monkeypatch):
    monkeypatch.setattr(configuracion, "max_mensajes_sesion", 1)
    primera = _consultar(entorno)
    datos = _consultar(entorno, "Otra pregunta", primera["sesion_id"])
    assert datos["respuesta"] == desvio.MENSAJE_LIMITE_SESION
    assert datos["ofrecer_radicar"] is True
    assert len(entorno.cliente.llamadas) == 1


# --- Criterio 2: si no resuelve, ofrece radicar con el contexto -------------


def test_continuar_sugiere_la_pqrsd_sin_crearla(entorno):
    primera = _consultar(entorno, "Me cobraron cuota de manejo dos veces este mes")
    _consultar(entorno, "Ya llamé y no me solucionaron", primera["sesion_id"])
    pqrsd_antes = entorno.sesion.scalar(select(func.count()).select_from(PQRSD))
    llamadas_antes = len(entorno.cliente.llamadas)

    respuesta = entorno.http.post(
        "/api/chat/continuar", json={"sesion_id": primera["sesion_id"]}
    )
    assert respuesta.status_code == 200
    sugerida = respuesta.json()["radicacion_sugerida"]
    assert sugerida["canal"] == "chat"
    assert sugerida["asunto"] == "Me cobraron cuota de manejo dos veces este mes"
    assert "Me cobraron cuota de manejo dos veces este mes" in sugerida["descripcion"]
    assert "Ya llamé y no me solucionaron" in sugerida["descripcion"]
    assert desvio.LINEA_NO_RESUELTO in sugerida["descripcion"]

    assert entorno.sesion.scalar(select(func.count()).select_from(PQRSD)) == pqrsd_antes
    assert len(entorno.cliente.llamadas) == llamadas_antes  # no llama a Claude
    filas = entorno.sesion.scalars(
        select(ConsultaDesvio).order_by(ConsultaDesvio.creada_en)
    ).all()
    assert [fila.resultado for fila in filas] == [None, "continuo"]


def test_asunto_se_corta_a_80_caracteres(entorno):
    primera = _consultar(entorno, "x" * 200)
    sugerida = entorno.http.post(
        "/api/chat/continuar", json={"sesion_id": primera["sesion_id"]}
    ).json()["radicacion_sugerida"]
    assert sugerida["asunto"] == "x" * 80


def test_continuar_con_sesion_desconocida_o_vacia(entorno):
    desconocida = entorno.http.post("/api/chat/continuar", json={"sesion_id": "no-existe"})
    assert desconocida.status_code == 404
    assert "conversación" in desconocida.json()["detail"]

    vacia = desvio.almacen_sesiones.nueva()
    respuesta = entorno.http.post("/api/chat/continuar", json={"sesion_id": vacia})
    assert respuesta.status_code == 409


# --- Resultado y métricas ---------------------------------------------------


def test_metricas_sin_consultas(entorno):
    datos = entorno.http.get("/api/chat/metricas").json()
    assert datos == {
        "consultas_total": 0,
        "con_respuesta": 0,
        "sin_contexto": 0,
        "resueltas_sin_radicar": 0,
        "continuaron_a_pqrsd": 0,
        "tasa_desvio": 0.0,
    }


def test_resultado_y_metricas(entorno):
    # Sesión A: respuesta total y el ciudadano dice que se resolvió.
    a = _consultar(entorno)
    assert entorno.http.post(
        "/api/chat/resultado", json={"sesion_id": a["sesion_id"], "resolvio": True}
    ).json()["resultado"] == "resuelta"

    # Sesión B: respuesta total, pero no se resolvió.
    b = _consultar(entorno)
    entorno.http.post("/api/chat/resultado", json={"sesion_id": b["sesion_id"], "resolvio": False})

    # Sesión C: sin contexto y continúa hacia una PQRSD.
    entorno.rag.resultado = VACIO
    c = _consultar(entorno, "Una pregunta sin respaldo")
    entorno.http.post("/api/chat/continuar", json={"sesion_id": c["sesion_id"]})

    # Sesión D: sin contexto y no hace nada más.
    _consultar(entorno, "Otra pregunta sin respaldo")

    datos = entorno.http.get("/api/chat/metricas").json()
    assert datos == {
        "consultas_total": 4,
        "con_respuesta": 2,
        "sin_contexto": 2,
        "resueltas_sin_radicar": 1,
        "continuaron_a_pqrsd": 1,
        "tasa_desvio": 0.25,
    }


def test_resultado_con_sesion_desconocida(entorno):
    respuesta = entorno.http.post(
        "/api/chat/resultado", json={"sesion_id": "no-existe", "resolvio": True}
    )
    assert respuesta.status_code == 404


# --- Validación de entrada --------------------------------------------------


@pytest.mark.parametrize("mensaje", ["", "   ", "a" * 1001])
def test_mensajes_vacios_o_largos_dan_422(entorno, mensaje):
    respuesta = entorno.http.post("/api/chat/consulta", json={"mensaje": mensaje})
    assert respuesta.status_code == 422
    assert respuesta.json()["detail"] == "El mensaje debe tener entre 1 y 1000 caracteres."
    assert "a" * 1001 not in respuesta.text  # no se devuelve lo enviado
    assert entorno.cliente.llamadas == []

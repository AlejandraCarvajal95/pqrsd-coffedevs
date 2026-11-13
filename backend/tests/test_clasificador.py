"""US-011: clasificación de tipo, área y confianza (sin llamar a la API real)."""

import contextlib
import json
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.config import configuracion
from app.models import PQRSD, CanalPQRSD, ConsumoIA, EstadoPQRSD
from app.pipeline import clasificador, costos, generador, orquestador, svm
from app.pipeline.costos import ErrorIA, LimiteExcedido

VALIDA = json.dumps(
    {
        "tipo": "reclamo",
        "area": "Tarjetas de Crédito",
        "confianza": 0.91,
        "justificacion": "Pide revertir un cobro.",
    }
)


class ClienteFalso:
    """Devuelve, en orden, los textos indicados (el último se repite)."""

    def __init__(self, *textos: str):
        self.textos = list(textos) or [VALIDA]
        self.llamadas: list[dict] = []
        self.messages = self

    def create(self, **parametros):
        self.llamadas.append(parametros)
        texto = self.textos[min(len(self.llamadas), len(self.textos)) - 1]
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text=texto)],
            usage=SimpleNamespace(
                input_tokens=1200,
                output_tokens=40,
                cache_creation_input_tokens=0,
                cache_read_input_tokens=0,
            ),
            stop_reason="end_turn",
        )


@pytest.fixture
def entorno(sesion, monkeypatch):
    monkeypatch.setattr(configuracion, "modelo_ligero", "modelo-ligero-de-prueba")
    monkeypatch.setattr(configuracion, "modelo_borrador", "modelo-borrador-de-prueba")
    monkeypatch.setattr(costos, "fabrica_sesion", lambda: contextlib.nullcontext(sesion))
    estado = SimpleNamespace(sesion=sesion, cliente=ClienteFalso())
    monkeypatch.setattr(costos, "obtener_cliente", lambda: estado.cliente)

    def usar(*textos):
        estado.cliente = ClienteFalso(*textos)
        return estado.cliente

    estado.usar = usar
    return estado


def _pqrsd(sesion, **extra) -> PQRSD:
    datos = dict(
        nombre_ciudadano="Ciudadano Ficticio",
        contacto="ficticio@ejemplo.test",
        asunto="Cobro doble de cuota de manejo",
        descripcion="Me cobraron la cuota de manejo dos veces en el mismo mes.",
        canal=CanalPQRSD.formulario,
    )
    datos.update(extra)
    pqrsd = PQRSD(**datos)
    sesion.add(pqrsd)
    sesion.flush()
    return pqrsd


# --- Criterio 1: tipo, área y confianza --------------------------------------


def test_clasifica_y_actualiza_la_pqrsd(entorno):
    pqrsd = _pqrsd(entorno.sesion)
    resultado = clasificador.clasificar_pqrsd(entorno.sesion, pqrsd)

    assert resultado.tipo == "reclamo"
    assert pqrsd.tipo == "reclamo"
    assert pqrsd.area == "Tarjetas de Crédito"
    assert pqrsd.confianza == pytest.approx(0.91)
    assert pqrsd.estado == EstadoPQRSD.clasificada

    # Una sola llamada, con el modelo liviano y su gasto registrado con la PQRSD.
    assert len(entorno.cliente.llamadas) == 1
    assert entorno.cliente.llamadas[0]["model"] == "modelo-ligero-de-prueba"
    consumo = entorno.sesion.scalars(select(ConsumoIA)).one()
    assert consumo.tarea == "clasificador"
    assert consumo.pqrsd_id == pqrsd.id


def test_la_pqrsd_va_en_el_rol_de_usuario_y_el_prompt_con_cache(entorno):
    pqrsd = _pqrsd(entorno.sesion)
    clasificador.clasificar_pqrsd(entorno.sesion, pqrsd)
    llamada = entorno.cliente.llamadas[0]
    sistema = llamada["system"][0]
    assert sistema["cache_control"] == {"type": "ephemeral"}
    assert sistema["text"] == clasificador.prompt_sistema()
    assert pqrsd.descripcion not in sistema["text"]
    assert llamada["messages"][-1]["role"] == "user"
    assert pqrsd.descripcion in llamada["messages"][-1]["content"]


@pytest.mark.parametrize(
    "salida, tipo, area",
    [
        ('{"tipo": "Petición", "area": "cartera", "confianza": 1}', "peticion", "Cartera"),
        ('{"tipo": "denuncia", "area": "JURIDICA", "confianza": 0}', "denuncia", "Jurídica"),
        (
            '```json\n{"tipo": "queja", "area": "Seguros de vida", "confianza": 0.5}\n```',
            "queja",
            "Seguros de Vida",
        ),
    ],
)
def test_interpretar_tolera_mayusculas_tildes_y_cercos(salida, tipo, area):
    resultado = clasificador.interpretar(salida)
    assert (resultado.tipo, resultado.area) == (tipo, area)
    assert 0 <= resultado.confianza <= 1


@pytest.mark.parametrize(
    "salida",
    [
        "no es JSON",
        '{"tipo": "felicitacion", "area": "Cartera", "confianza": 0.9}',
        '{"tipo": "queja", "area": "Mercadeo", "confianza": 0.9}',
        '{"tipo": "queja", "area": "Cartera", "confianza": 1.5}',
        '{"tipo": "queja", "area": "Cartera", "confianza": -0.1}',
        '{"tipo": "queja", "area": "Cartera", "confianza": "alta"}',
        '{"tipo": "queja", "area": "Cartera", "confianza": true}',
        '{"tipo": "queja", "area": "Cartera"}',
        "[1, 2, 3]",
    ],
)
def test_interpretar_rechaza_salidas_invalidas(salida):
    assert clasificador.interpretar(salida) is None


# --- Criterio 2: reintenta una vez y, si falla, revisión humana -------------


def test_json_invalido_reintenta_una_vez(entorno):
    cliente = entorno.usar("esto no es JSON", VALIDA)
    pqrsd = _pqrsd(entorno.sesion)
    clasificador.clasificar_pqrsd(entorno.sesion, pqrsd)
    assert len(cliente.llamadas) == 2
    assert pqrsd.estado == EstadoPQRSD.clasificada


def test_dos_fallos_dejan_la_pqrsd_en_revision_humana(entorno):
    cliente = entorno.usar("no es JSON", '{"tipo": "otro"}')
    pqrsd = _pqrsd(entorno.sesion)
    assert clasificador.clasificar_pqrsd(entorno.sesion, pqrsd) is None
    assert len(cliente.llamadas) == 2  # no reintenta más de una vez
    assert pqrsd.estado == EstadoPQRSD.pendiente_revision_clasificacion
    assert pqrsd.tipo is None and pqrsd.area is None and pqrsd.confianza is None


@pytest.mark.parametrize(
    "error", [ErrorIA("sin conexión"), LimiteExcedido("presupuesto_agotado", "tope")]
)
def test_falla_de_api_o_presupuesto_deja_revision_humana(entorno, monkeypatch, error):
    def fallar(*_, **__):
        raise error

    monkeypatch.setattr(costos, "llamar_claude", fallar)
    pqrsd = _pqrsd(entorno.sesion)
    assert clasificador.clasificar_pqrsd(entorno.sesion, pqrsd) is None
    assert pqrsd.estado == EstadoPQRSD.pendiente_revision_clasificacion


# --- Criterio 3: el prompt vive en un .md -----------------------------------


def test_el_prompt_vive_en_un_archivo_md():
    assert clasificador.RUTA_PROMPT.parent.name == "prompts"
    assert clasificador.RUTA_PROMPT.suffix == ".md"
    texto = clasificador.prompt_sistema()
    for area in clasificador.AREAS:
        assert area in texto
    for tipo in ("peticion", "queja", "reclamo", "sugerencia", "denuncia"):
        assert f'"{tipo}"' in texto


# --- Integración con el orquestador (lo dispara la radicación) ---------------


def test_el_orquestador_clasifica_la_pqrsd_radicada(entorno, monkeypatch):
    monkeypatch.setattr(
        orquestador, "fabrica_sesion", lambda: contextlib.nullcontext(entorno.sesion)
    )
    # El paso híbrido usa un SVM falso que coincide con Claude (ver test_clasificacion_hibrida).
    falso = {"tipo": "reclamo", "area": "tarjetas", "sentimiento": "negativo", "fraude": "no"}
    monkeypatch.setattr(svm, "predecir",
                        lambda capa, texto: svm.PrediccionCapa(falso[capa], 0.9, {}))
    monkeypatch.setattr(svm, "predecir_tema", lambda texto, area: None)
    # Aquí solo se prueba la clasificación; el borrador se cubre en test_orquestador.py.
    monkeypatch.setattr(generador, "generar_borrador", lambda sesion, pqrsd: None)
    pqrsd = _pqrsd(entorno.sesion)
    orquestador.procesar_pqrsd(pqrsd.id)
    entorno.sesion.refresh(pqrsd)
    assert pqrsd.estado == EstadoPQRSD.clasificada
    assert pqrsd.area == "Tarjetas de Crédito"

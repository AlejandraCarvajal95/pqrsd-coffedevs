"""Clasificación híbrida: Claude decide el tipo y el SVM resuelve las demás capas.

El SVM se reemplaza por respuestas fijas: aquí se prueban las reglas, no los modelos.
"""

import pytest

from app.models import PQRSD, CanalPQRSD, EstadoPQRSD, TipoPQRSD
from app.pipeline import clasificacion_hibrida as hibrida
from app.pipeline import svm
from app.pipeline.clasificador import Clasificacion


def _pqrsd(sesion) -> PQRSD:
    pqrsd = PQRSD(
        nombre_ciudadano="Ciudadana Ficticia",
        contacto="ficticia@ejemplo.test",
        asunto="Cobro doble de cuota de manejo",
        descripcion="Me cobraron la cuota de manejo dos veces en el mismo mes.",
        canal=CanalPQRSD.formulario,
        estado=EstadoPQRSD.clasificada,
    )
    sesion.add(pqrsd)
    sesion.flush()
    return pqrsd


def _claude(tipo="reclamo", area="Tarjetas de Crédito", confianza=0.9) -> Clasificacion:
    return Clasificacion(tipo=TipoPQRSD(tipo), area=area, confianza=confianza,
                         justificacion="prueba")


@pytest.fixture
def svm_falso(monkeypatch):
    """Respuestas del SVM por capa: (etiqueta, confianza). Las pruebas las cambian."""
    respuestas = {
        "tipo": ("reclamo", 0.9), "area": ("tarjetas", 0.9),
        "sentimiento": ("negativo", 0.8), "fraude": ("no", 0.7),
        "tema": ("cobros_comisiones_intereses", 0.85),
    }

    def prediccion(capa):
        etiqueta, confianza = respuestas[capa]
        return svm.PrediccionCapa(etiqueta, confianza, {etiqueta: confianza})

    monkeypatch.setattr(svm, "predecir", lambda capa, texto: prediccion(capa))
    monkeypatch.setattr(svm, "predecir_tema", lambda texto, area: prediccion("tema"))
    return respuestas


def test_coinciden_y_el_svm_llena_sus_capas(sesion, svm_falso):
    pqrsd = _pqrsd(sesion)
    detalle = hibrida.complementar(sesion, pqrsd, _claude())
    assert pqrsd.estado == EstadoPQRSD.clasificada
    assert pqrsd.area == "Tarjetas de Crédito"
    assert pqrsd.tema == "cobros_comisiones_intereses"
    assert pqrsd.sentimiento == "negativo"
    assert pqrsd.riesgo_fraude is False
    assert detalle["origen_area"] == "coinciden"
    assert detalle["motivos_revision"] == []
    assert pqrsd.clasificacion_detalle["tipos_candidatos"] == ["reclamo"]


def test_tipo_discrepante_seguro_va_a_revision_con_dos_candidatos(sesion, svm_falso):
    svm_falso["tipo"] = ("peticion", 0.75)
    pqrsd = _pqrsd(sesion)
    detalle = hibrida.complementar(sesion, pqrsd, _claude(tipo="reclamo"))
    assert pqrsd.estado == EstadoPQRSD.pendiente_revision_clasificacion
    assert hibrida.TIPO_DISCREPANTE in detalle["motivos_revision"]
    assert detalle["tipos_candidatos"] == ["reclamo", "peticion"]


def test_tipo_discrepante_con_poca_confianza_no_molesta(sesion, svm_falso):
    svm_falso["tipo"] = ("peticion", 0.55)
    pqrsd = _pqrsd(sesion)
    detalle = hibrida.complementar(sesion, pqrsd, _claude(tipo="reclamo"))
    assert pqrsd.estado == EstadoPQRSD.clasificada
    assert detalle["tipos_candidatos"] == ["reclamo"]


def test_el_svm_muy_seguro_corrige_el_area(sesion, svm_falso):
    svm_falso["area"] = ("cartera", 0.85)
    pqrsd = _pqrsd(sesion)
    detalle = hibrida.complementar(sesion, pqrsd, _claude(area="Tarjetas de Crédito"))
    assert pqrsd.area == "Cartera"
    assert detalle["origen_area"] == "svm"


def test_si_el_svm_duda_queda_el_area_de_claude(sesion, svm_falso):
    svm_falso["area"] = ("cartera", 0.6)
    pqrsd = _pqrsd(sesion)
    detalle = hibrida.complementar(sesion, pqrsd, _claude(area="Tarjetas de Crédito"))
    assert pqrsd.area == "Tarjetas de Crédito"
    assert detalle["origen_area"] == "claude"


def test_regla_de_seguros_corrige_el_area(sesion, svm_falso):
    pqrsd = _pqrsd(sesion)
    pqrsd.descripcion = "Me cobran un seguro de vida en la tarjeta que nunca autoricé."
    detalle = hibrida.complementar(sesion, pqrsd, _claude(area="Tarjetas de Crédito"))
    assert pqrsd.area == "Seguros de Vida"
    assert detalle["origen_area"] == "regla_seguros"


@pytest.mark.parametrize("texto", [
    "No estoy seguro de que la compra sea mía.",
    "Estoy seguro de que pagué a tiempo la cuota de manejo.",
    "Mi prima usó mi tarjeta sin permiso.",
    "Me cobran una deuda médica que mi seguro debía cubrir.",
])
def test_seguro_como_adjetivo_no_activa_la_regla(sesion, svm_falso, texto):
    pqrsd = _pqrsd(sesion)
    pqrsd.descripcion = texto
    hibrida.complementar(sesion, pqrsd, _claude(area="Tarjetas de Crédito"))
    assert pqrsd.area == "Tarjetas de Crédito"


def test_fuera_de_competencia_va_a_revision_y_no_tiene_tema(sesion, svm_falso):
    svm_falso["area"] = ("fuera_de_competencia", 0.95)
    pqrsd = _pqrsd(sesion)
    detalle = hibrida.complementar(sesion, pqrsd, _claude())
    assert hibrida.FUERA_DE_COMPETENCIA in detalle["motivos_revision"]
    assert pqrsd.estado == EstadoPQRSD.pendiente_revision_clasificacion


def test_baja_confianza_de_claude_va_a_revision(sesion, svm_falso):
    pqrsd = _pqrsd(sesion)
    detalle = hibrida.complementar(sesion, pqrsd, _claude(confianza=0.4))
    assert hibrida.BAJA_CONFIANZA in detalle["motivos_revision"]
    assert pqrsd.estado == EstadoPQRSD.pendiente_revision_clasificacion


def test_sin_claude_no_inventa_tipo_pero_el_svm_llena_sus_capas(sesion, svm_falso):
    pqrsd = _pqrsd(sesion)
    pqrsd.estado = EstadoPQRSD.pendiente_revision_clasificacion
    detalle = hibrida.complementar(sesion, pqrsd, None)
    assert pqrsd.tipo is None
    assert hibrida.CLAUDE_NO_DISPONIBLE in detalle["motivos_revision"]
    assert pqrsd.sentimiento == "negativo"
    assert detalle["svm"]["tipo"]["etiqueta"] == "reclamo"  # propuesta para quien revise


def test_si_el_svm_falla_queda_lo_de_claude(sesion, monkeypatch):
    def falla(capa, texto):
        raise FileNotFoundError("sin modelos")

    monkeypatch.setattr(svm, "predecir", falla)
    pqrsd = _pqrsd(sesion)
    pqrsd.area = "Tarjetas de Crédito"
    detalle = hibrida.complementar(sesion, pqrsd, _claude())
    assert detalle["svm"] == "no_disponible"
    assert pqrsd.estado == EstadoPQRSD.clasificada
    assert pqrsd.area == "Tarjetas de Crédito"

"""Pruebas del embudo SVM con modelos diminutos entrenados en la prueba (sin el modelo real)."""

import joblib
import pytest

from app.pipeline import svm

TEXTOS = {
    "tipo": {
        "peticion": ["solicito el certificado de saldo de mi tarjeta",
                     "solicito copia del contrato de mi credito",
                     "solicito el paz y salvo de mi obligacion"],
        "reclamo": ["me cobraron dos veces la cuota de manejo y pido devolucion",
                    "me cobraron un seguro que no autorice y pido devolucion",
                    "me cobraron intereses de mas y pido devolucion"],
    },
    "area": {
        "tarjetas": ["cuota de manejo de la tarjeta de credito",
                     "compra no reconocida en la tarjeta de credito",
                     "bloqueo de la tarjeta de credito"],
        "fuera_de_competencia": ["impuesto predial de mi casa en el municipio",
                                 "pago del impuesto predial del lote en el municipio",
                                 "certificado del impuesto predial del municipio"],
    },
    "sentimiento": {
        "negativo": ["estoy furioso, pesimo servicio, nadie responde",
                     "pesimo servicio, estoy cansado y furioso",
                     "furioso con el pesimo servicio del banco"],
        "neutral": ["quisiera saber el horario de atencion de la oficina",
                    "quisiera saber el horario de la oficina principal",
                    "quisiera saber el horario de atencion del sabado"],
    },
    "tema_tarjetas": {
        "cobros_comisiones_intereses": ["me cobraron la cuota de manejo dos veces",
                                        "cobro de cuota de manejo sin usar la tarjeta",
                                        "la cuota de manejo esta mal cobrada"],
        "transaccion_no_reconocida": ["compra no reconocida en otra ciudad",
                                      "no reconozco una compra en mi extracto",
                                      "compra no reconocida por internet"],
    },
}


@pytest.fixture
def modelos(tmp_path, monkeypatch, embedder_falso):
    """Entrena modelos mínimos de cada capa y los deja donde svm.clasificar los busca."""
    monkeypatch.setattr(svm, "DIR_MODELOS", tmp_path)
    monkeypatch.setattr(svm, "_modelos", {})
    for capa, clases in TEXTOS.items():
        x = [t for textos in clases.values() for t in textos * 2]
        y = [c for c, textos in clases.items() for _ in textos * 2]
        modelo = svm.construir_modelo(c=1.0, particiones_calibracion=2).fit(x, y)
        joblib.dump({"modelo": modelo}, tmp_path / f"{capa}.joblib")
    return tmp_path


def test_clasifica_en_cascada_con_tema_del_area(modelos):
    r = svm.clasificar("me cobraron dos veces la cuota de manejo de la tarjeta de credito")
    assert r.area.etiqueta == "tarjetas"
    assert r.tipo.etiqueta == "reclamo"
    assert r.tema is not None and r.tema.etiqueta == "cobros_comisiones_intereses"
    assert 0 <= r.tipo.confianza <= 1
    assert sum(r.tipo.probabilidades.values()) == pytest.approx(1, abs=1e-3)


def test_fuera_de_competencia_no_lleva_tema_ni_fraude(modelos):
    r = svm.clasificar("certificado del impuesto predial de mi lote en el municipio")
    assert r.area.etiqueta == "fuera_de_competencia"
    assert r.tema is None
    assert r.fraude is None


def test_sin_modelos_base_falla_claro(tmp_path, monkeypatch):
    monkeypatch.setattr(svm, "DIR_MODELOS", tmp_path)
    monkeypatch.setattr(svm, "_modelos", {})
    with pytest.raises(FileNotFoundError, match="tipo"):
        svm.clasificar("cualquier texto")

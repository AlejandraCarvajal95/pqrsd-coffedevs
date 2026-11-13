"""US-016 y US-017: festivos de Colombia, días hábiles, vencimiento y semáforo."""

from datetime import UTC, date, datetime

import pytest

from app.config import configuracion
from app.pipeline import dias_habiles as dh

FESTIVOS_2026 = {
    date(2026, 1, 1),    # Año Nuevo
    date(2026, 1, 12),   # Reyes (6 de enero, martes) trasladado al lunes
    date(2026, 3, 23),   # San José (19 de marzo, jueves) trasladado
    date(2026, 4, 2),    # Jueves Santo
    date(2026, 4, 3),    # Viernes Santo
    date(2026, 5, 1),    # Día del Trabajo
    date(2026, 5, 18),   # Ascensión
    date(2026, 6, 8),    # Corpus Christi
    date(2026, 6, 15),   # Sagrado Corazón
    date(2026, 6, 29),   # San Pedro y San Pablo (cae lunes)
    date(2026, 7, 20),   # Independencia
    date(2026, 8, 7),    # Batalla de Boyacá
    date(2026, 8, 17),   # Asunción (15 de agosto, sábado) trasladado
    date(2026, 10, 12),  # Día de la Raza (cae lunes)
    date(2026, 11, 2),   # Todos los Santos (1 de noviembre, domingo) trasladado
    date(2026, 11, 16),  # Independencia de Cartagena (11 de noviembre) trasladado
    date(2026, 12, 8),   # Inmaculada Concepción
    date(2026, 12, 25),  # Navidad
}  # fmt: skip


@pytest.mark.parametrize(
    ("anio", "esperado"),
    [(2024, date(2024, 3, 31)), (2025, date(2025, 4, 20)),
     (2026, date(2026, 4, 5)), (2027, date(2027, 3, 28))],
)  # fmt: skip
def test_domingo_de_pascua(anio, esperado):
    assert dh.domingo_de_pascua(anio) == esperado


def test_festivos_de_colombia_2026():
    assert dh.festivos(2026) == FESTIVOS_2026


def test_festivos_de_2027_dependen_de_la_pascua_y_del_lunes():
    festivos = dh.festivos(2027)
    assert len(festivos) == 18
    assert date(2027, 1, 11) in festivos  # Reyes (miércoles 6) pasa al lunes 11
    assert date(2027, 1, 6) not in festivos
    assert {date(2027, 3, 25), date(2027, 3, 26)} <= festivos  # Jueves y Viernes Santo


@pytest.mark.parametrize(
    ("fecha", "habil"),
    [
        (date(2026, 11, 13), True),   # viernes común
        (date(2026, 11, 14), False),  # sábado
        (date(2026, 11, 15), False),  # domingo
        (date(2026, 11, 16), False),  # lunes festivo
        (date(2026, 7, 20), False),   # 20 de julio
        (date(2026, 8, 7), False),    # 7 de agosto
        (date(2026, 4, 2), False),    # Jueves Santo
    ],
)  # fmt: skip
def test_es_habil(fecha, habil):
    assert dh.es_habil(fecha) is habil


@pytest.mark.parametrize(
    ("desde", "dias", "esperado"),
    [
        # 15 hábiles desde el jueves 12 de noviembre; el lunes 16 es festivo.
        (date(2026, 11, 12), 15, date(2026, 12, 4)),
        # Radicada un sábado: el plazo empieza el siguiente día hábil (martes 17).
        (date(2026, 11, 14), 15, date(2026, 12, 7)),
        # Radicada un lunes festivo: empieza el martes.
        (date(2026, 11, 16), 1, date(2026, 11, 17)),
        # Semana Santa: del miércoles salta al lunes de Pascua.
        (date(2026, 4, 1), 1, date(2026, 4, 6)),
        # Puentes del 20 de julio y del 7 de agosto.
        (date(2026, 7, 17), 1, date(2026, 7, 21)),
        (date(2026, 8, 6), 1, date(2026, 8, 10)),
        # Cambio de año: Navidad y Año Nuevo no cuentan.
        (date(2026, 12, 24), 5, date(2027, 1, 4)),
    ],
)
def test_sumar_dias_habiles(desde, dias, esperado):
    assert dh.sumar_dias_habiles(desde, dias) == esperado


def test_dias_habiles_entre():
    assert dh.dias_habiles_entre(date(2026, 11, 12), date(2026, 12, 4)) == 15
    assert dh.dias_habiles_entre(date(2026, 12, 4), date(2026, 11, 12)) == -15
    assert dh.dias_habiles_entre(date(2026, 11, 12), date(2026, 11, 12)) == 0
    assert dh.dias_habiles_entre(date(2026, 11, 13), date(2026, 11, 16)) == 0  # fin de semana


def test_el_vencimiento_usa_la_fecha_de_colombia():
    # Las 02:00 UTC del 13 todavía son las 21:00 del 12 en Colombia.
    radicada = datetime(2026, 11, 13, 2, 0, tzinfo=UTC)
    assert dh.fecha_colombia(radicada) == date(2026, 11, 12)
    assert dh.calcular_vencimiento(radicada) == date(2026, 12, 4)


def test_el_plazo_es_configurable_por_tipo(monkeypatch):
    assert dh.plazo_en_dias() == 15  # plazo general
    monkeypatch.setattr(configuracion, "plazos_por_tipo", {"peticion": 10, "sugerencia": 30})
    assert dh.plazo_en_dias(["peticion"]) == 10
    assert dh.plazo_en_dias(["reclamo"]) == 15
    assert dh.plazo_en_dias([None]) == 15
    # Tipo dudoso: se toma el plazo más corto de los candidatos.
    assert dh.plazo_en_dias(["sugerencia", "peticion"]) == 10
    radicada = datetime(2026, 11, 12, 15, 0, tzinfo=UTC)
    assert dh.calcular_vencimiento(radicada, ["peticion"]) == date(2026, 11, 27)

    monkeypatch.setattr(configuracion, "plazo_dias_habiles", 5)
    assert dh.calcular_vencimiento(radicada, ["reclamo"]) == date(2026, 11, 20)


@pytest.mark.parametrize(
    ("hoy", "color", "dias", "vencida"),
    [
        (date(2026, 11, 12), "verde", 15, False),
        (date(2026, 11, 24), "verde", 8, False),
        (date(2026, 11, 25), "amarillo", 7, False),
        (date(2026, 11, 30), "amarillo", 4, False),
        (date(2026, 12, 1), "rojo", 3, False),
        (date(2026, 12, 4), "rojo", 0, False),   # vence hoy
        (date(2026, 12, 5), "rojo", 0, True),    # sábado siguiente: ya venció
        (date(2026, 12, 9), "rojo", -2, True),   # el 8 es festivo: dos hábiles de atraso
    ],
)  # fmt: skip
def test_semaforo(hoy, color, dias, vencida):
    estado = dh.semaforo(date(2026, 12, 4), hoy=hoy)
    assert (estado.color, estado.dias_restantes, estado.vencida) == (color, dias, vencida)


def test_semaforo_sin_fecha_y_con_umbrales_configurables(monkeypatch):
    assert dh.semaforo(None) == dh.Semaforo(color=None, dias_restantes=None, vencida=False)
    monkeypatch.setattr(configuracion, "semaforo_rojo_dias", 5)
    monkeypatch.setattr(configuracion, "semaforo_amarillo_dias", 10)
    assert dh.semaforo(date(2026, 12, 4), hoy=date(2026, 11, 30)).color == "rojo"
    assert dh.semaforo(date(2026, 12, 4), hoy=date(2026, 11, 24)).color == "amarillo"

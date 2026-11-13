"""Motor de plazos (US-016 y US-017): días hábiles de Colombia, vencimiento y semáforo.

- Día hábil: lunes a viernes que no sea festivo. Los festivos se calculan con
  las reglas de la Ley 51 de 1983 (Ley Emiliani), sin tablas ni librerías:
  fijos, trasladados al lunes siguiente y los que dependen de la Pascua.
- El plazo se cuenta desde el día hábil siguiente a la radicación, en hora de
  Colombia. Si se radica un sábado, un domingo o un festivo, el primer día del
  plazo es el siguiente día hábil.
- Los plazos y los umbrales del semáforo vienen de la configuración
  (PLAZO_DIAS_HABILES, PLAZOS_POR_TIPO, SEMAFORO_ROJO_DIAS, SEMAFORO_AMARILLO_DIAS).

Es una simplificación para la demo, no asesoría legal: el reto habla de 15 días
hábiles y la Ley 1755 de 2015 distingue otros términos (documentos, consultas)
que se pueden configurar por tipo sin tocar el código.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from functools import lru_cache

from app.config import configuracion
from app.models.pqrsd import ZONA_COLOMBIA

UN_DIA = timedelta(days=1)

# (mes, día) que no se mueven.
FESTIVOS_FIJOS = ((1, 1), (5, 1), (7, 20), (8, 7), (12, 8), (12, 25))
# (mes, día) que se trasladan al lunes siguiente si no caen en lunes.
FESTIVOS_AL_LUNES = ((1, 6), (3, 19), (6, 29), (8, 15), (10, 12), (11, 1), (11, 11))
# Días respecto al Domingo de Pascua: Jueves y Viernes Santo, y Ascensión,
# Corpus Christi y Sagrado Corazón ya trasladados al lunes.
FESTIVOS_DE_PASCUA = (-3, -2, 43, 64, 71)

VERDE, AMARILLO, ROJO = "verde", "amarillo", "rojo"


def domingo_de_pascua(anio: int) -> date:
    """Algoritmo gregoriano anónimo (Meeus/Jones/Butcher)."""
    a = anio % 19
    b, c = divmod(anio, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    m = (32 + 2 * e + 2 * i - h - k) % 7
    n = (a + 11 * h + 22 * m) // 451
    mes, dia = divmod(h + m - 7 * n + 114, 31)
    return date(anio, mes, dia + 1)


def _al_lunes(fecha: date) -> date:
    return fecha + timedelta(days=(7 - fecha.weekday()) % 7)


@lru_cache(maxsize=32)
def festivos(anio: int) -> frozenset[date]:
    """Los 18 festivos de Colombia del año."""
    pascua = domingo_de_pascua(anio)
    return frozenset(
        [date(anio, mes, dia) for mes, dia in FESTIVOS_FIJOS]
        + [_al_lunes(date(anio, mes, dia)) for mes, dia in FESTIVOS_AL_LUNES]
        + [pascua + timedelta(days=dias) for dias in FESTIVOS_DE_PASCUA]
    )


def es_festivo(fecha: date) -> bool:
    return fecha in festivos(fecha.year)


def es_habil(fecha: date) -> bool:
    return fecha.weekday() < 5 and not es_festivo(fecha)


def sumar_dias_habiles(desde: date, dias: int) -> date:
    """Fecha en la que se cumplen `dias` hábiles contados desde el día siguiente a `desde`."""
    fecha = desde
    while dias > 0:
        fecha += UN_DIA
        if es_habil(fecha):
            dias -= 1
    return fecha


def dias_habiles_entre(desde: date, hasta: date) -> int:
    """Días hábiles en (desde, hasta]. Negativo si `hasta` ya pasó."""
    if hasta < desde:
        return -dias_habiles_entre(hasta, desde)
    cuenta, fecha = 0, desde
    while fecha < hasta:
        fecha += UN_DIA
        if es_habil(fecha):
            cuenta += 1
    return cuenta


def fecha_colombia(momento: datetime | None = None) -> date:
    """La fecha en Colombia de un instante (por defecto, ahora)."""
    momento = momento or datetime.now(ZONA_COLOMBIA)
    return momento.astimezone(ZONA_COLOMBIA).date()


def plazo_en_dias(tipos: Iterable[str | None] = ()) -> int:
    """Plazo en días hábiles. Con varios tipos candidatos se usa el más corto."""
    por_tipo = configuracion.plazos_por_tipo
    plazos = [
        por_tipo.get(str(tipo), configuracion.plazo_dias_habiles) for tipo in tipos if tipo
    ]
    return min(plazos, default=configuracion.plazo_dias_habiles)


def calcular_vencimiento(
    fecha_radicacion: datetime | None, tipos: Iterable[str | None] = ()
) -> date:
    """Fecha de vencimiento de una PQRSD según su fecha de radicación y su tipo."""
    return sumar_dias_habiles(fecha_colombia(fecha_radicacion), plazo_en_dias(tipos))


@dataclass(frozen=True)
class Semaforo:
    color: str | None  # verde | amarillo | rojo; None si no hay fecha de vencimiento
    dias_restantes: int | None  # días hábiles que quedan; negativo si ya venció
    vencida: bool


def semaforo(vencimiento: date | None, hoy: date | None = None) -> Semaforo:
    """Urgencia de una PQRSD: rojo si quedan pocos días hábiles o ya venció."""
    if vencimiento is None:
        return Semaforo(color=None, dias_restantes=None, vencida=False)
    hoy = hoy or fecha_colombia()
    restantes = dias_habiles_entre(hoy, vencimiento)
    vencida = hoy > vencimiento
    if vencida or restantes <= configuracion.semaforo_rojo_dias:
        color = ROJO
    elif restantes <= configuracion.semaforo_amarillo_dias:
        color = AMARILLO
    else:
        color = VERDE
    return Semaforo(color=color, dias_restantes=restantes, vencida=vencida)

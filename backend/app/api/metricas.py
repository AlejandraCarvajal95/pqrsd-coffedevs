"""Resumen ejecutivo del panel (US-024): GET /api/metricas, solo con sesión del panel.

Cifras agregadas para las tarjetas, las distribuciones y el calendario de
vencimientos. El semáforo y los días hábiles se calculan al consultar, con la
misma lógica de la bandeja.
"""

from collections import Counter, defaultdict
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.bandeja import consultar_bandeja
from app.config import configuracion
from app.db import obtener_sesion
from app.models import EstadoPQRSD
from app.pipeline.costos import gasto_por_tarea, gasto_total
from app.pipeline.dias_habiles import AMARILLO, ROJO, VERDE

router = APIRouter(prefix="/metricas", tags=["metricas"])

SIN_DATO = "sin clasificar"


def _distribucion(valores: list) -> list[dict]:
    conteo = Counter(str(valor) if valor else SIN_DATO for valor in valores)
    return [{"nombre": nombre, "total": total} for nombre, total in conteo.most_common()]


@router.get("")
def resumen(sesion: Annotated[Session, Depends(obtener_sesion)]) -> dict:
    todas = consultar_bandeja(sesion, incluir_respondidas=True)
    activas = [item for item in todas if item["estado"] != EstadoPQRSD.respondida]

    por_estado = Counter(str(item["estado"]) for item in todas)
    vencidas = [item for item in activas if item["vencida"]]
    por_semaforo = {
        VERDE: sum(item["semaforo"] == VERDE for item in activas),
        AMARILLO: sum(item["semaforo"] == AMARILLO for item in activas),
        # En rojo pero todavía dentro del plazo; las vencidas se cuentan aparte.
        ROJO: sum(item["semaforo"] == ROJO and not item["vencida"] for item in activas),
        "vencidas": len(vencidas),
        "sin_fecha": sum(item["semaforo"] is None for item in activas),
    }

    # Calendario: qué PQRSD activas vencen cada día (ya vienen ordenadas por urgencia).
    por_fecha: dict = defaultdict(list)
    for item in activas:
        if item["fecha_vencimiento"] is not None:
            por_fecha[item["fecha_vencimiento"]].append(
                {
                    "radicado": item["radicado"],
                    "asunto": item["asunto"],
                    "area": item["area"],
                    "tipo": item["tipo"],
                    "semaforo": item["semaforo"],
                    "vencida": item["vencida"],
                }
            )
    calendario = [
        {"fecha": fecha, "total": len(lista), "pqrsd": lista}
        for fecha, lista in sorted(por_fecha.items())
    ]

    gasto = float(gasto_total(sesion))
    return {
        "tarjetas": {
            "activas": len(activas),
            "por_vencer": por_semaforo[ROJO] + por_semaforo["vencidas"],
            "pendientes_revision": por_estado[EstadoPQRSD.pendiente_revision_clasificacion.value],
            "con_borrador_listo": por_estado[EstadoPQRSD.borrador_listo.value],
            "respondidas": por_estado[EstadoPQRSD.respondida.value],
            "riesgo_fraude": sum(bool(item["riesgo_fraude"]) for item in activas),
        },
        "por_estado": {estado.value: por_estado[estado.value] for estado in EstadoPQRSD},
        "por_semaforo": por_semaforo,
        "por_area": _distribucion([item["area"] for item in todas]),
        "por_tipo": _distribucion([item["tipo"] for item in todas]),
        "calendario": calendario,
        "presupuesto_ia": {
            "total_usd": round(gasto, 6),
            "alerta_usd": configuracion.gasto_alerta_usd,
            "tope_usd": configuracion.gasto_tope_usd,
            "alerta": gasto >= configuracion.gasto_alerta_usd,
            "por_tarea": gasto_por_tarea(sesion),
        },
    }

"""Paso 1b del pipeline: clasificación híbrida (Claude + SVM).

Claude (pipeline/clasificador.py, US-011) decide el TIPO, porque el tipo define el plazo
legal y distinguir petición, queja y reclamo exige entender el sentido. El SVM
(pipeline/svm.py) resuelve las demás capas sin gastar API: área, tema, sentimiento y
riesgo de fraude, y además verifica el tipo y el área de Claude.

Reglas (umbrales medidos en el split de test, ver modelos_svm/metricas.md):
- Tipo: siempre el de Claude. Si el SVM propone otro con confianza >= 0,7 (85 % de
  precisión), la PQRSD va a revisión humana y se guardan los dos tipos candidatos: el
  motor de plazos debe usar el plazo más corto mientras una persona decide.
- Área: si Claude y el SVM coinciden, se acepta. Si no, gana el SVM cuando su confianza
  es >= 0,8 (95 % de precisión); si no, queda la de Claude.
- Seguros: si el texto nombra un seguro, una póliza o un siniestro (REGLA_SEGUROS), el área
  es Seguros de Vida. En el golden set ninguno de los dos clasificadores lo lograba.
- Fuera de competencia: si el SVM lo dice con confianza >= 0,8, va a revisión (posible
  traslado a otra entidad).
- Confianza de Claude < 0,6: revisión humana.
- Si Claude no respondió, tipo y área quedan vacíos y la PQRSD va a revisión; el SVM igual
  llena las capas que le tocan y deja su propuesta en el detalle para quien revise.
Nunca se envía nada al ciudadano sin aprobación humana.
"""

import logging
import re

from sqlalchemy.orm import Session

from app.models import PQRSD, EstadoPQRSD
from app.pipeline import svm
from app.pipeline.clasificador import Clasificacion

logger = logging.getLogger(__name__)

UMBRAL_SVM_AREA = 0.8
UMBRAL_SVM_TIPO_DISCREPANTE = 0.7
UMBRAL_FUERA_DE_COMPETENCIA = 0.8
UMBRAL_CONFIANZA_CLAUDE = 0.6

# Etiquetas del SVM -> nombres de área que usa Claude y el resto del sistema.
AREAS = {
    "tarjetas": "Tarjetas de Crédito",
    "cartera": "Cartera",
    "seguros": "Seguros de Vida",
    "juridica": "Jurídica",
}
ETIQUETA_DE_AREA = {v: k for k, v in AREAS.items()}

# Regla de Seguros: en el golden set, las quejas por el seguro asociado a la tarjeta o al
# crédito se iban a Tarjetas o Cartera (hablan del cobro en el extracto). Si el texto nombra
# un seguro, una póliza o un siniestro, el área es Seguros de Vida. Se evita "seguro" suelto
# porque también significa "estoy seguro".
REGLA_SEGUROS = re.compile(
    # Solo seguros del Banco: no "mi seguro" ni "la aseguradora" sueltos, que en el golden set
    # se referían a seguros médicos dentro de quejas de cobranza (Cartera).
    r"\b(p[óo]lizas? (de vida|del cr[ée]dito|de la tarjeta|de seguro)|siniestros?|"
    r"seguros? (de vida|deudor(es)?|de (la|mi) (tarjeta|cr[ée]dito|deuda)|de deuda|de desempleo|"
    r"de protecci[óo]n|asociados? (a|al)|que (nunca |no )?(autoric[ée]|ped[íi]|solicit[ée]))|"
    r"prima (del|de|de mi) seguro|cobr\w* (adicional )?(por|de) (un|el) seguro)",
    re.IGNORECASE,
)

# Motivos que mandan la PQRSD a revisión humana.
TIPO_DISCREPANTE = "tipo_discrepante"
BAJA_CONFIANZA = "baja_confianza"
FUERA_DE_COMPETENCIA = "posible_fuera_de_competencia"
CLAUDE_NO_DISPONIBLE = "claude_no_disponible"


def _resumen(p: svm.PrediccionCapa | None) -> dict | None:
    return None if p is None else {"etiqueta": p.etiqueta, "confianza": p.confianza}


def complementar(sesion: Session, pqrsd: PQRSD, claude: Clasificacion | None) -> dict:
    """Completa la clasificación de Claude con el SVM y decide si va a revisión. No hace commit.

    Devuelve el detalle que guarda en pqrsd.clasificacion_detalle.
    """
    texto = f"{pqrsd.asunto}. {pqrsd.descripcion}"
    detalle: dict = {
        "claude": None if claude is None else {
            "tipo": str(claude.tipo), "area": claude.area, "confianza": claude.confianza,
            "justificacion": claude.justificacion,
        },
    }
    try:
        tipo_svm = svm.predecir("tipo", texto)
        area_svm = svm.predecir("area", texto)
        sentimiento = svm.predecir("sentimiento", texto)
    except Exception:  # noqa: BLE001 - sin SVM queda lo de Claude, como antes
        logger.exception("SVM no disponible para %s", pqrsd.radicado)
        detalle["svm"] = "no_disponible"
        pqrsd.clasificacion_detalle = detalle
        sesion.flush()
        return detalle

    motivos: list[str] = []
    candidatos: list[str] = []

    # --- Tipo: decide Claude; el SVM verifica.
    if claude is None:
        motivos.append(CLAUDE_NO_DISPONIBLE)
    else:
        candidatos.append(str(claude.tipo))
        if (tipo_svm and tipo_svm.etiqueta != str(claude.tipo)
                and tipo_svm.confianza >= UMBRAL_SVM_TIPO_DISCREPANTE):
            motivos.append(TIPO_DISCREPANTE)
            candidatos.append(tipo_svm.etiqueta)
        if claude.confianza < UMBRAL_CONFIANZA_CLAUDE:
            motivos.append(BAJA_CONFIANZA)

    # --- Área: coincidencia, o el SVM cuando está muy seguro.
    area_final = claude.area if claude else None
    origen_area = "claude"
    if area_svm is not None:
        if area_svm.etiqueta == "fuera_de_competencia":
            if area_svm.confianza >= UMBRAL_FUERA_DE_COMPETENCIA:
                motivos.append(FUERA_DE_COMPETENCIA)
        elif AREAS[area_svm.etiqueta] == area_final:
            origen_area = "coinciden"
        elif area_svm.confianza >= UMBRAL_SVM_AREA:
            area_final, origen_area = AREAS[area_svm.etiqueta], "svm"
    svm_dice_banco = area_svm is not None and area_svm.etiqueta != "fuera_de_competencia"
    es_del_banco = area_final is not None or svm_dice_banco
    if es_del_banco and area_final != AREAS["seguros"] and REGLA_SEGUROS.search(texto):
        area_final, origen_area = AREAS["seguros"], "regla_seguros"
    pqrsd.area = area_final

    # --- Capas del SVM: tema (según el área final), sentimiento y fraude.
    etiqueta_area = ETIQUETA_DE_AREA.get(area_final or "")
    tema = svm.predecir_tema(texto, etiqueta_area) if etiqueta_area else None
    fraude = svm.predecir("fraude", texto) if etiqueta_area else None
    pqrsd.tema = tema.etiqueta if tema else None
    pqrsd.sentimiento = sentimiento.etiqueta if sentimiento else None
    pqrsd.riesgo_fraude = (fraude.etiqueta == "si") if fraude else None

    if motivos:
        pqrsd.estado = EstadoPQRSD.pendiente_revision_clasificacion
    detalle.update({
        "svm": {"tipo": _resumen(tipo_svm), "area": _resumen(area_svm), "tema": _resumen(tema),
                "sentimiento": _resumen(sentimiento), "fraude": _resumen(fraude)},
        "origen_area": origen_area,
        "tipos_candidatos": candidatos,
        "motivos_revision": motivos,
    })
    pqrsd.clasificacion_detalle = detalle
    sesion.flush()
    logger.info("%s: área %s (%s), tema %s, sentimiento %s, fraude %s, revisión %s",
                pqrsd.radicado, area_final, origen_area, pqrsd.tema, pqrsd.sentimiento,
                pqrsd.riesgo_fraude, motivos or "no")
    return detalle

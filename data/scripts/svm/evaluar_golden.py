"""Evalúa el pipeline real (Claude + SVM) contra el golden set etiquetado por el equipo.

    docker compose run --rm --user root -v ./data/datasets:/data/datasets \
        -v ./data/scripts/svm:/data/scripts/svm \
        -v ./backend/app/pipeline/modelos_svm:/app/app/pipeline/modelos_svm \
        backend python /data/scripts/svm/evaluar_golden.py

Entrada: data/datasets/final/golden_set.jsonl (59 PQRSD reales, ninguna usada para entrenar).
- Tipo: lo etiquetó una persona del equipo.
- Área y tema: los eligió el propio cliente del CFPB al radicar; las de entidades públicas y
  reseñas son "fuera de competencia".
Salida: modelos_svm/evaluacion_golden.json y evaluacion_golden.md (solo métricas e ids).
"""

import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, "/app")
from sklearn.metrics import confusion_matrix, f1_score  # noqa: E402

from app.models import PQRSD, CanalPQRSD, EstadoPQRSD  # noqa: E402
from app.pipeline import clasificacion_hibrida, clasificador, svm  # noqa: E402

GOLDEN = Path("/data/datasets/final/golden_set.jsonl")
TIPOS = ["peticion", "queja", "reclamo", "sugerencia", "denuncia"]


class SesionFalsa:
    """complementar() solo llama a flush(): aquí no se guarda nada en la base."""

    def flush(self):
        pass


def clasificar(texto: str) -> dict:
    claude = clasificador.clasificar_texto("", texto)
    pqrsd = PQRSD(nombre_ciudadano="-", contacto="-", asunto="", descripcion=texto,
                  canal=CanalPQRSD.formulario, radicado="EVALUACION")
    if claude:
        pqrsd.tipo, pqrsd.area, pqrsd.confianza = claude.tipo, claude.area, claude.confianza
        pqrsd.estado = EstadoPQRSD.clasificada
    else:
        pqrsd.estado = EstadoPQRSD.pendiente_revision_clasificacion
    detalle = clasificacion_hibrida.complementar(SesionFalsa(), pqrsd, claude)
    area_final = clasificacion_hibrida.ETIQUETA_DE_AREA.get(pqrsd.area or "", None)
    return {
        "tipo_claude": str(claude.tipo) if claude else None,
        "confianza_claude": claude.confianza if claude else None,
        "tipo_svm": detalle["svm"]["tipo"]["etiqueta"],
        "area_claude": clasificacion_hibrida.ETIQUETA_DE_AREA.get(claude.area) if claude else None,
        "area_svm": detalle["svm"]["area"]["etiqueta"],
        "area_final": area_final,
        "tema_pred": pqrsd.tema,
        "revision": pqrsd.estado == EstadoPQRSD.pendiente_revision_clasificacion,
        "motivos": detalle["motivos_revision"],
        "origen_area": detalle.get("origen_area"),
    }


def exactitud(pares) -> float:
    pares = list(pares)
    return round(sum(a == b for a, b in pares) / max(len(pares), 1), 3)


def main():
    filas = [json.loads(linea) for linea in GOLDEN.read_text(encoding="utf-8").splitlines()]
    for i, f in enumerate(filas, 1):
        f.update(clasificar(f["texto"]))
        print(f"{i:>2} {f['tipo']:<10} claude={f['tipo_claude']!s:<10} svm={f['tipo_svm']:<10} "
              f"área ref={f['area']:<20} final={f['area_final']!s:<10} revisión={f['motivos']}",
              flush=True)

    pqrsd = [f for f in filas if f["tipo"] in TIPOS]  # sin "no_aplica"
    banco = [f for f in filas if f["area"] != "fuera_de_competencia"]
    fuera = [f for f in filas if f["area"] == "fuera_de_competencia"]
    con_tema = [f for f in banco if f["tema"] is not None and f["area"] != "seguros"]
    sin_revision = [f for f in pqrsd if not f["revision"]]
    errores_claude = [f for f in pqrsd if f["tipo_claude"] != f["tipo"]]

    m = {
        "n": len(filas),
        "tipo": {
            "n": len(pqrsd),
            "exactitud_claude": exactitud((f["tipo_claude"], f["tipo"]) for f in pqrsd),
            "f1_macro_claude": round(f1_score([f["tipo"] for f in pqrsd],
                                              [f["tipo_claude"] or "-" for f in pqrsd],
                                              labels=TIPOS, average="macro", zero_division=0), 3),
            "exactitud_svm": exactitud((f["tipo_svm"], f["tipo"]) for f in pqrsd),
            "exactitud_sin_revision": exactitud((f["tipo_claude"], f["tipo"]) for f in sin_revision),
            "casos_sin_revision": len(sin_revision),
            "errores_de_claude_atrapados_por_revision": sum(f["revision"] for f in errores_claude),
            "errores_de_claude": len(errores_claude),
            "matriz_claude": {"clases": TIPOS, "valores": confusion_matrix(
                [f["tipo"] for f in pqrsd], [f["tipo_claude"] or "-" for f in pqrsd],
                labels=TIPOS).tolist()},
        },
        "area_banco": {
            "n": len(banco),
            "exactitud_claude": exactitud((f["area_claude"], f["area"]) for f in banco),
            "exactitud_svm": exactitud((f["area_svm"], f["area"]) for f in banco),
            "exactitud_final_hibrida": exactitud((f["area_final"], f["area"]) for f in banco),
        },
        "fuera_de_competencia": {
            "n": len(fuera),
            "detectadas_por_svm": sum(f["area_svm"] == "fuera_de_competencia" for f in fuera),
            "enviadas_a_revision": sum(f["revision"] for f in fuera),
        },
        "tema": {"n": len(con_tema),
                 "exactitud_svm": exactitud((f["tema_pred"], f["tema"]) for f in con_tema)},
        "revision_humana": {"porcentaje": round(sum(f["revision"] for f in filas) / len(filas), 3),
                            "motivos": Counter(m for f in filas for m in f["motivos"])},
        "filas": [{k: f[k] for k in ("id", "tipo", "tipo_claude", "tipo_svm", "area", "area_claude",
                                     "area_svm", "area_final", "tema", "tema_pred", "revision", "motivos",
                                     "confianza_claude", "origen_area")}
                  for f in filas],
    }
    return m


if __name__ == "__main__":
    print("Modelos:", svm.modelos_disponibles(), flush=True)
    resultado = main()
    ruta = svm.DIR_MODELOS / "evaluacion_golden.json"
    ruta.write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in resultado.items() if k != "filas"}, ensure_ascii=False, indent=2))

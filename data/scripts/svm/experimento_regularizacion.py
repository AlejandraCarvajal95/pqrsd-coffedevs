"""Experimento contra el sobreajuste: tamaño de vocabulario TF-IDF x fuerza de regularización (C).

    docker compose run --rm --user root -v ./data/datasets:/data/datasets \
        -v ./data/scripts/svm:/data/scripts/svm \
        -v ./backend/app/pipeline/svm.py:/app/app/pipeline/svm.py \
        -v ./backend/app/pipeline/modelos_svm:/app/app/pipeline/modelos_svm \
        backend python /data/scripts/svm/experimento_regularizacion.py [capa ...]

Entrena con train y mide F1 macro en train (lo que memoriza) y en val (lo que generaliza).
Guarda la mejor combinación por capa en modelos_svm/regularizacion.json, que usa entrenar.py.
"""

import json
import sys
from dataclasses import asdict

from sklearn.metrics import f1_score

sys.path.insert(0, "/data/scripts/svm")
sys.path.insert(0, "/app")
from app.pipeline import svm  # noqa: E402
from entrenar import leer, precalcular_embeddings  # noqa: E402

VOCABULARIOS = {
    "actual": svm.Vocabulario(),
    "reducido": svm.Vocabulario(max_palabras=5_000, min_df_palabras=3,
                                max_caracteres=10_000, min_df_caracteres=5),
    "muy_reducido": svm.Vocabulario(max_palabras=2_000, min_df_palabras=5,
                                    max_caracteres=4_000, min_df_caracteres=10),
}
VALORES_C = (0.005, 0.01, 0.02, 0.05, 0.2)
CAPAS = ("tipo", "area", "sentimiento", "tema_tarjetas", "tema_cartera")


def experimento(capa: str) -> dict:
    filas = leer(capa)
    etiqueta = [c for c in filas[0] if c not in ("id", "texto", "fuente", "es_banco", "split")][0]
    tr = [f for f in filas if f["split"] == "train"]
    va = [f for f in filas if f["split"] == "val"]
    xtr, ytr = [f["texto"] for f in tr], [f[etiqueta] for f in tr]
    xva, yva = [f["texto"] for f in va], [f[etiqueta] for f in va]
    resultados = []
    for nombre, vocab in VOCABULARIOS.items():
        for c in VALORES_C:
            modelo = svm.construir_modelo(c, vocabulario=vocab).fit(xtr, ytr)
            f1_tr = f1_score(ytr, modelo.predict(xtr), average="macro")
            f1_va = f1_score(yva, modelo.predict(xva), average="macro")
            resultados.append({"vocabulario": nombre, "c": c, "f1_train": round(f1_tr, 4),
                               "f1_val": round(f1_va, 4), "brecha": round(f1_tr - f1_va, 4)})
            print(f"[{capa}] {nombre:<13} C={c:<6} train={f1_tr:.3f} val={f1_va:.3f} "
                  f"brecha={f1_tr - f1_va:+.3f}", flush=True)
    # La mejor en validación; si hay empate (menos de 0,005), la de menor brecha.
    tope = max(r["f1_val"] for r in resultados)
    candidatas = [r for r in resultados if r["f1_val"] >= tope - 0.005]
    mejor = min(candidatas, key=lambda r: r["brecha"])
    print(f"[{capa}] ELEGIDA: {mejor}", flush=True)
    return {"mejor": {**mejor, "parametros": asdict(VOCABULARIOS[mejor["vocabulario"]])},
            "todas": resultados}


if __name__ == "__main__":
    capas = sys.argv[1:] or CAPAS
    precalcular_embeddings({f["texto"] for c in capas for f in leer(c)})
    ruta = svm.DIR_MODELOS / "regularizacion.json"
    salida = json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else {}
    for capa in capas:
        salida[capa] = experimento(capa)
        ruta.write_text(json.dumps(salida, ensure_ascii=False, indent=2), encoding="utf-8")

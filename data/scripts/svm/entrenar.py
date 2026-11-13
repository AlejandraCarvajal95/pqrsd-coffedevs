"""Entrena y evalúa los SVM de cada capa del embudo.

Corre dentro del contenedor del backend (mismo modelo de embeddings que en producción):

    docker compose run --rm --user root \
        -v ./data/datasets:/data/datasets \
        -v ./backend/app/pipeline/modelos_svm:/app/app/pipeline/modelos_svm \
        backend python /data/scripts/svm/entrenar.py [capa ...]

Por cada capa (data/datasets/final/capas/<capa>.csv):
1. Elige C con el split de validación (F1 macro).
2. Reentrena con train + val y evalúa en test, que el modelo nunca vio.
3. Guarda el modelo en modelos_svm/<capa>.joblib y las métricas en metricas.json / metricas.md.

El acierto por fuente en test sirve para detectar si el modelo aprendió el estilo de una
fuente (por ejemplo, "texto traducido = reclamo") en vez de la clase.
"""

import csv
import json
import sys
import time
import warnings
from collections import defaultdict
from datetime import date
from pathlib import Path

import joblib
import numpy as np
from sklearn.exceptions import ConvergenceWarning
from sklearn.metrics import classification_report, confusion_matrix, f1_score

sys.path.insert(0, "/app")
from app.pipeline import embeddings, svm  # noqa: E402

CAPAS = Path("/data/datasets/final/capas")
VALORES_C = (0.05, 0.2, 1.0)


def leer(capa: str) -> list[dict]:
    with open(CAPAS / f"{capa}.csv", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


CACHE_DISCO = Path("/data/datasets/intermedio/cache_embeddings.npz")


def precalcular_embeddings(textos: set[str]):
    """Calcula los embeddings que falten y los guarda en disco para las siguientes corridas."""
    if not svm.CACHE_EMBEDDINGS and CACHE_DISCO.exists():
        datos = np.load(CACHE_DISCO, allow_pickle=False)
        svm.CACHE_EMBEDDINGS.update(zip(datos["textos"].tolist(), datos["vectores"], strict=True))
    pendientes = [t for t in textos if t not in svm.CACHE_EMBEDDINGS]
    inicio = time.time()
    for i in range(0, len(pendientes), 256):
        lote = pendientes[i:i + 256]
        for t, v in zip(lote, embeddings.generar_embeddings(lote), strict=True):
            svm.CACHE_EMBEDDINGS[t] = np.asarray(v, dtype=np.float32)
    if pendientes:
        np.savez(CACHE_DISCO, textos=np.array(list(svm.CACHE_EMBEDDINGS)),
                 vectores=np.stack(list(svm.CACHE_EMBEDDINGS.values())))
    segundos = time.time() - inicio
    print(f"Embeddings: {len(pendientes)} textos nuevos en {segundos:.0f} s", flush=True)


def entrenar(capa: str) -> dict:
    filas = leer(capa)
    etiqueta = [c for c in filas[0] if c not in ("id", "texto", "fuente", "es_banco", "split")][0]
    por_split = defaultdict(list)
    for f in filas:
        por_split[f["split"]].append(f)
    x = {s: [f["texto"] for f in v] for s, v in por_split.items()}
    y = {s: [f[etiqueta] for f in v] for s, v in por_split.items()}

    # 1. Vocabulario y C: los que eligió experimento_regularizacion.py para esta capa, si
    #    existen; si no, el vocabulario por defecto y C por validación.
    ruta_reg = svm.DIR_MODELOS / "regularizacion.json"
    reg = json.loads(ruta_reg.read_text(encoding="utf-8")).get(capa) if ruta_reg.exists() else None
    vocab = svm.Vocabulario(**reg["mejor"]["parametros"]) if reg else svm.Vocabulario()
    f1_val = {}
    if reg:
        mejor_c = reg["mejor"]["c"]
        f1_val[mejor_c] = reg["mejor"]["f1_val"]
    else:
        for c in VALORES_C:
            modelo = svm.construir_modelo(c, vocabulario=vocab).fit(x["train"], y["train"])
            f1_val[c] = f1_score(y["val"], modelo.predict(x["val"]), average="macro")
        mejor_c = max(f1_val, key=f1_val.get)

    # 2. Modelo final con train + val; evaluación en test. Se registra si el optimizador
    # convergió: si no, el modelo quedó a medio camino y hay que subir max_iter.
    with warnings.catch_warnings(record=True) as avisos:
        warnings.simplefilter("always", ConvergenceWarning)
        modelo = svm.construir_modelo(mejor_c, vocabulario=vocab).fit(
            x["train"] + x["val"], y["train"] + y["val"])
    convergio = not any(issubclass(a.category, ConvergenceWarning) for a in avisos)
    pred = modelo.predict(x["test"])
    probs = modelo.predict_proba(x["test"]).max(axis=1)
    clases = [str(c) for c in modelo.classes_]
    reporte = classification_report(y["test"], pred, output_dict=True, zero_division=0)

    acierto_fuente = defaultdict(lambda: [0, 0])
    for f, p in zip(por_split["test"], pred, strict=True):
        acierto_fuente[f["fuente"]][0] += int(p == f[etiqueta])
        acierto_fuente[f["fuente"]][1] += 1

    # Confianza: cuánto aciertan las predicciones con probabilidad alta (para fijar umbrales).
    aciertos = np.array(pred) == np.array(y["test"])
    umbrales = {}
    for u in (0.5, 0.6, 0.7, 0.8, 0.9):
        sel = probs >= u
        umbrales[str(u)] = {
            "cobertura": round(float(sel.mean()), 3),
            "precision": round(float(aciertos[sel].mean()), 3) if sel.any() else None,
        }

    metricas = {
        "capa": capa, "etiqueta": etiqueta, "clases": clases, "c": mejor_c, "convergio": convergio,
        "vocabulario": vars(vocab),
        "f1_macro_val_por_c": {str(k): round(v, 4) for k, v in f1_val.items()},
        "n_train": len(x["train"]) + len(x["val"]), "n_test": len(x["test"]),
        "f1_macro_test": round(reporte["macro avg"]["f1-score"], 4),
        "exactitud_test": round(reporte["accuracy"], 4),
        "por_clase": {c: {k: round(v, 3) for k, v in reporte[c].items()} for c in clases},
        "matriz_confusion": {"clases": clases,
                             "valores": confusion_matrix(y["test"], pred, labels=clases).tolist()},
        "acierto_por_fuente": {k: round(a / n, 3) for k, (a, n) in sorted(acierto_fuente.items())},
        "umbrales_confianza": umbrales,
        "entrenado_en": date.today().isoformat(),
    }
    svm.DIR_MODELOS.mkdir(exist_ok=True)
    joblib.dump({"modelo": modelo, **metricas}, svm.DIR_MODELOS / f"{capa}.joblib", compress=3)
    print(f"[{capa}] C={mejor_c} F1 macro test={metricas['f1_macro_test']} "
          f"exactitud={metricas['exactitud_test']} n_test={len(x['test'])} "
          f"convergio={convergio}", flush=True)
    return metricas


def markdown(todas: dict) -> str:
    lineas = ["# Métricas de los SVM", "",
              "Evaluación en el split de test (el modelo nunca lo vio). "
              "La métrica de la demo debe salir del golden set escrito por el equipo.", "",
              "| Capa | Clases | F1 macro | Exactitud | C | Test |",
              "| --- | --- | --- | --- | --- | --- |"]
    for m in todas.values():
        lineas.append(f"| {m['capa']} | {len(m['clases'])} | {m['f1_macro_test']:.3f} | "
                      f"{m['exactitud_test']:.3f} | {m['c']} | {m['n_test']} |")
    for m in todas.values():
        lineas += ["", f"## {m['capa']}", "", "| Clase | Precisión | Exhaustividad | F1 | n |",
                   "| --- | --- | --- | --- | --- |"]
        for c, r in m["por_clase"].items():
            lineas.append(f"| {c} | {r['precision']:.2f} | {r['recall']:.2f} | "
                          f"{r['f1-score']:.2f} | {int(r['support'])} |")
        lineas += ["", "Acierto por fuente: " + ", ".join(
            f"{k} {v:.0%}" for k, v in m["acierto_por_fuente"].items()),
            "", "Umbral de confianza → cobertura / precisión: " + ", ".join(
            f"≥{u}: {d['cobertura']:.0%} / {d['precision']:.0%}"
            for u, d in m["umbrales_confianza"].items() if d["precision"] is not None)]
    return "\n".join(lineas) + "\n"


if __name__ == "__main__":
    capas = sys.argv[1:] or sorted(p.stem for p in CAPAS.glob("*.csv"))
    precalcular_embeddings({f["texto"] for c in capas for f in leer(c)})
    ruta = svm.DIR_MODELOS / "metricas.json"
    todas = json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else {}
    for capa in capas:
        todas[capa] = entrenar(capa)
    ruta.write_text(json.dumps(todas, ensure_ascii=False, indent=2), encoding="utf-8")
    (svm.DIR_MODELOS / "metricas.md").write_text(markdown(todas), encoding="utf-8")

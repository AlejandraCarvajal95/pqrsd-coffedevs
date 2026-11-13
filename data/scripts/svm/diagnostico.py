"""Diagnóstico de los SVM: sobreajuste y efecto de los pesos de clase en la capa tipo.

    docker compose run --rm --user root -v ./data/datasets:/data/datasets \
        -v ./data/scripts/svm:/data/scripts/svm \
        -v ./backend/app/pipeline/modelos_svm:/app/app/pipeline/modelos_svm \
        backend python /data/scripts/svm/diagnostico.py

1. Sobreajuste: F1 macro en una muestra de los datos con que se entrenó el modelo final
   frente al F1 en test. Una brecha grande indica que memoriza en vez de generalizar.
2. Pesos en "tipo": compara, con el split de validación, sin pesos, pesos balanceados
   (castigo mayor al equivocarse en clases chicas) y castigo extra en queja/reclamo/petición,
   que son las clases que más se confunden.
"""

import json
import random
import sys

import joblib
from sklearn.metrics import f1_score

sys.path.insert(0, "/data/scripts/svm")
sys.path.insert(0, "/app")
from entrenar import leer, precalcular_embeddings  # noqa: E402

from app.pipeline import svm  # noqa: E402

MUESTRA_TRAIN = 400


def sobreajuste() -> dict:
    resultado = {}
    muestras = {}
    for ruta in sorted(svm.DIR_MODELOS.glob("*.joblib")):
        filas = [f for f in leer(ruta.stem) if f["split"] in ("train", "val")]
        random.Random(1).shuffle(filas)
        muestras[ruta.stem] = filas[:MUESTRA_TRAIN]
    precalcular_embeddings({f["texto"] for m in muestras.values() for f in m})
    for capa, muestra in muestras.items():
        datos = joblib.load(svm.DIR_MODELOS / f"{capa}.joblib")
        etiqueta = datos["etiqueta"]
        pred = datos["modelo"].predict([f["texto"] for f in muestra])
        f1_train = f1_score([f[etiqueta] for f in muestra], pred, average="macro")
        resultado[capa] = {
            "f1_entrenamiento": round(f1_train, 3), "f1_test": datos["f1_macro_test"],
            "brecha": round(f1_train - datos["f1_macro_test"], 3),
            "f1_val_por_c": datos["f1_macro_val_por_c"],
        }
        print(f"[{capa}] F1 entrenamiento={f1_train:.3f} test={datos['f1_macro_test']:.3f} "
              f"brecha={f1_train - datos['f1_macro_test']:+.3f} | F1 val por C: "
              f"{datos['f1_macro_val_por_c']}", flush=True)
    return resultado


def pesos_tipo() -> dict:
    filas = leer("tipo")
    tr = [f for f in filas if f["split"] == "train"]
    va = [f for f in filas if f["split"] == "val"]
    precalcular_embeddings({f["texto"] for f in tr + va})
    variantes = {
        "sin_pesos": None,
        "balanceado (actual)": "balanced",
        "castigo x1.5 queja/reclamo/peticion": {"queja": 1.5, "reclamo": 1.5, "peticion": 1.5,
                                                "denuncia": 1.0, "sugerencia": 1.6},
        "castigo x2 queja/reclamo": {"queja": 2.0, "reclamo": 2.0, "peticion": 1.0,
                                     "denuncia": 1.0, "sugerencia": 1.6},
    }
    resultado = {}
    for nombre, pesos in variantes.items():
        for c in (0.05, 0.2, 1.0):
            modelo = svm.construir_modelo(c)
            modelo.named_steps["svm"].estimator.set_params(class_weight=pesos)
            modelo.fit([f["texto"] for f in tr], [f["tipo"] for f in tr])
            pred = modelo.predict([f["texto"] for f in va])
            y = [f["tipo"] for f in va]
            f1 = f1_score(y, pred, average="macro")
            por_clase = f1_score(y, pred, average=None, labels=list(modelo.classes_))
            resultado[f"{nombre} | C={c}"] = {
                "f1_macro_val": round(f1, 4),
                "por_clase": {k: round(v, 3)
                              for k, v in zip(modelo.classes_, por_clase, strict=True)},
            }
            print(f"[tipo] {nombre:<38} C={c:<5} F1 val={f1:.4f} "
                  + " ".join(f"{k[:4]}={v:.2f}" for k, v in zip(modelo.classes_, por_clase,
                                                                  strict=True)), flush=True)
    return resultado


if __name__ == "__main__":
    salida = {"sobreajuste": sobreajuste(), "pesos_tipo": pesos_tipo()}
    texto = json.dumps(salida, ensure_ascii=False, indent=2)
    (svm.DIR_MODELOS / "diagnostico.json").write_text(texto, encoding="utf-8")

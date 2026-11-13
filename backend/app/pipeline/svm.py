"""Clasificadores SVM del embudo de clasificación (mitad SVM, mitad Claude).

Cada capa es un SVM lineal entrenado con data/scripts/svm/entrenar.py sobre el dataset de
data/scripts/dataset. Los modelos viven en app/pipeline/modelos_svm/<capa>.joblib.

Capas que resuelve el SVM: tipo, área, tema (un modelo por área), sentimiento y fraude.
Las que necesitan razonamiento (información faltante, manipulación, riesgo regulatorio)
las resuelve Claude; reincidencia, prioridad y escalamiento son reglas.

Características de cada texto:
- TF-IDF de palabras (1 y 2 palabras),
- TF-IDF de caracteres (3 a 5), que tolera errores de ortografía,
- el embedding multilingüe que ya usa el RAG (app.pipeline.embeddings), así el modelo
  entiende sinónimos y usa la misma representación en entrenamiento y en producción.
El SVM va dentro de CalibratedClassifierCV: la confianza es una probabilidad calibrada.
"""

import logging
import threading
from dataclasses import dataclass, field
from pathlib import Path

import joblib
import numpy as np
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.calibration import CalibratedClassifierCV
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import FeatureUnion, Pipeline
from sklearn.svm import LinearSVC

from app.pipeline import embeddings

logger = logging.getLogger(__name__)

DIR_MODELOS = Path(__file__).parent / "modelos_svm"
CAPAS_BASE = ("tipo", "area", "sentimiento", "fraude")
AREAS_BANCO = ("tarjetas", "cartera", "seguros", "juridica")

# Solo durante el entrenamiento: embeddings ya calculados, para no repetirlos en cada ajuste.
CACHE_EMBEDDINGS: dict[str, np.ndarray] = {}


class TransformadorEmbeddings(BaseEstimator, TransformerMixin):
    """Convierte textos en el embedding del RAG (384 dimensiones, normalizado)."""

    def fit(self, textos, y=None):
        return self

    def transform(self, textos):
        textos = list(textos)
        faltan = [t for t in textos if t not in CACHE_EMBEDDINGS]
        nuevos = dict(zip(faltan, embeddings.generar_embeddings(faltan), strict=True))
        return np.array(
            [CACHE_EMBEDDINGS[t] if t in CACHE_EMBEDDINGS else nuevos[t] for t in textos],
            dtype=np.float32,
        )


def construir_modelo(c: float = 1.0, particiones_calibracion: int = 3) -> Pipeline:
    caracteristicas = FeatureUnion([
        ("palabras", TfidfVectorizer(ngram_range=(1, 2), min_df=2, max_features=20_000,
                                     sublinear_tf=True)),
        ("caracteres", TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=3,
                                       max_features=30_000, sublinear_tf=True)),
        ("embeddings", TransformadorEmbeddings()),
    ])
    svm = LinearSVC(C=c, class_weight="balanced", max_iter=5_000)
    return Pipeline([
        ("caracteristicas", caracteristicas),
        ("svm", CalibratedClassifierCV(svm, method="sigmoid", cv=particiones_calibracion)),
    ])


# ---------------------------------------------------------------------------
# Clasificación
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PrediccionCapa:
    etiqueta: str
    confianza: float  # probabilidad calibrada de la etiqueta elegida
    probabilidades: dict[str, float]


@dataclass(frozen=True)
class ResultadoSVM:
    tipo: PrediccionCapa
    area: PrediccionCapa
    sentimiento: PrediccionCapa
    tema: PrediccionCapa | None = None  # solo si el área tiene modelo de tema
    fraude: PrediccionCapa | None = None  # solo para áreas del banco
    capas: dict[str, PrediccionCapa] = field(default_factory=dict)


_modelos: dict[str, Pipeline] = {}
_candado = threading.Lock()


def modelos_disponibles() -> list[str]:
    return sorted(p.stem for p in DIR_MODELOS.glob("*.joblib"))


def _modelo(capa: str) -> Pipeline | None:
    with _candado:
        if capa not in _modelos:
            ruta = DIR_MODELOS / f"{capa}.joblib"
            if not ruta.exists():
                return None
            _modelos[capa] = joblib.load(ruta)["modelo"]
            logger.info("Modelo SVM cargado: %s", capa)
        return _modelos[capa]


def _predecir(modelo: Pipeline, texto: str) -> PrediccionCapa:
    probs = modelo.predict_proba([texto])[0]
    clases = [str(c) for c in modelo.classes_]
    i = int(np.argmax(probs))
    return PrediccionCapa(
        etiqueta=clases[i],
        confianza=round(float(probs[i]), 4),
        probabilidades={c: round(float(p), 4) for c, p in zip(clases, probs, strict=True)},
    )


def clasificar(texto: str) -> ResultadoSVM:
    """Pasa el texto por el embudo. Lanza FileNotFoundError si faltan los modelos base."""
    capas: dict[str, PrediccionCapa] = {}
    for capa in CAPAS_BASE:
        modelo = _modelo(capa)
        if modelo is None:
            if capa == "fraude":
                continue
            raise FileNotFoundError(f"Falta el modelo SVM '{capa}' en {DIR_MODELOS}")
        capas[capa] = _predecir(modelo, texto)

    area = capas["area"].etiqueta
    modelo_tema = _modelo(f"tema_{area}") if area in AREAS_BANCO else None
    if modelo_tema is not None:
        capas["tema"] = _predecir(modelo_tema, texto)
    if area not in AREAS_BANCO:
        capas.pop("fraude", None)  # el riesgo de fraude solo aplica a productos del banco

    return ResultadoSVM(
        tipo=capas["tipo"], area=capas["area"], sentimiento=capas["sentimiento"],
        tema=capas.get("tema"), fraude=capas.get("fraude"), capas=capas,
    )

# Entorno para armar el dataset de entrenamiento de los SVM.
# Uso (desde la raíz del repo):
#   docker build -t pqrsd-dataset data/scripts/dataset
#   docker run --rm -v "$PWD/data:/data" pqrsd-dataset python scripts/dataset/01_descargar.py
FROM python:3.12-slim
WORKDIR /data
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt \
 && pip install --no-cache-dir \
    https://github.com/explosion/spacy-models/releases/download/es_core_news_md-3.8.0/es_core_news_md-3.8.0-py3-none-any.whl

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Usuario sin privilegios para ejecutar la aplicación
RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# Caché del modelo de embeddings. Se monta como volumen en docker-compose;
# crearla aquí con dueño app hace que el volumen nuevo herede ese dueño.
RUN mkdir -p /modelos && chown app:app /modelos

USER app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

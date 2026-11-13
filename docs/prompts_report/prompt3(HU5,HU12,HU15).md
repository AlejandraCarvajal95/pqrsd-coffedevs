Written for: integrantes del equipo y revisores del pull request que incluya US-005, US-012 y US-015.

# Reporte de trabajo: US-005, US-012 y US-015

Este documento describe qué se construyó para las historias de carga de conocimiento (US-005), recuperación RAG (US-012) y control de costos de IA (US-015), por qué se tomaron las decisiones principales y qué quedó pendiente.

## 1. Punto de partida

Antes de este trabajo, `data/conocimiento/` tenía tres documentos ficticios (`politica_y_contratos.md`, `faq_clientes.md` y `normativa_ley_1755.md`) de la historia US-004. En el backend, `rag.py`, `clasificador.py` y `generador.py` estaban vacíos, y no existía ningún cliente de Claude ni tabla de embeddings de consultas o de consumo.

Las instrucciones del proyecto (`CLAUDE.md`) fijan tres reglas que guiaron el diseño:

- El modelo liviano (`MODELO_LIGERO`) se usa para clasificación y chat; el modelo capaz (`MODELO_BORRADOR`) solo para el borrador final.
- Los nombres de modelo y las claves vienen de variables de entorno.
- Presupuesto de IA del evento: 40 USD.

## 2. Decisión principal: embeddings locales

Anthropic no ofrece una API de embeddings. Para no depender de otro proveedor ni gastar presupuesto de Claude, los embeddings se calculan con un modelo local a través de `fastembed` (ONNX):

- Modelo: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`.
- Dimensión: 384, igual al valor por defecto de `EMBEDDING_DIM`.
- Idioma: multilingüe, con buen desempeño en español.
- Límite de entrada: unos 128 tokens. Por eso los fragmentos se limitan a 700 caracteres.
- Tamaño: unos 220 MB, descargados una vez al volumen `modelos` de Docker.

El modelo se carga de forma perezosa y una sola vez por proceso, así que `/api/health` no lo carga.

## 3. US-005: carga de conocimiento y embeddings

**Archivos:** `backend/app/pipeline/conocimiento.py`, `backend/app/pipeline/embeddings.py`, `data/scripts/cargar_conocimiento.py`.

**Qué hace:**

1. Lee cada `.md` de `data/conocimiento/`.
2. Divide por encabezados: `##` abre una sección y `###` se cita como "Sección › Subsección".
3. Empaqueta párrafos sin pasar de 700 caracteres. Las tablas largas se parten y cada parte repite el encabezado de la tabla.
4. Calcula el embedding de cada fragmento. El texto que se vectoriza incluye el título del documento y la sección, para no perder contexto.
5. Guarda en `fragmentos_conocimiento` el documento, la sección, un índice, el contenido y el vector.

**Idempotencia.** La llave es (documento, sección, índice), que ya es única en la tabla. Al volver a cargar:

- Si el contenido no cambió, no se recalcula el embedding.
- Si cambió, se actualiza la fila y conserva su id.
- Si el fragmento desapareció del archivo, se borra.
- Con `--eliminar-huerfanos` se borran los documentos cuyo archivo ya no existe.
- Con `--forzar` se recalculan todos los embeddings, por ejemplo si cambia el modelo.

**Verificación:** con el modelo real, la primera carga creó 47 fragmentos de los tres documentos. La segunda no calculó ningún embedding y no duplicó nada.

**Uso:**

```bash
docker compose run --rm backend python /data/scripts/cargar_conocimiento.py
```

## 4. US-012: recuperación RAG

**Archivo:** `backend/app/pipeline/rag.py`.

**Función principal:** `recuperar(sesion, texto, k=None, umbral=None)`.

- Calcula el embedding de la consulta y busca los `k` fragmentos más cercanos por similitud coseno (por defecto 4).
- Descarta los que no alcanzan el umbral `RAG_UMBRAL_SIMILITUD`.
- Si ninguno lo supera, devuelve el estado `"sin contexto suficiente"` y una lista vacía. Así no llega nada irrelevante al generador.
- `como_contexto()` arma el texto para el prompt, con etiquetas `[F1]`, `[F2]`, etc., para que el borrador pueda citarlas.
- `citas()` devuelve la estructura que se guarda en `borradores.citas`.

**Calibración del umbral.** Se midió con el modelo real sobre diez consultas de prueba. Con el umbral en 0.30:

- Las consultas relevantes quedan entre 0.31 y 0.75 (por ejemplo, "Quiero cancelar el seguro de vida de mi tarjeta" llega a 0.75).
- Las consultas sin relación con el banco ("receta del ajiaco", "comprar un carro usado") no pasan de 0.27.

El umbral inicial era 0.45 y dejaba fuera casos relevantes, así que se bajó a 0.30. Es un valor configurable.

**Caché de consultas.** Tabla `cache_embeddings_consulta`:

- La llave es un hash SHA-256 de (modelo + texto normalizado). La normalización colapsa espacios y saltos de línea.
- Guarda el embedding, no los resultados. Así, si se recarga el conocimiento, la búsqueda ya refleja los cambios sin invalidar la caché.
- Cuenta los usos de cada consulta.

**Verificación:** en la prueba de punta a punta, la misma consulta con espacios distintos reutilizó la caché y el contador de usos llegó a 2.

## 5. US-015: control de costos de IA

**Archivos:** `backend/app/pipeline/costos.py`, `backend/app/api/costos.py`, `backend/app/models/consumo.py`, y los campos nuevos en `backend/app/config.py`.

**Punto de entrada único.** Toda llamada a Claude debe pasar por `llamar_claude(tarea, mensajes, ...)`. Así los límites, el conteo y la alerta no dependen de que cada módulo los recuerde.

**Enrutamiento por tarea:**

| Tarea | Rol de modelo | `max_tokens` | Entrada máxima (caracteres) | Esfuerzo |
| --- | --- | --- | --- | --- |
| `clasificador` | ligero | 400 | 12 000 | low |
| `chat` | ligero | 700 | 12 000 | low |
| `edicion` | ligero | 1 500 | 16 000 | low |
| `generador` | borrador (capaz) | 2 000 | 24 000 | medium |

Los nombres de modelo se leen de `MODELO_LIGERO` y `MODELO_BORRADOR`. Si falta alguno, la llamada falla con un mensaje claro antes de llamar a la API.

**Límites:**

- Si se pide más `max_tokens` que el tope de la tarea, o la entrada supera el máximo, se lanza `LimiteExcedido` y **no se llama a la API**.
- Máximo de 12 mensajes por sesión de chat (`MAX_MENSAJES_SESION`). El conteo vive en memoria del proceso, con un tope de 10 000 sesiones. Se reinicia si se reinicia el backend, lo cual basta para la demo.
- El backend convierte estos errores en respuestas JSON: 429 para límites, 413 para entradas largas y 503 para fallas de la API. El mensaje se muestra en español y no incluye el contenido enviado ni la clave.

**Contador de gasto:**

- Cada llamada guarda una fila en `consumos_ia`, con tokens de entrada, salida y de caché, modelo, tarea y costo estimado en USD.
- La fila se escribe en una sesión propia y se confirma antes de devolver la respuesta, así que el gasto queda registrado aunque después falle el procesamiento.
- `GET /api/costos` devuelve el total y el desglose por tarea.

**Alerta y tope:**

- Desde `GASTO_ALERTA_USD` (30 USD) cada llamada escribe una advertencia en el log y marca `alerta_presupuesto=True` en la respuesta.
- Desde `GASTO_TOPE_USD` (40 USD) se bloquean las llamadas con el código `presupuesto_agotado`.

**Precios.** Son variables de entorno, con los valores que usamos como referencia: Haiku 5.5 a 0.10 / 0.50 USD y Sonnet 5.5 a 2 / 10 USD por millón de tokens de entrada y salida. Hay que confirmarlos en la página de precios de Anthropic antes de la entrega. Los factores de caché son 1.25x para escritura y 0.1x para lectura.

**Verificación:** las pruebas de `test_costos.py` cubren el enrutamiento de modelos, los límites de tokens y de entrada, el límite de mensajes por sesión, el cálculo de costos con caché, la alerta, el tope y el endpoint. Usan un cliente falso, así que no gastan presupuesto.

## 6. Pruebas y calidad

- **Lint:** `ruff check` pasa sobre `backend/` y `data/scripts/`.
- **Pruebas:** 37 pasan contra PostgreSQL con pgvector 16, igual que en la CI. Incluyen la carga idempotente, la fragmentación, el RAG con umbral y caché, y los límites de costos.
- **Prueba de punta a punta:** con el modelo real, carga dos veces, consulta el RAG y revisa la caché sobre una base de datos temporal.
- **Compose:** la configuración de `docker-compose.yml` es válida (`docker compose config`).

Las pruebas no usan el modelo real de embeddings: usan un reemplazo determinista (`embedder_falso` en `conftest.py`), para que la CI no descargue 220 MB.

## 7. Archivos afectados

Modificados:

- `.env.example`, `README.md`, `backend/Dockerfile`, `backend/requirements.txt`
- `backend/app/config.py`, `backend/app/main.py`, `backend/app/models/__init__.py`
- `backend/app/pipeline/rag.py`, `backend/tests/conftest.py`
- `data/scripts/cargar_conocimiento.py`, `docker-compose.yml`

Nuevos:

- `backend/app/api/costos.py`
- `backend/app/models/cache_consulta.py`, `backend/app/models/consumo.py`
- `backend/app/pipeline/conocimiento.py`, `backend/app/pipeline/costos.py`, `backend/app/pipeline/embeddings.py`
- `backend/tests/test_conocimiento.py`, `backend/tests/test_costos.py`, `backend/tests/test_rag.py`

Ninguno contiene claves ni datos reales. Los documentos de conocimiento son ficticios.

## 8. Pendiente antes del pull request

1. **Construir la imagen completa.** No se ejecutó `docker compose up --build` con el stack entero. Hay que comprobar el cambio de permisos de `/modelos` en el Dockerfile.
2. **Confirmar precios** de Haiku 5.5 y Sonnet 5.5 en la página oficial de Anthropic.
3. **Verificar los plazos legales** citados en `normativa_ley_1755.md`, como indica US-004. Este reporte no los cambia.
4. **Límite del RAG para plazos.** La consulta "¿cuántos días tiene el banco para responder mi queja?" devuelve preguntas frecuentes y no la tabla de plazos. Los vencimientos deben calcularse con la configuración del motor de plazos (US-016), no con el RAG.
5. **Autenticación de `/api/costos`.** Hoy es pública y solo muestra cifras agregadas. Se restringirá con US-022 (acceso por roles).
6. **Primera descarga del modelo.** La descarga tarda varios minutos en redes lentas. Conviene hacerla antes de la demo.
7. **Revisión por otra persona**, como exige `CLAUDE.md` antes de hacer merge a `main`.

## 9. Próximos pasos

- US-013 (borrador con citas): usa `recuperar` y `llamar_claude(Tarea.generador, ...)`. Si el RAG no tiene contexto suficiente, el borrador debe decirlo y derivar el caso a una persona.
- US-007 y US-008 (radicación): cuando el chat llame a Claude, debe pasar `sesion_chat` para aplicar el límite de mensajes.
- US-016 (plazos): calcular el vencimiento con la configuración de plazos y festivos, sin depender del RAG.

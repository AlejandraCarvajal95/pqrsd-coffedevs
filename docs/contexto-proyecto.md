# Contexto del proyecto — PQRSD Coffee Devs

Resumen para retomar el trabajo (personas o asistentes de IA). Estado al 12 de noviembre de 2026, rama `develop` (hasta el PR #9).
Las convenciones obligatorias están en [CLAUDE.md](../CLAUDE.md); el backlog completo en [backlog.md](backlog.md) y la propuesta en [arquitectura.md](arquitectura.md).

## 1. Qué es
Plataforma web de gestión inteligente de PQRSD (peticiones, quejas, reclamos, sugerencias y denuncias) de un **banco ficticio**, para el hackathon NEPXA (reto: PQRSD con términos legales de 15 días hábiles; responder tarde o clasificar mal es una multa).
Principio central: **la IA propone y una persona aprueba**. Nada sale al ciudadano sin aprobación humana.

## 2. Restricciones del evento
- **Entrega:** viernes 13 de noviembre de 2026, 10:30 (código y documentación en el repositorio; el servidor se elimina al cierre).
- **Servidor:** Ubuntu 24.04, 2 vCPU, 8 GB de RAM, Docker sin sudo; solo puertos 22, 80 y 443.
- **Presupuesto de IA:** 40 USD en total para todo el evento.
- **Datos:** solo ficticios. Nunca `.env`, API keys ni `.pem` en el repositorio.

## 3. Flujo acordado (diagrama del equipo)

### Lado del ciudadano
1. **Resolución de dudas:** chat con RAG y Haiku. Si la base de conocimiento resuelve la duda, no se radica nada (desvío).
2. **Diligenciar la PQRSD:** chatbot de IA que extrae los datos, o el formulario.
3. **Consultar la PQRSD por número de radicado.**

### Pipeline (en segundo plano, al radicar)
4. **Clasificación:** el SVM clasifica la PQRSD (hoy es híbrida: Claude decide el tipo y el SVM el área, el tema, el sentimiento y el riesgo de fraude).
5. **Borrador con Sonnet:** recupera normativa con el RAG, redacta el borrador con citas y lo guarda en la base de datos.

### Lado del empleado
6. **Panel admin:** semáforo por tiempo, clasificación por área y calendario de vencimientos.
7. **Chatbot para responder la PQRSD:** Sonnet, con system prompt y base de conocimiento; el empleado ajusta el borrador conversando.
8. **Ver las PQRSD enviadas** (aprobadas).
9. **Retroalimentación:** las ideas o correcciones del agente se guardan como `.md` en la base de conocimiento para mejorar respuestas futuras.
10. **Descargar la BD** (exportación desde el panel).

## 4. Stack y despliegue
- `docker compose up --build` levanta los servicios:
  - **db:** pgvector/pgvector:pg16.
  - **backend:** FastAPI, Python 3.12, SQLAlchemy 2 y psycopg 3.
  - **frontend:** React 19 con Vite, servido por nginx.
  - **nginx:** el único que publica un puerto (80); `/api/` va al backend y `/` al frontend.
- **Volúmenes:** `pgdata` (base de datos), `modelos` (modelo de embeddings descargado) y `./data` montado en `/data` como solo lectura.
- **Variables:** todas en `.env` (plantilla en `.env.example`).
  - Obligatorias: `ANTHROPIC_API_KEY` y `DB_URL`.
  - Modelos: `MODELO_LIGERO` (Haiku) y `MODELO_BORRADOR` (Sonnet).
  - Embeddings y RAG: `EMBEDDING_*`, `RAG_TOP_K` y `RAG_UMBRAL_SIMILITUD`.
  - Costos: `GASTO_ALERTA_USD`, `GASTO_TOPE_USD`, `MAX_MENSAJES_SESION` y `PRECIO_*`.
- **Embeddings:** locales con fastembed (`paraphrase-multilingual-MiniLM-L12-v2`, 384 dimensiones), sin costo de API.

## 5. Qué está hecho (en `develop`)

| Historia | Qué hay | Dónde |
|---|---|---|
| US-001 a US-003 | Docker, modelo de datos con pgvector, configuración segura | `docker-compose.yml`, `app/config.py`, `app/db.py`, `app/models/` |
| CI | GitHub Actions: secretos, backend (ruff y pytest), frontend (build), docker (humo) | `.github/workflows/ci.yml` |
| US-004 y US-005 | Base de conocimiento del banco ficticio y carga de embeddings | `data/conocimiento/*.md`, `data/scripts/cargar_conocimiento.py`, `app/pipeline/conocimiento.py` |
| US-007 | Radicar por formulario | `POST /api/pqrsd`, página `/radicar` |
| US-008 | Chat de radicación con extracción de campos | `/api/chat/radicacion/{mensaje,confirmar}`, `app/pipeline/radicacion_chat.py`, página `/radicar/chat` |
| US-009 | Chat de desvío (responde solo con fragmentos citados `[F#]`) | `/api/chat/{consulta,resultado,continuar,metricas}`, `app/pipeline/desvio.py`, página `/chat` |
| US-010 | Consulta de estado por radicado | `GET /api/pqrsd/{radicado}` (con límite de consultas por IP), página `/estado` |
| US-011 y SVM | Clasificación híbrida | `app/pipeline/clasificador.py`, `svm.py`, `clasificacion_hibrida.py`, `modelos_svm/*.joblib`, scripts en `data/scripts/svm/` y `data/scripts/dataset/` |
| US-012 (parcial) | RAG con caché de embeddings de consultas | `app/pipeline/rag.py` (hoy lo usa solo el desvío) |
| US-015 | Control de costos: contador por tarea, alerta a 30 USD y tope a 40 USD | `app/pipeline/costos.py`, `GET /api/costos` |
| Identidad visual | Tokens, logo y portal del ciudadano | `docs/identidad-visual.md`, `frontend/src/styles/` |

- **Orquestador** (`app/pipeline/orquestador.py`): hoy solo clasifica (Claude, luego SVM) y guarda.
- **Pruebas:** 156 en verde. Verificado en Docker: radicar y clasificar tarda unos 6 s.

## 6. Qué falta (priorizado para la entrega)

Ya está hecho todo el flujo del diagrama: borrador con Sonnet y RAG (US-012 y US-013), vencimiento en días hábiles (US-016), semáforo (US-017), bandeja con calendario y enviadas (US-019), editor con aprobación (US-020), chat del empleado para ajustar el borrador (US-021), acceso al panel (US-022, sin roles por área), aprendizajes del equipo en `.md` (US-023) y descarga de la base en CSV. Ver el README.

1. **Ensayo completo con la IA real** siguiendo `docs/demo.md`, y grabación de respaldo. El chat del empleado y los borradores se probaron con Claude simulado.
2. **Despliegue en el servidor:** lista "Antes de la demo en el servidor" del README (clave del panel, permisos de la carpeta de aprendizajes y carga del conocimiento).
3. **PR de `develop` a `main`** con la CI en verde.
4. **README:** completar la columna "Persona" de la tabla "Quién hace qué".
5. Si sobra tiempo: alertas escalonadas (US-018) y roles por área (resto de US-022).

## 7. Problemas conocidos
- **Sin Alembic:** `create_all` no agrega columnas a tablas existentes. Tras cambios de modelo, usar `docker compose down -v` (borra los datos y el modelo descargado) o un `ALTER` a mano. Pasó con `tema`, `sentimiento`, `riesgo_fraude` y `clasificacion_detalle` en `pqrsd`.
- **Contraseña de Postgres:** `POSTGRES_PASSWORD` solo se aplica al crear el volumen. Si se cambia en `.env`, hay que hacer `ALTER USER` o recrear el volumen.
- **nginx y el backend recreado:** nginx guarda la IP del backend al arrancar. Si se recrea el backend y aparece un 502, ejecutar `docker compose restart nginx`.
- **Variables de `.env`:** se leen al crear el contenedor. Tras cambiarlas, usar `docker compose up -d <servicio>`; no basta `restart`.
- **Gasto en pruebas:** con una API key real en `.env`, radicar llama a Claude (fracción de centavo por PQRSD). Las pruebas automáticas no llaman a la API.

## 8. Cómo trabajar
- Una rama por historia desde `develop`, commits en español y PR hacia `develop` revisado por otra persona. Nunca merge directo a `main`.
- La CI debe quedar en verde.
- Correr las pruebas del backend: ver la sección "Pruebas y CI" del README.
- Prompts de IA en `backend/app/pipeline/prompts/*.md` y nombres de modelo solo por variable de entorno.
- No inventar normas ni datos.

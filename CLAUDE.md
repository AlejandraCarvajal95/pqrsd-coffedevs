# CLAUDE.md — convenciones del proyecto PQRSD Coffee Devs

Guía para personas y asistentes de IA que trabajen en este repositorio.

## Idioma
- Comentarios, docstrings, mensajes de commit y términos de dominio en **español** (radicado, borrador, revisión, bandeja, vencimiento…).
- Los identificadores siguen el dominio: `PQRSD`, `Borrador`, `Revision`, `generar_radicado`, `obtener_sesion`.

## Backend
- FastAPI + SQLAlchemy 2.0 tipado (`Mapped[...]`) + psycopg v3.
- **Todas las rutas van bajo `/api`**: nginx reenvía `/api/...` a `backend:8000` sin quitar el prefijo. Cada módulo de `app/api/` define un `APIRouter` y se incluye con prefijo `/api`.
- Sesión de base por petición con la dependencia `obtener_sesion` de `app/db.py`.
- Enums guardados como texto con CHECK (`native_enum=False`), vía `enum_texto` en `app/models/base.py`.
- `borradores.texto_original` es inmutable (trigger en la base). Las ediciones van a `texto_actual` y se registran en `revisiones` (usar `Borrador.editar`).
- El radicado (`PQRSD-AAAA-XXXXXX`) es aleatorio y no consecutivo; al insertar, reintentar si hay `IntegrityError` por colisión.

### Sin Alembic (decisión consciente de hackathon)
- El esquema se crea al arrancar con `Base.metadata.create_all` (solo crea lo que no existe; no altera tablas existentes).
- Si cambias una columna o un enum: en desarrollo, `docker compose down -v && docker compose up --build` (borra los datos). En el servidor del evento, coordina con el equipo y aplica el `ALTER` a mano.
- Si el proyecto sigue después del hackathon, migrar a Alembic.

### Embeddings
- La dimensión del vector viene de la variable `EMBEDDING_DIM` (por defecto 384). No la escribas en el código.
- Si cambia, hay que recrear `fragmentos_conocimiento`. El índice HNSW de pgvector admite hasta 2000 dimensiones.

## IA (Claude)
- **La IA propone y una persona aprueba.** Nada se envía al ciudadano sin aprobación humana.
- Modelo **liviano** (`MODELO_LIGERO`) para chat y clasificación; modelo **más capaz** (`MODELO_BORRADOR`) solo para el borrador final.
- Los nombres de modelo vienen de variables de entorno; nunca escritos en el código.
- Los prompts viven en archivos `.md` dentro de `backend/app/pipeline/prompts/`, no como cadenas en el código.
- **No inventar normas ni datos.** Las respuestas citan fragmentos recuperados por el RAG; si no hay soporte, se dice.
- Los pasos del pipeline se encadenan en `pipeline/orquestador.py`, que corre en segundo plano al radicar. Si un paso de IA falla, la PQRSD queda para revisión humana; nunca se inventa un resultado.
- Chat de desvío (`pipeline/desvio.py`): responde solo con fragmentos citados (`[F#]`); sin contexto suficiente no llama a Claude y devuelve un mensaje fijo.
- Presupuesto total de IA del evento: 40 USD. Registrar tokens de entrada y salida en `borradores`.

## Datos y secretos
- **Solo datos ficticios.** Nada de datos personales reales de ciudadanos.
- **Nunca secretos en el repositorio**: ni API keys, ni contraseñas, ni `.pem`. Todo va en `.env` (ignorado por git); `.env.example` solo lleva marcadores `cambiar-esto`.
- `config.py` usa `SecretStr` para `ANTHROPIC_API_KEY` y `DB_URL`: no imprimas ni registres sus valores.
- Si se sube una clave por error: revocarla y generar otra (ver README). Borrar el commit no basta.

## Infraestructura
- Servidor del evento: Ubuntu 24.04, 2 vCPU, 8 GB de RAM, solo puertos 22, 80 y 443.
- Solo nginx publica el puerto 80; `db`, `backend` y `frontend` usan `expose`.
- Las variables de `.env` se leen al crear el contenedor: tras cambiar `.env`, usar `docker compose up -d <servicio>` (no basta `restart`).

## Flujo de trabajo
- Una rama por historia (`feat/...`), commits claros en español y pull request revisado por otra persona. No hacer merge directo a `main`.
- No agregar dependencias innecesarias; fijar versiones exactas.

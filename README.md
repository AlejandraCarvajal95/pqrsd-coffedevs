# PQRSD Coffee Devs

Plataforma web de gestión inteligente de PQRSD (peticiones, quejas, reclamos, sugerencias y denuncias) del equipo Coffee Devs para el hackathon NEPXA.
Cada PQRSD se radica, Claude la clasifica (tipo, área y confianza), un RAG sobre pgvector recupera la normativa aplicable y Claude redacta un borrador con citas.
Una persona revisa, edita y aprueba la respuesta en una bandeja con semáforo de vencimiento: nada se envía al ciudadano sin aprobación humana.

## Cómo correrlo

Requisitos: Docker y Docker Compose.

```bash
cp .env.example .env
```

Completa `.env`: reemplaza cada `cambiar-esto` por un valor propio (la contraseña de `POSTGRES_PASSWORD` debe coincidir con la que va dentro de `DB_URL`). Luego:

```bash
docker compose up --build
```

| URL | Qué es |
| --- | --- |
| http://localhost/ | Frontend (React) |
| http://localhost/api/health | Estado del backend y de la base (`{"estado":"ok","db":true}`) |
| http://localhost/api/docs | Documentación interactiva de la API (Swagger) |

Solo nginx publica un puerto (80). La base y el backend quedan en la red interna de Docker. Para entrar a la base:

```bash
docker compose exec db psql -U pqrsd -d pqrsd
```

(usa el usuario y la base que pusiste en `.env`). Para borrar todo y empezar de cero: `docker compose down -v`.

### Cargar la base de conocimiento (RAG)

Con los servicios arriba, carga `data/conocimiento/*.md` en pgvector:

```bash
docker compose run --rm backend python /data/scripts/cargar_conocimiento.py
```

Los embeddings se calculan con un modelo local (`fastembed`), que no gasta presupuesto de API. La primera vez el script descarga el modelo (unos 220 MB) al volumen `modelos`. Si lo vuelves a correr, no duplica fragmentos: solo recalcula los que cambiaron. Usa `--forzar` si cambias `EMBEDDING_MODELO` y `--eliminar-huerfanos` si borras un documento.

El gasto estimado en la API de Claude, total y por tarea, se consulta en http://localhost/api/costos. Desde `GASTO_ALERTA_USD` (30) el backend escribe una alerta en el log, y al llegar a `GASTO_TOPE_USD` (40) bloquea las llamadas.

### Radicar una PQRSD (US-007)

Abre http://localhost/radicar, o usa "Continuar con una PQRSD" desde el chat. El endpoint es `POST /api/pqrsd` con `nombre_ciudadano`, `contacto` (correo o teléfono, ficticios), `asunto`, `descripcion` (máximo 4000 caracteres) y `canal` (`formulario` o `chat`). Responde 201 con el radicado y deja la PQRSD en estado `recibida`. Luego dispara el pipeline de IA en segundo plano (`pipeline/orquestador.py`). Si falta un campo, responde 422 con los nombres en `campos` y no guarda nada.

```bash
curl -s -X POST localhost/api/pqrsd -H 'Content-Type: application/json' \
  -d '{"nombre_ciudadano":"Ciudadana Ficticia","contacto":"ficticia@ejemplo.test","asunto":"Cobro doble","descripcion":"Me cobraron la cuota de manejo dos veces."}'
```

### Consultar el estado de una PQRSD (US-010)

Abre http://localhost/estado e ingresa el radicado. El endpoint es `GET /api/pqrsd/{radicado}` y devuelve solo `radicado`, `estado` (`recibida`, `en_tramite` o `respondida`), `etiqueta`, `fecha_radicacion` y `fecha_vencimiento` (nula hasta que exista el cálculo de plazos). Un radicado inexistente da siempre el mismo 404 genérico, y cada IP puede hacer 20 consultas por minuto (después, 429).

```bash
curl -s localhost/api/pqrsd/PQRSD-2026-ABC234
```

### Chat de desvío de consultas (US-009)

Abre http://localhost/chat. El asistente responde solo con fragmentos de la base de conocimiento y muestra sus fuentes. Si no encuentra información suficiente, lo dice sin llamar a Claude y ofrece continuar con una PQRSD. Necesita el conocimiento cargado (paso anterior) y una `ANTHROPIC_API_KEY` real para las preguntas con contexto.

| Endpoint | Qué hace |
| --- | --- |
| `POST /api/chat/consulta` | `{"sesion_id": null, "mensaje": "..."}`: responde con `respuesta`, `cobertura` (total, parcial o ninguna), `fuentes`, `ofrecer_radicar` y `pregunta_resuelto`. El primer mensaje devuelve el `sesion_id` que se reenvía después. |
| `POST /api/chat/resultado` | `{"sesion_id", "resolvio": true}`: registra si se resolvió la duda. |
| `POST /api/chat/continuar` | `{"sesion_id"}`: sugiere asunto y descripción de una PQRSD con lo conversado. No la crea. |
| `GET /api/chat/metricas` | Consultas totales, con respuesta, sin contexto, resueltas sin radicar, que continuaron a PQRSD y tasa de desvío. |

Prueba rápida desde la terminal:

```bash
curl -s -X POST localhost/api/chat/consulta -H 'Content-Type: application/json' \
  -d '{"mensaje":"¿Cuánto cuesta la cuota de manejo?"}'
```

Para probar las 12 consultas de `data/ejemplos/consultas_desvio.json` contra la API real (gasta presupuesto: hasta 12 llamadas al modelo liviano):

```bash
python3 data/scripts/probar_desvio.py
```

## Estructura

```
backend/            API FastAPI (Python 3.12)
  app/main.py       app, lifespan y rutas bajo /api
  app/config.py     variables de entorno (pydantic-settings)
  app/db.py         engine, sesión e inicialización del esquema
  app/models/       tablas: pqrsd, borradores, revisiones, fragmentos_conocimiento,
                    cache_embeddings_consulta, consumos_ia, consultas_desvio
  app/api/          endpoints: costos y chat de desvío (los demás, pendientes)
  app/pipeline/     RAG, costos y desvío; clasificador y generador pendientes; prompts/ en .md
frontend/           React + Vite, servido por nginx en su contenedor
nginx/nginx.conf    proxy: /api/ -> backend:8000, / -> frontend
data/               conocimiento y ejemplos ficticios, scripts de carga
docs/               arquitectura, backlog y guion de demo
```

Convenciones del equipo: ver [CLAUDE.md](CLAUDE.md).

## Pruebas y CI

Cada pull request hacia `main` o `develop` corre el pipeline de [.github/workflows/ci.yml](.github/workflows/ci.yml) en GitHub Actions:

| Check | Qué valida |
| --- | --- |
| Secretos fuera del repo | No hay `.env` ni `.pem` versionados ni claves en el historial |
| Backend (lint y pruebas) | `ruff check` y `pytest` contra un PostgreSQL con pgvector |
| Frontend (build) | `npm ci` y `npm run build` |
| Docker compose (humo) | Levanta todo, `/api/health` devuelve `db: true`, `/` da 200 y existen las 4 tablas |

`main` está protegida: solo se fusiona por pull request y con los cuatro checks en verde.

Para correr las pruebas del backend en local (con el `docker compose` arriba; usa tu contraseña de `.env`):

```bash
docker compose exec db psql -U pqrsd -d pqrsd -c "CREATE DATABASE pqrsd_test"
```

```bash
docker run --rm --network pqrsd-coffedevs_default -v "$PWD/backend:/src:ro" -e ANTHROPIC_API_KEY=clave-falsa -e DB_URL=postgresql+psycopg://pqrsd:TU_CONTRASEÑA@db:5432/pqrsd_test python:3.12-slim sh -c "cp -r /src /w && cd /w && pip install -q -r requirements-dev.txt && ruff check . && pytest"
```

Las pruebas nuevas van en `backend/tests/` (archivos `test_*.py`). Usa la fixture `sesion`: deshace todo al terminar y no deja datos.

## Si se sube una clave por error

1. **Revócala de inmediato** en la consola del proveedor (Anthropic, servidor, etc.) y genera una nueva. Asume que ya está comprometida.
2. Pon la clave nueva solo en tu `.env` local o en el del servidor.
3. Borrar el commit **no basta**: la clave sigue en el historial, en los forks y en las copias locales de todo el equipo. Limpiar el historial (por ejemplo con `git filter-repo`) es opcional y no reemplaza la revocación.
4. Avisa al equipo.

Antes de hacer push puedes revisar:

```bash
git ls-files | grep -E '\.env$|\.pem$'
```

```bash
git log -p --all | grep -iE 'sk-[a]nt-|BEGIN [A-Z ]*PRIVATE [K]EY'
```

Ambos comandos deben salir vacíos. (Los corchetes evitan que el propio README coincida con la búsqueda.)

## Quién hace qué

| Persona | Responsabilidad | Historias |
| --- | --- | --- |
| | | |
| | | |
| | | |
| | | |

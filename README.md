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

## Estructura

```
backend/            API FastAPI (Python 3.12)
  app/main.py       app, lifespan y rutas bajo /api
  app/config.py     variables de entorno (pydantic-settings)
  app/db.py         engine, sesión e inicialización del esquema
  app/models/       tablas: pqrsd, borradores, revisiones, fragmentos_conocimiento
  app/api/          endpoints de negocio (pendiente)
  app/pipeline/     clasificador, RAG y generador (pendiente); prompts/ en .md
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

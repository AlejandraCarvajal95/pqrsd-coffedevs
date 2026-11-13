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

El primer paso del pipeline es el clasificador (US-011, `pipeline/clasificador.py`). El modelo liviano, con el prompt y los ejemplos de `prompts/clasificador.md`, asigna `tipo`, `area` (Tarjetas de Crédito, Cartera, Seguros de Vida o Jurídica) y `confianza` (0 a 1), y deja la PQRSD en `clasificada`. Si la salida no es válida reintenta una vez. Si vuelve a fallar, o la API o el presupuesto fallan, la deja en `pendiente_revision_clasificacion` para que la clasifique una persona. Para ver el resultado:

```bash
docker compose exec db psql -U pqrsd -d pqrsd -c "select radicado, estado, tipo, area, confianza from pqrsd"
```

```bash
curl -s -X POST localhost/api/pqrsd -H 'Content-Type: application/json' \
  -d '{"nombre_ciudadano":"Ciudadana Ficticia","contacto":"ficticia@ejemplo.test","asunto":"Cobro doble","descripcion":"Me cobraron la cuota de manejo dos veces."}'
```

Con la PQRSD ya `clasificada`, el pipeline redacta el borrador (US-012 y US-013, `pipeline/generador.py`). El RAG recupera los fragmentos de `data/conocimiento/` que superan `RAG_UMBRAL_SIMILITUD` y el modelo más capaz (`MODELO_BORRADOR`), con el prompt de `prompts/borrador_pqrsd.md`, escribe la carta citando cada afirmación con `[F1]`, `[F2]`… El borrador queda en la tabla `borradores` con sus citas y sus tokens, y la PQRSD pasa a `borrador_listo` para que una persona lo revise. Hay que cargar antes la base de conocimiento (ver arriba): sin ella todo borrador sale "sin contexto".

- **Sin contexto suficiente:** el modelo recibe el aviso de que no hay fragmentos y el borrador empieza con `[AVISO AUTOMÁTICO DEL SISTEMA]`; no se cita ninguna norma.
- **Citas:** las etiquetas que no corresponden a un fragmento recuperado se borran. Cada cita guardada lleva `etiqueta`, `fragmento_id`, `documento`, `seccion` y `similitud`.
- **Si falla la API, el modelo declina o se agotó el presupuesto:** no se crea borrador y la PQRSD sigue `clasificada`. La clasificación se guarda antes de pedir el borrador, así que nunca se pierde.
- **En revisión de clasificación** (`pendiente_revision_clasificacion`): no se genera borrador hasta que una persona confirme tipo y área.

Para ver el borrador y sus citas:

```bash
docker compose exec db psql -U pqrsd -d pqrsd -c "select p.radicado, p.estado, b.modelo, b.tokens_entrada, b.tokens_salida, jsonb_array_length(b.citas) as citas from pqrsd p join borradores b on b.pqrsd_id = p.id order by b.creado_en desc limit 5"
```

### Consultar el estado de una PQRSD (US-010)

Abre http://localhost/estado e ingresa el radicado. El endpoint es `GET /api/pqrsd/{radicado}` y devuelve solo `radicado`, `estado` (`recibida`, `en_tramite` o `respondida`), `etiqueta`, `fecha_radicacion` y `fecha_vencimiento` (nula hasta que exista el cálculo de plazos). Un radicado inexistente da siempre el mismo 404 genérico, y cada IP puede hacer 20 consultas por minuto (después, 429).

```bash
curl -s localhost/api/pqrsd/PQRSD-2026-ABC234
```

### Chat de radicación (US-008)

Abre http://localhost/radicar/chat. El ciudadano cuenta su caso en lenguaje natural; el agente (modelo liviano, prompt en `pipeline/prompts/radicacion.md`) extrae los campos y pide los que faltan. Cuando están completos aparece un resumen y, al confirmarlo, se radica con el mismo flujo del formulario (`POST /api/pqrsd`, canal `chat`). Necesita una `ANTHROPIC_API_KEY` real.

| Endpoint | Qué hace |
| --- | --- |
| `POST /api/chat/radicacion/mensaje` | `{"sesion_id": null, "mensaje": "..."}`: responde con `respuesta`, `campos` extraídos, `faltantes`, `listo_para_confirmar`, `limite_alcanzado` y `resumen` (nombre, contacto, asunto y descripción). El primer mensaje devuelve el `sesion_id` que se reenvía después. |
| `POST /api/chat/radicacion/confirmar` | `{"sesion_id"}`: radica la PQRSD y devuelve el radicado. 409 si faltan datos. Si se repite, devuelve el mismo radicado sin duplicar. |

Obligatorios: nombre, contacto (correo o teléfono) y hechos; fecha, producto y asunto son opcionales (si no hay asunto se usa el inicio de los hechos). Qué falta lo decide el código, no el modelo. Al superar `MAX_MENSAJES_SESION` no se llama al modelo: si ya están los obligatorios se ofrece radicar con lo reunido, y si no, se pasa al formulario ya llenado.

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

### Plazos, semáforo y vencimiento (US-016 y US-017)

Al radicar se guarda `fecha_vencimiento`: el plazo se cuenta en días hábiles de Colombia (sin sábados, domingos ni festivos de la Ley Emiliani, calculados en `pipeline/dias_habiles.py`) desde el día hábil siguiente a la radicación. Al clasificar se recalcula con el plazo del tipo; si el tipo es dudoso se usa el más corto. El ciudadano ve la fecha en `/estado`.

- `PLAZO_DIAS_HABILES` (15) es el plazo general y `PLAZOS_POR_TIPO` (JSON) permite uno distinto por tipo. Verifique los términos de la Ley 1755 de 2015 antes de cambiarlos: es una simplificación para la demo, no asesoría legal.
- Semáforo: rojo con `SEMAFORO_ROJO_DIAS` (3) días hábiles o menos, o si ya venció; amarillo hasta `SEMAFORO_AMARILLO_DIAS` (7); verde con más.

### Panel del equipo (US-017, US-019, US-020 y US-022)

Abra http://localhost/admin (también hay un enlace "Panel del equipo" en el pie). Pide usuario y clave:

- **En su máquina** (`APP_ENV=desarrollo` y `ADMIN_CLAVE=cambiar-esto`): usuario `admin`, clave `coffeedevs-demo`.
- **En el servidor del evento:** ponga `APP_ENV=evento` y una `ADMIN_CLAVE` propia en el `.env` del servidor (nunca en el repositorio). Sin clave propia y fuera de `desarrollo`, el panel queda cerrado. Tras cambiar `.env`: `docker compose up -d backend`.

Qué trae el panel:

- **Resumen:** activas, en rojo o vencidas, clasificaciones por revisar, respondidas y gasto de IA.
- **Bandeja por vencimiento:** de la más urgente a la menos urgente, con semáforo, días hábiles restantes y filtros por semáforo, área, tipo, estado, riesgo de fraude y texto.
- **Calendario:** qué PQRSD vencen cada día hábil de las próximas semanas, y las ya vencidas.
- **Enviadas:** las respondidas, con quién las aprobó y cuándo.
- **Descargar base (CSV):** todas las PQRSD, sin nombre ni contacto del ciudadano.
- **Detalle de una PQRSD:** la solicitud, la clasificación (se puede confirmar o corregir; si no había borrador se manda a redactar), el borrador editable con sus avisos y las fuentes citadas con el fragmento exacto.

Reglas de la aprobación: `texto_original` nunca cambia (las ediciones van a `texto_actual`); no se puede aprobar un texto con avisos del sistema, notas internas, campos `[COMPLETAR: …]` o la firma sin llenar; al aprobar, la PQRSD pasa a `respondida`, queda quién aprobó y cuándo, y la respuesta final se guarda sin las etiquetas `[F#]`. El envío al ciudadano es simulado: cambia lo que ve en `/estado`.

Endpoints (todos piden `Authorization: Bearer <token>` salvo el acceso):

| Endpoint | Para qué |
| --- | --- |
| `POST /api/admin/login` | Devuelve el token de la sesión (12 horas por defecto) |
| `GET /api/bandeja` | Lista por urgencia con filtros |
| `GET /api/bandeja/{radicado}` | Detalle, borrador y fuentes |
| `PATCH /api/bandeja/{radicado}/clasificacion` | Confirmar o corregir tipo y área |
| `POST /api/bandeja/{radicado}/borrador/generar` | Redactar el borrador si falta |
| `PUT /api/bandeja/{radicado}/borrador` | Guardar la edición |
| `POST /api/bandeja/{radicado}/aprobar` | Aprobar y marcar como respondida |
| `POST /api/bandeja/{radicado}/chat` | Pedir un ajuste del borrador al asistente (US-021) |
| `POST /api/bandeja/{radicado}/retroalimentacion` | Guardar un aprendizaje como `.md` e indexarlo (US-023) |
| `GET /api/bandeja/exportar/csv` | Descargar la base en CSV |
| `GET /api/metricas` | Resumen, distribuciones, calendario y gasto de IA |

Pendiente de US-022: roles por área (hoy hay un solo usuario del equipo).

### Asistente de redacción del empleado (US-021)

En el detalle de una PQRSD con borrador (`/admin/pqrsd/:radicado`) está el bloque **Asistente de redacción**. La persona escribe una instrucción ("hazlo más empático", "explica el plazo") o usa una sugerencia rápida; el modelo de borrador responde y, si aplica, propone la carta completa.

- **Nada cambia sin la persona:** la propuesta solo entra al editor con **Aplicar al editor**, y se puede **Deshacer**. `texto_original` no se toca; para guardar hay que pulsar **Guardar cambios**.
- **Citas:** las etiquetas `[F#]` del borrador conservan su significado. Si la instrucción necesita otra fuente, el RAG la busca y la numera a continuación; las etiquetas sin fuente se borran. Las fuentes nuevas de una propuesta se agregan a las "Fuentes citadas" del borrador.
- **Costo:** usa `MODELO_BORRADOR` (tarea `edicion` del contador de gasto). Solo viajan el caso, el texto del editor, la instrucción y los dos últimos turnos. Cada conversación admite `MAX_MENSAJES_SESION` instrucciones (12 por defecto); la conversación vive en el navegador y se reinicia al recargar la página.
- **Prompt:** `backend/app/pipeline/prompts/chat_empleado.md`. Si se pide algo que las fuentes no respaldan, el asistente lo dice en vez de escribirlo.

### Aprendizajes del equipo en la base de conocimiento (US-023)

En el mismo detalle, antes o después de aprobar, **Guardar aprendizaje en la base de conocimiento** registra una regla o corrección para casos futuros.

- Se guarda como un `.md` en `data/conocimiento/retroalimentacion/` con este nombre: `retro_AAAAMMDD_<radicado>_<resumen-del-titulo>.md`. El nombre lo arma el sistema; lo que escribe la persona nunca llega a la ruta.
- Se indexa de inmediato en pgvector, sin tocar los demás fragmentos. La recarga completa (`cargar_conocimiento.py`) también lee esa carpeta.
- Al redactar o ajustar un borrador, el RAG reserva un lugar adicional para el aprendizaje más parecido, si supera `RAG_UMBRAL_SIMILITUD`. El chat del ciudadano no usa esa reserva, pero sí puede recuperar un aprendizaje si queda entre los más parecidos: **no escriban datos de ciudadanos en un aprendizaje**.
- Los `.md` generados no están en `.gitignore`: si un aprendizaje debe quedar para todo el equipo, súbanlo al repositorio; si era una prueba, bórrenlo y recarguen con `--eliminar-huerfanos`.

**Permisos de la carpeta.** `docker-compose.yml` monta `data/` en solo lectura y `data/conocimiento/retroalimentacion/` con escritura. En Windows y macOS funciona sin más. En Linux (el servidor del evento) el backend corre con un usuario sin privilegios y hay que permitirle escribir:

```bash
chmod a+rwx data/conocimiento/retroalimentacion
```

Si falta ese permiso, el panel responde "la carpeta de retroalimentación no admite escritura" y no guarda nada. La carpeta se puede cambiar con `RETROALIMENTACION_DIR`.

### Antes de la demo en el servidor

Lista de arranque, en orden:

1. `cp .env.example .env` y complete: `ANTHROPIC_API_KEY`, `POSTGRES_PASSWORD` (igual a la de `DB_URL`), `APP_ENV=evento` y una `ADMIN_CLAVE` propia. Sin clave propia y fuera de `desarrollo`, el panel queda cerrado.
2. `chmod a+rwx data/conocimiento/retroalimentacion` (solo Linux).
3. `docker compose up -d --build` y compruebe `curl -s localhost/api/health`: debe responder `{"estado":"ok","db":true}`.
4. Cargue la base de conocimiento. Sin ella todos los borradores salen "sin contexto":

   ```bash
   docker compose run --rm backend python /data/scripts/cargar_conocimiento.py
   ```

5. Si la base del servidor se creó antes de los últimos cambios del modelo, recréela (`docker compose down -v`, borra los datos) o agregue las columnas a mano: `create_all` no altera tablas existentes. Las historias US-021 y US-023 no cambiaron el esquema.
6. Si tras reconstruir el backend aparece un 502: `docker compose restart nginx`.
7. Siga el guion de [docs/demo.md](docs/demo.md): trae los tres casos, los textos para copiar y el plan B.

## Estructura

```
backend/                  API FastAPI (Python 3.12)
  app/main.py             app, lifespan y rutas bajo /api
  app/config.py           variables de entorno (pydantic-settings)
  app/db.py               engine, sesión e inicialización del esquema
  app/models/             tablas: pqrsd, borradores, revisiones, fragmentos_conocimiento,
                          cache_embeddings_consulta, consumos_ia, consultas_desvio
  app/api/                pqrsd y estado (ciudadano), chat y chat_radicacion, costos,
                          admin (acceso), bandeja (panel, asistente, aprendizajes), metricas
  app/pipeline/           orquestador, clasificador, svm, clasificacion_hibrida, dias_habiles,
                          rag, embeddings, conocimiento, generador, chat_empleado,
                          retroalimentacion, desvio, radicacion_chat, costos; prompts/ en .md
  tests/                  pruebas (pytest); ninguna llama a la API real
frontend/                 React + Vite, servido por nginx en su contenedor
  src/pages/              portal del ciudadano y panel del equipo (Admin*.jsx)
  src/components/         piezas compartidas, asistente de redacción y aprendizajes
  src/styles/             tokens de identidad y hojas por zona
nginx/nginx.conf          proxy: /api/ -> backend:8000, / -> frontend
data/conocimiento/        base de conocimiento ficticia; retroalimentacion/ = aprendizajes
data/scripts/             carga del conocimiento, dataset y entrenamiento del SVM
docs/                     arquitectura, backlog, identidad visual, contexto y guion de demo
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

Responsabilidades por frente. La columna **Persona** la completa el equipo.

| Frente | Qué hace | Dónde vive | Historias | Persona |
| --- | --- | --- | --- | --- |
| Plataforma | Docker, base de datos, configuración y secretos, CI | `docker-compose.yml`, `nginx/`, `backend/app/{config,db}.py`, `backend/app/models/`, `.github/workflows/` | US-001 a US-003 | |
| Conocimiento y datos | Empresa ficticia, normativa, carga con embeddings, dataset y SVM | `data/conocimiento/`, `data/scripts/`, `backend/app/pipeline/{conocimiento,embeddings,svm}.py` | US-004 a US-006, US-025 | |
| Portal del ciudadano | Formulario, chat de radicación, chat de desvío y consulta de estado | `backend/app/api/{pqrsd,estado,chat,chat_radicacion}.py`, `backend/app/pipeline/{desvio,radicacion_chat}.py`, `frontend/src/pages/` | US-007 a US-010 | |
| Pipeline de IA | Clasificación híbrida, RAG, borrador con citas y control de costos | `backend/app/pipeline/{orquestador,clasificador,clasificacion_hibrida,rag,generador,costos}.py`, `prompts/` | US-011 a US-015 | |
| Plazos | Días hábiles de Colombia, vencimiento y semáforo | `backend/app/pipeline/dias_habiles.py` | US-016, US-017 | |
| Panel del equipo | Acceso, bandeja, calendario, editor, aprobación, CSV y métricas | `backend/app/api/{admin,bandeja,metricas}.py`, `frontend/src/pages/Admin*.jsx` | US-019, US-020, US-022, US-024 | |
| Asistente y aprendizaje | Chat para ajustar el borrador y aprendizajes en `.md` | `backend/app/pipeline/{chat_empleado,retroalimentacion}.py`, `frontend/src/components/{AsistenteBorrador,Aprendizaje}.jsx` | US-021, US-023 | |
| Experiencia y demo | Identidad visual, textos en lenguaje claro, guion y ensayo | `docs/identidad-visual.md`, `frontend/src/styles/`, `docs/demo.md` | US-026, US-027 | |

Pendiente del backlog: alertas escalonadas (US-018), roles por área (resto de US-022) y los extras de US-028.

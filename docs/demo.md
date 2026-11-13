# Guion de la demo — PQRSD Coffee Devs

Guion para la presentación final (unos 5 minutos). Tres casos muestran el flujo completo: una duda que se resuelve sin radicar, un reclamo que recorre todo el camino hasta la respuesta aprobada, y un caso urgente con riesgo de fraude. Todos los datos son ficticios.

> **Ensayo pendiente.** Este guion se escribió con el sistema probado por partes (pruebas automáticas, panel en el navegador y aprendizajes con la base real), pero **no se ensayó completo con la IA real**. Las respuestas de Claude cambian de una corrida a otra: hagan al menos un ensayo de punta a punta en el servidor, ajusten los textos de abajo si hace falta y graben el respaldo (ver "Plan B").

## Mensaje central (15 segundos)

"Una PQRSD respondida tarde o mal clasificada es una multa. Nuestra plataforma la recibe, la clasifica, calcula su plazo legal, redacta un borrador con citas de la normativa y avisa antes de que venza. La IA propone; una persona decide. Nada llega al ciudadano sin aprobación."

## Antes de empezar

### La noche anterior (o una hora antes)

1. En el servidor: `APP_ENV=evento` y `ADMIN_CLAVE` propia en `.env`; `docker compose up -d --build`.
2. Cargar la base de conocimiento: `docker compose run --rm backend python /data/scripts/cargar_conocimiento.py`. Debe terminar con 9 documentos.
3. Permisos de la carpeta de aprendizajes (solo Linux): `chmod a+rwx data/conocimiento/retroalimentacion`.
4. **Precargar el caso 3:** radíquelo con el formulario (texto en el caso 3) y espere a que tenga borrador. Luego acerque su vencimiento para que salga en rojo, cambiando `RADICADO` por el suyo:

   ```bash
   docker compose exec db psql -U pqrsd -d pqrsd -c "update pqrsd set fecha_vencimiento = current_date + 1 where radicado = 'RADICADO'"
   ```

5. Opcional, para cerrar el caso 2 sin esperas: precargue también un segundo reclamo por cobro doble **después** de guardar el aprendizaje en un ensayo (ver el paso 2.8).
6. Revise el gasto: abra el panel y mire la tarjeta "Gasto de IA". Reserve unos 10 USD para la presentación.

### Cinco minutos antes

- Pestaña 1: `http://SERVIDOR/` (portal del ciudadano).
- Pestaña 2: `http://SERVIDOR/admin` con la sesión ya iniciada.
- Este archivo abierto para copiar los textos.
- Compruebe `http://SERVIDOR/api/health`: debe decir `"db": true`.

## Caso 1 — Una duda que no necesita radicarse (45 segundos)

**Qué demuestra:** el asistente responde con la base de conocimiento y cita su fuente; lo que no sabe, no lo inventa. Cada duda resuelta aquí es una PQRSD menos para el equipo.

1. En el portal, entre a **Resolver una duda** (`/chat`).
2. Pegue esta pregunta:

   ```text
   ¿Por qué me cobran cuota de manejo si no he usado la tarjeta este mes?
   ```

3. Muestre la respuesta y sus fuentes (preguntas frecuentes y contrato). **Diga:** "Responde solo con documentos del banco y los cita. No radicamos nada."
4. Pegue una pregunta que la base no cubre:

   ```text
   ¿Cuál es la tasa de interés de un crédito hipotecario a 15 años?
   ```

5. **Diga:** "Aquí no tiene respaldo, así que lo dice y ofrece radicar. Prefiere no responder a inventar."

## Caso 2 — Un reclamo de punta a punta (2 minutos y medio)

**Qué demuestra:** radicación, plazo en días hábiles, clasificación híbrida, borrador con citas, ajuste conversando, aprendizaje del equipo y aprobación humana.

### 2.1 Radicar

En el portal, **Radicar una PQRSD** → **Llenar el formulario** (o **Hágalo con el asistente** si quieren mostrar el chat que extrae los datos). Pegue:

| Campo | Texto |
| --- | --- |
| Nombre | `Laura Gómez Ficticia` |
| Contacto | `laura.gomez@ejemplo.test` |
| Asunto | `Cobro doble de la cuota de manejo` |
| Descripción | `En el extracto de noviembre me cobraron dos veces la cuota de manejo de mi Tarjeta de Crédito Andina Clásica, 18.000 pesos cada vez. No hice compras este mes. Solicito que revisen el cobro duplicado y me devuelvan el valor cobrado de más.` |

**Muestre** el radicado y la fecha de vencimiento. **Diga:** "El plazo ya corre: 15 días hábiles, sin fines de semana ni festivos de Colombia. Y el radicado no es consecutivo, no se puede adivinar."

### 2.2 La bandeja

Pase a la pestaña del panel y recargue. La PQRSD aparece en verde, como **Reclamo** de **Tarjetas de Crédito**. El borrador tarda entre 20 y 40 segundos; mientras tanto, **diga:** "Claude decidió el tipo, porque el tipo define el plazo legal. Un modelo SVM entrenado por nosotros resolvió el área, el tema, el sentimiento y el riesgo de fraude sin gastar API, y además verifica a Claude: si no coinciden, el caso va a revisión humana."

### 2.3 El borrador y sus fuentes

Abra la PQRSD. **Muestre:**

- La clasificación completa a la izquierda.
- El borrador a la derecha, con etiquetas `[F1]`, `[F2]`.
- **Fuentes citadas:** abra una para ver el fragmento exacto del contrato.
- El aviso "Para poder aprobar": hay campos `[COMPLETAR: …]` y la firma sin llenar.

**Diga:** "Cada afirmación tiene su fuente. Y miren esto: la IA no afirmó que el cobro estuviera duplicado, porque eso no lo sabe. Lo dejó para que lo verifique una persona."

### 2.4 Ajustar conversando

En **Asistente de redacción**, pulse **Hacer más empático**. Cuando responda, abra "Ver la carta propuesta" y pulse **Aplicar al editor**. Si quiere mostrar una instrucción propia, pegue:

```text
Explica en una frase que estamos verificando el cobro en el extracto y que le informaremos el resultado dentro del plazo legal.
```

**Diga:** "No reescribo la carta: le pido el cambio. La propuesta solo entra al editor cuando yo la aplico, puedo deshacerla, y el texto original de la IA se conserva siempre."

### 2.5 Completar y firmar

En el editor, reemplace el campo `[COMPLETAR: …]` y la firma. Textos para pegar:

```text
Verificamos su extracto de noviembre y confirmamos que la cuota de manejo se cobró dos veces. Reversamos el cobro duplicado; lo verá reflejado en su próximo extracto.
```

```text
Ana Ficticia
Analista — Tarjetas de Crédito
Banco Andino Ficticio
```

Pulse **Guardar cambios**. El aviso "Para poder aprobar" desaparece.

### 2.6 Guardar el aprendizaje

Pulse **Guardar aprendizaje en la base de conocimiento** y pegue:

| Campo | Texto |
| --- | --- |
| Título | `Cobro duplicado de la cuota de manejo` |
| Área | Tarjetas de Crédito (ya viene elegida) |
| Regla o criterio | `Cuando un cliente reclama que la cuota de manejo se cobró dos veces en el mismo mes, el analista verifica el extracto. Si el cobro está duplicado, se reversa el valor cobrado de más y se informa al cliente en la respuesta, indicando el mes del extracto revisado. Si no está duplicado, se le explica el cobro con la cláusula de cuota de manejo del contrato.` |

**Muestre** el aviso verde con el nombre del archivo `.md`. **Diga:** "Nuestra base no tenía una regla para cobros duplicados. Ahora la tiene: quedó como un documento más y ya está indexada. El próximo borrador de un caso parecido la va a citar."

### 2.7 Aprobar

Pulse **Aprobar y enviar respuesta** y confirme. La PQRSD pasa a **Respondida** y queda quién aprobó y cuándo. Vuelva al portal, **Consultar estado**, pegue el radicado: el ciudadano la ve respondida.

**Diga:** "Las etiquetas de fuente se retiraron solas del texto final. Y el sistema no me dejaba aprobar mientras quedaran notas internas o campos por completar."

### 2.8 Cierre del ciclo (opcional, 30 segundos)

Abra el segundo reclamo por cobro doble que precargó después de guardar el aprendizaje. En **Fuentes citadas** aparece un documento que empieza por "Retro…": es el aprendizaje del equipo. **Diga:** "El sistema aprendió de la corrección de una persona, no de un reentrenamiento."

Texto para precargarlo (con el mismo formulario):

| Campo | Texto |
| --- | --- |
| Nombre | `Carlos Ruiz Ficticio` |
| Contacto | `carlos.ruiz@ejemplo.test` |
| Asunto | `Me cobraron dos veces la cuota de manejo` |
| Descripción | `Revisé mi extracto y la cuota de manejo de la tarjeta aparece cobrada dos veces este mes. Pido que corrijan el cobro duplicado.` |

## Caso 3 — Urgente y con riesgo de fraude (1 minuto)

**Qué demuestra:** el semáforo pone primero lo que está por vencer, el sistema marca el riesgo de fraude y la IA es prudente: avisa en vez de resolver sola.

Este caso se precarga (ver "La noche anterior"). Texto para radicarlo:

| Campo | Texto |
| --- | --- |
| Nombre | `Marta Díaz Ficticia` |
| Contacto | `marta.diaz@ejemplo.test` |
| Asunto | `Compra que no reconozco en mi tarjeta` |
| Descripción | `Hoy apareció en mi tarjeta de crédito una compra por internet de 1.250.000 pesos que yo no hice. No he perdido la tarjeta ni compartí mis datos. Creo que la clonaron. Solicito que bloqueen la tarjeta y reversen el cargo.` |

En la presentación:

1. En el panel, la **Bandeja** la muestra de primera, en **rojo** y con la etiqueta **Riesgo de fraude**. La tarjeta "En rojo o vencidas" la cuenta. **Diga:** "El semáforo no es solo color: tiene forma y texto, y ordena la bandeja por urgencia."
2. Pase a **Calendario**: muestre qué vence cada día hábil.
3. Abra la PQRSD. **Muestre** "Riesgo de fraude: Sí, verificar antes de responder" y la nota interna o el aviso al inicio del borrador. **Diga:** "En un caso de fraude la IA no promete reversar el cargo ni revela reglas internas. Le dice al analista qué debe verificar, y no se puede aprobar hasta que una persona retire esa nota."
4. Pulse **Descargar base (CSV)**. **Diga:** "Toda la gestión se exporta, sin datos de contacto del ciudadano."

### Variante: clasificación en revisión

Si alguna PQRSD quedó con la etiqueta **Revisar clasificación**, ábrala: muestra por qué (baja confianza o tipos distintos entre Claude y el SVM). Elija tipo y área y pulse **Confirmar y generar borrador**: el plazo se recalcula y el borrador se redacta en segundo plano.

## Cierre (20 segundos)

"En cinco minutos vieron una duda resuelta sin radicar, un reclamo respondido con citas y aprobado por una persona, y un caso urgente priorizado. Todo corre con un `docker compose up`, con el gasto de IA medido en pantalla y un tope que bloquea las llamadas antes de pasarnos del presupuesto."

Cifras para mencionar (verifíquelas antes de decirlas): el gasto de IA que muestra el panel, las pruebas automáticas del backend que pasan en la CI y la precisión del clasificador medida con el golden set (`backend/app/pipeline/modelos_svm/metricas.md`).

## Tiempos

| Parte | Duración |
| --- | --- |
| Mensaje central | 0:15 |
| Caso 1 — duda sin radicar | 0:45 |
| Caso 2 — reclamo de punta a punta | 2:30 |
| Caso 3 — urgente con riesgo de fraude | 1:00 |
| Cierre | 0:20 |
| **Total** | **4:50** |

Si el tiempo aprieta, omita el paso 2.8 y la variante del caso 3.

## Plan B

| Si pasa esto | Haga esto |
| --- | --- |
| El borrador del caso 2 tarda o no llega | Abra un caso precargado que ya tenga borrador y siga desde el paso 2.3. En el detalle, **Generar borrador** lo reintenta. |
| La API de Claude no responde o se agotó el presupuesto | La radicación, el plazo, la bandeja, el semáforo, el calendario, la edición a mano, la aprobación y el CSV funcionan sin IA. Muestre los casos precargados. |
| El asistente de redacción falla | Edite el borrador a mano en el editor: el flujo de aprobación no depende del asistente. |
| "No se pudo guardar el aprendizaje… no admite escritura" | Falta el permiso de la carpeta en el servidor: `chmod a+rwx data/conocimiento/retroalimentacion`. |
| Todos los borradores dicen "sin contexto suficiente" | No se cargó la base de conocimiento: corra `cargar_conocimiento.py` (paso 2 de la preparación). |
| El panel responde 502 después de reconstruir | `docker compose restart nginx`. |
| No hay red o se cae el servidor | Use la grabación de respaldo del flujo completo. Grábela en el ensayo. |

# **Product Backlog — Gestión inteligente de PQRSD · Coffee Devs**

Nov 11, 2026 · @VALENTINA

## **1\. Visión del producto y objetivos estratégicos**

**Visión.** Una plataforma web que recibe una PQRSD por chat o formulario, la clasifica, la asigna al área correcta, redacta un borrador con citas de la normativa y avisa antes de que venza el plazo legal. Un empleado revisa y aprueba cada respuesta, de modo que la IA propone y la persona decide. Está pensada para ciudadanos o clientes que radican solicitudes y para los empleados de atención, jurídica y cartera de una organización sujeta a términos legales (alcaldías, bancos, aseguradoras); la demo usa una empresa ficticia.

**Objetivo estratégico.** Eliminar el riesgo sancionatorio por respuestas tardías o mal clasificadas y descargar al equipo de atención.

### **KPIs sugeridos (metas ajustables)**

| KPI | Meta sugerida | Cómo se mide |
| ----- | ----- | ----- |
| Precisión del clasificador (tipo y área) | 85 % o más | Aciertos sobre el set de prueba de unos 50 casos |
| Tiempo de radicación a borrador listo | Menos de 60 segundos | Medido en la demo |
| Borradores con al menos una cita de la base de conocimiento | 100 % | Revisión de los casos de prueba |
| Respuestas enviadas sin aprobación humana | 0 | Registro de revisiones |
| Casos con semáforo rojo visibles al inicio de la bandeja | 100 % | Prueba con el caso de plazo crítico |
| Gasto en la API de Claude | 40 USD o menos en todo el evento | Contador de gasto por endpoint |

## **2\. Definición de Hecho (DoD)**

Una historia se considera terminada solo si cumple los seis criterios:

1. El código está en el repositorio del equipo, integrado por pull request revisado por otra persona, y no contiene secretos (`.env`, `*.pem`, API keys).  
2. Funciona con `docker compose up` en el servidor del evento, no solo en la máquina de quien lo desarrolló.  
3. Cada criterio de aceptación se probó manualmente con datos ficticios y el resultado quedó anotado en el pull request.  
4. Toda salida de IA que llega al ciudadano pasa por aprobación humana y muestra las fuentes que usó.  
5. Los prompts viven en archivos `.md` versionados y toda variable nueva está en `.env.example`.  
6. Si la historia cambia la arquitectura o la forma de correr el proyecto, se actualizó el `README` o `docs/`.

## **3\. Matriz del Product Backlog**

Son 28 historias en 8 épicas, ordenadas en el orden de construcción propuesto. Los puntos usan la escala 1, 2, 3, 5, 8, 13\.

| ID | Épica | Historia de usuario (título) | Prioridad (MoSCoW) | Story points |
| ----- | ----- | ----- | ----- | ----- |
| US-001 | 1\. Plataforma base | Entorno Docker y repositorio | Must Have | 3 |
| US-002 | 1\. Plataforma base | Modelo de datos en PostgreSQL con pgvector | Must Have | 3 |
| US-003 | 1\. Plataforma base | Gestión segura de credenciales | Must Have | 2 |
| US-004 | 2\. Conocimiento y datos | Empresa ficticia y normativa para el RAG | Must Have | 5 |
| US-005 | 2\. Conocimiento y datos | Carga de conocimiento y embeddings | Must Have | 3 |
| US-006 | 2\. Conocimiento y datos | Casos de prueba y 3 casos de demo | Must Have | 3 |
| US-007 | 3\. Radicación y chat | Radicar una PQRSD con formulario | Must Have | 3 |
| US-008 | 3\. Radicación y chat | Chat de radicación con extracción de campos | Should Have | 8 |
| US-009 | 3\. Radicación y chat | Desvío de consultas resueltas por la base de conocimiento | Should Have | 5 |
| US-010 | 3\. Radicación y chat | Consultar el estado de una PQRSD | Must Have | 2 |
| US-011 | 4\. Pipeline de IA | Clasificación de tipo, área y confianza | Must Have | 5 |
| US-012 | 4\. Pipeline de IA | Recuperación RAG de normativa y políticas | Must Have | 5 |
| US-013 | 4\. Pipeline de IA | Borrador de respuesta con citas | Must Have | 8 |
| US-014 | 4\. Pipeline de IA | Enrutamiento según confianza | Should Have | 3 |
| US-015 | 4\. Pipeline de IA | Control de costos de IA | Must Have | 3 |
| US-016 | 5\. Plazos y alertas | Cálculo del vencimiento en días hábiles | Must Have | 5 |
| US-017 | 5\. Plazos y alertas | Semáforo de vencimiento | Must Have | 2 |
| US-018 | 5\. Plazos y alertas | Alertas escalonadas | Should Have | 5 |
| US-019 | 6\. Bandeja del empleado | Bandeja priorizada por vencimiento y área | Must Have | 5 |
| US-020 | 6\. Bandeja del empleado | Editor de borrador con aprobación | Must Have | 5 |
| US-021 | 6\. Bandeja del empleado | Edición del borrador por chat | Should Have | 5 |
| US-022 | 6\. Bandeja del empleado | Acceso por roles | Should Have | 3 |
| US-023 | 7\. Aprendizaje y métricas | Aprendizaje con las ediciones del empleado | Should Have | 5 |
| US-024 | 7\. Aprendizaje y métricas | Dashboard de métricas | Should Have | 5 |
| US-025 | 7\. Aprendizaje y métricas | Evaluación de precisión del clasificador | Should Have | 3 |
| US-026 | 8\. Demo y entrega | Guion y ensayo de la demo | Must Have | 3 |
| US-027 | 8\. Demo y entrega | Documentación y entrega del código | Must Have | 2 |
| US-028 | 8\. Demo y entrega | Extras: notificaciones por correo, avatar con video o voz | Could Have | 8 |

## 

## **4\. Detalle completo de épicas e historias**

### **Épica 1: Plataforma base**

*Deja listo el servidor, el repositorio y la base de datos para que el resto del equipo trabaje en paralelo. Valor: sin esto no hay demo ni entrega.*

#### **Historia de Usuario: US-001 \- Entorno Docker y repositorio**

* **Enunciado:** Como desarrollador del equipo, quiero levantar todos los servicios con un solo comando, para que cualquier integrante pueda probar su trabajo en el servidor del evento.  
* **Prioridad:** Must Have  
* **Story Points:** 3  
* **Criterios de Aceptación:**  
  1. Dado que el repositorio está clonado en el servidor, cuando ejecuto `docker compose up`, entonces arrancan base de datos, backend, frontend y nginx sin errores.  
  2. Dado que nginx está activo, cuando abro el puerto 80, entonces `/` muestra el frontend y `/api` responde desde el backend.  
  3. Dado que el repositorio existe, cuando reviso el `.gitignore`, entonces excluye `.env`, `*.pem`, `node_modules`, `__pycache__` y datos.  
* **Notas Técnicas / Riesgos:** Solo están abiertos los puertos 22, 80 y 443\. El servidor se elimina al cierre, por lo que se sube código al repositorio todos los días.

#### **Historia de Usuario: US-002 \- Modelo de datos en PostgreSQL con pgvector**

* **Enunciado:** Como desarrollador del backend, quiero un modelo de datos con tablas para PQRSD, borradores, revisiones y fragmentos de conocimiento, para que el pipeline y la bandeja guarden y consulten información de forma consistente.  
* **Prioridad:** Must Have  
* **Story Points:** 3  
* **Criterios de Aceptación:**  
  1. Dado que la base está vacía, cuando arranca el backend, entonces crea las tablas `pqrsd`, `borradores`, `revisiones` y la de fragmentos con columna vectorial.  
  2. Dado que se radica una PQRSD, cuando se guarda, entonces queda con radicado único, fecha de radicación, estado, tipo, área y confianza.  
  3. Dado que existe un borrador, cuando se edita, entonces se conserva el texto original y se registra la versión final en `revisiones`.  
* **Notas Técnicas / Riesgos:** Definir el esquema el primer día; cambiarlo tarde rompe a todos. La tabla de ediciones de US-023 se agrega sobre este modelo.

#### **Historia de Usuario: US-003 \- Gestión segura de credenciales**

* **Enunciado:** Como líder técnico, quiero que las claves y credenciales vivan solo en variables de entorno, para que ninguna API key ni llave `.pem` termine en el repositorio.  
* **Prioridad:** Must Have  
* **Story Points:** 2  
* **Criterios de Aceptación:**  
  1. Dado que existe `.env.example`, cuando lo reviso, entonces lista `ANTHROPIC_API_KEY`, `DB_URL` y las demás variables sin valores reales.  
  2. Dado que `config.py` lee las variables, cuando falta una obligatoria, entonces el backend falla al arrancar con un mensaje claro.  
  3. Dado que se hace un commit, cuando se revisa el historial, entonces no aparecen claves ni archivos `.pem`.  
* **Notas Técnicas / Riesgos:** Si una clave se sube por error, se revoca de inmediato y se genera otra; borrar el commit no basta.

### **Épica 2: Base de conocimiento y datos de demo**

*Define la empresa ficticia, su normativa y los casos con los que se alimenta, prueba y demuestra el sistema. Valor: sin contenido en español y coherente, el RAG y la demo no convencen.*

#### **Historia de Usuario: US-004 \- Empresa ficticia y normativa para el RAG**

* **Enunciado:** Como equipo de producto, quiero una empresa ficticia con áreas, políticas y normativa resumida, para que el sistema responda con contexto realista y sin datos reales.  
* **Prioridad:** Must Have  
* **Story Points:** 5  
* **Criterios de Aceptación:**  
  1. Dado que se eligió una empresa (banco, aseguradora o similar), cuando reviso `data/conocimiento/`, entonces hay documentos de políticas, contratos y preguntas frecuentes en español.  
  2. Dado que la normativa se resume, cuando se cita la Ley 1755 de 2015, entonces los plazos coinciden con el texto verificado de la ley y quedan como configuración.  
  3. Dado que el contenido es ficticio, cuando se revisa, entonces no hay nombres, documentos ni datos de clientes reales.  
* **Notas Técnicas / Riesgos:** Elegir una sola empresa el miércoles. Si la normativa se redacta de memoria puede tener errores; verificar antes de citar.

#### **Historia de Usuario: US-005 \- Carga de conocimiento y embeddings**

* **Enunciado:** Como desarrollador del backend, quiero un script que divida los documentos y guarde sus embeddings, para que el RAG recupere fragmentos relevantes.  
* **Prioridad:** Must Have  
* **Story Points:** 3  
* **Criterios de Aceptación:**  
  1. Dado que existen documentos en `data/conocimiento/`, cuando ejecuto `cargar_conocimiento.py`, entonces se guardan fragmentos con su vector y su documento de origen.  
  2. Dado que el script ya corrió, cuando se ejecuta de nuevo, entonces no duplica fragmentos.  
  3. Dado que el script termina, cuando se consulta la tabla, entonces cada fragmento conserva el nombre del documento y la sección para poder citarlo.  
* **Notas Técnicas / Riesgos:** Los embeddings consumen presupuesto de API; cargarlos una vez y guardarlos. Dependencia: US-002.

#### **Historia de Usuario: US-006 \- Casos de prueba y 3 casos de demo**

* **Enunciado:** Como equipo de producto, quiero un set de PQRSD sintéticas etiquetadas y 3 casos de demo ensayados, para que evaluemos el clasificador y presentemos sin improvisar.  
* **Prioridad:** Must Have  
* **Story Points:** 3  
* **Criterios de Aceptación:**  
  1. Dado que se generan los casos, cuando reviso `data/ejemplos/`, entonces hay unas 50 PQRSD en español con tipo y área esperados.  
  2. Dado que se definen los casos de demo, cuando los reviso, entonces cubren un caso feliz, uno de plazo crítico y uno de baja confianza o edición.  
  3. Dado que el set se usa para evaluar, cuando se compara con los ejemplos del prompt del clasificador, entonces no hay casos repetidos entre ambos.  
* **Notas Técnicas / Riesgos:** Se pueden generar con Claude y revisarse a mano. Dependencia: US-004. El dataset CFPB sirve solo como inspiración de categorías.

### **Épica 3: Radicación y agente de chat**

*Es la puerta de entrada del ciudadano: primero un formulario que garantiza el flujo mínimo, luego un chat que lo guía y evita radicaciones innecesarias. Valor: más PQRSD completas y menos carga para el equipo.*

#### **Historia de Usuario: US-007 \- Radicar una PQRSD con formulario**

* **Enunciado:** Como ciudadano, quiero radicar mi solicitud con un formulario simple, para que quede registrada y reciba un número de radicado.  
* **Prioridad:** Must Have  
* **Story Points:** 3  
* **Criterios de Aceptación:**  
  1. Dado que estoy en la página de radicación, cuando completo nombre ficticio, contacto y descripción y envío, entonces se crea la PQRSD y veo una confirmación con mi radicado.  
  2. Dado que dejo vacío un campo obligatorio, cuando envío, entonces veo un mensaje claro y no se guarda nada.  
  3. Dado que se radicó la PQRSD, cuando reviso la base de datos, entonces queda con fecha de radicación y estado "recibida" y dispara el pipeline de IA.  
* **Notas Técnicas / Riesgos:** Es la base del flujo mínimo; el chat de US-008 reutiliza el mismo endpoint. Validar longitud del texto para controlar el costo de IA.

#### **Historia de Usuario: US-008 \- Chat de radicación con extracción de campos**

* **Enunciado:** Como ciudadano, quiero contarle mi situación a un agente en un chat, para que él arme mi PQRSD sin que yo tenga que conocer el formato.  
* **Prioridad:** Should Have  
* **Story Points:** 8  
* **Criterios de Aceptación:**  
  1. Dado que describo mi caso en lenguaje natural, cuando el agente responde, entonces extrae los campos de la PQRSD (hechos, fechas, producto o servicio, contacto).  
  2. Dado que falta información necesaria, cuando el agente lo detecta, entonces me la pide antes de radicar.  
  3. Dado que confirmo el resumen, cuando acepto radicar, entonces se crea la PQRSD con el mismo flujo del formulario y recibo mi radicado.  
  4. Dado que la conversación supera el tope de mensajes por sesión, cuando envío otro mensaje, entonces el agente me ofrece radicar con lo que hay o pasar al formulario.  
* **Notas Técnicas / Riesgos:** Usar modelo liviano y `max_tokens` bajo. Dependencias: US-007, US-012, US-015. Es la historia más grande de la épica; si el tiempo aprieta, el formulario cubre el flujo.

#### **Historia de Usuario: US-009 \- Desvío de consultas resueltas por la base de conocimiento**

* **Enunciado:** Como ciudadano, quiero que el agente me responda directamente cuando mi duda ya tiene respuesta, para que no tenga que radicar una PQRSD ni esperar.  
* **Prioridad:** Should Have  
* **Story Points:** 5  
* **Criterios de Aceptación:**  
  1. Dado que hago una pregunta cubierta por la base de conocimiento, cuando el agente la responde, entonces la respuesta cita el documento de origen.  
  2. Dado que la respuesta no me resuelve, cuando pido continuar, entonces el agente me ofrece radicar la PQRSD con el contexto de la conversación.  
  3. Dado que la base de conocimiento no tiene información suficiente, cuando consulto, entonces el agente lo dice y no inventa datos ni normas.  
* **Notas Técnicas / Riesgos:** Riesgo de respuestas inventadas: el agente solo responde con fragmentos recuperados. Dependencias: US-005, US-012. Se puede medir como argumento de negocio: consultas resueltas sin radicar.

#### **Historia de Usuario: US-010 \- Consultar el estado de una PQRSD**

* **Enunciado:** Como ciudadano, quiero consultar el estado de mi PQRSD con mi número de radicado, para que sepa si fue recibida, está en trámite o respondida.  
* **Prioridad:** Must Have  
* **Story Points:** 2  
* **Criterios de Aceptación:**  
  1. Dado que tengo un radicado válido, cuando lo ingreso en la página de estado, entonces veo el estado actual y la fecha de vencimiento.  
  2. Dado que ingreso un radicado inexistente, cuando consulto, entonces veo un mensaje que no revela información de otras solicitudes.  
  3. Dado que el empleado aprobó la respuesta, cuando consulto, entonces el estado cambia a "respondida".  
* **Notas Técnicas / Riesgos:** No exponer borradores ni datos internos al ciudadano. Considerar radicados no consecutivos para evitar adivinarlos.

### **Épica 4: Pipeline de IA**

*Es el corazón del producto: clasifica, recupera normativa, redacta el borrador y decide cuándo interviene una persona, todo dentro del presupuesto de 40 USD. Valor: respuestas rápidas, trazables y sin datos inventados.*

#### **Historia de Usuario: US-011 \- Clasificación de tipo, área y confianza**

* **Enunciado:** Como coordinador de atención, quiero que cada PQRSD se clasifique automáticamente por tipo y área con un nivel de confianza, para que llegue al equipo correcto sin triaje manual.  
* **Prioridad:** Must Have  
* **Story Points:** 5  
* **Criterios de Aceptación:**  
  1. Dado que entra una PQRSD, cuando corre el clasificador, entonces devuelve tipo (petición, queja, reclamo, sugerencia o denuncia), área y confianza entre 0 y 1\.  
  2. Dado que la respuesta del modelo no es un JSON válido, cuando se procesa, entonces el sistema reintenta una vez y, si falla, deja el caso en revisión humana.  
  3. Dado que se usan ejemplos en el prompt, cuando cambian, entonces el prompt vive en `pipeline/prompts/` como archivo `.md` y no dentro del código.  
* **Notas Técnicas / Riesgos:** Modelo liviano, salida corta y caché del prompt con los ejemplos fijos. Dependencias: US-002, US-004.

#### **Historia de Usuario: US-012 \- Recuperación RAG de normativa y políticas**

* **Enunciado:** Como agente de IA del sistema, quiero recuperar los fragmentos más relevantes de la base de conocimiento, para que mis respuestas se apoyen en normativa y políticas reales de la empresa ficticia.  
* **Prioridad:** Must Have  
* **Story Points:** 5  
* **Criterios de Aceptación:**  
  1. Dado que tengo una PQRSD clasificada, cuando se consulta pgvector, entonces se devuelven los fragmentos más cercanos con su documento de origen.  
  2. Dado que ningún fragmento supera el umbral de similitud, cuando se consulta, entonces el sistema marca "sin contexto suficiente" y no pasa fragmentos irrelevantes al generador.  
  3. Dado que la consulta se repite con el mismo texto, cuando se ejecuta, entonces se reutiliza el resultado guardado y no se vuelve a llamar a la API.  
* **Notas Técnicas / Riesgos:** El umbral se calibra con los casos de prueba. Dependencias: US-005, US-011.

#### **Historia de Usuario: US-013 \- Borrador de respuesta con citas**

* **Enunciado:** Como empleado del área, quiero un borrador de respuesta ya redactado con sus fuentes, para que solo tenga que revisarlo y no empezar de cero.  
* **Prioridad:** Must Have  
* **Story Points:** 8  
* **Criterios de Aceptación:**  
  1. Dado que hay fragmentos recuperados, cuando se genera el borrador, entonces cada afirmación normativa o de política cita el fragmento de origen.  
  2. Dado que no hay contexto suficiente, cuando se genera, entonces el borrador lo indica y propone derivar el caso a una persona, sin inventar normas ni datos.  
  3. Dado que el borrador se guarda, cuando se abre en la bandeja, entonces queda asociado a la PQRSD con su tipo, área y fecha de vencimiento.  
  4. Dado que se genera con el modelo más capaz, cuando se registra la llamada, entonces queda el consumo de tokens para el contador de gasto.  
* **Notas Técnicas / Riesgos:** Solo se llama con el caso ya clasificado y con `max_tokens` acotado. Riesgo: alucinaciones; la validación humana es obligatoria. Dependencias: US-011, US-012, US-015.

#### **Historia de Usuario: US-014 \- Enrutamiento según confianza**

* **Enunciado:** Como coordinador de atención, quiero que los casos con baja confianza pasen primero por una persona, para que un error de clasificación no mande una PQRSD al área equivocada.  
* **Prioridad:** Should Have  
* **Story Points:** 3  
* **Criterios de Aceptación:**  
  1. Dado que la confianza es igual o mayor al umbral configurado, cuando termina la clasificación, entonces la PQRSD se asigna directamente al área.  
  2. Dado que la confianza es menor al umbral, cuando termina la clasificación, entonces queda en una cola de revisión de clasificación.  
  3. Dado que una persona corrige el área, cuando confirma, entonces la PQRSD se asigna a la nueva área y el cambio queda registrado.  
* **Notas Técnicas / Riesgos:** El umbral es configurable y se ajusta con los resultados de US-025. Dependencia: US-011.

#### **Historia de Usuario: US-015 \- Control de costos de IA**

* **Enunciado:** Como líder técnico, quiero limitar y medir el gasto en la API de Claude, para que los 40 USD alcancen hasta el final del evento.  
* **Prioridad:** Must Have  
* **Story Points:** 3  
* **Criterios de Aceptación:**  
  1. Dado que cada tarea tiene un modelo asignado, cuando se llama a la API, entonces el chat y la clasificación usan el modelo liviano y solo el borrador final usa el más capaz.  
  2. Dado que se define un tope de mensajes por sesión y de `max_tokens` por llamada, cuando se superan, entonces el sistema corta la llamada y responde con un mensaje claro.  
  3. Dado que se hacen llamadas, cuando consulto el contador, entonces veo el gasto estimado acumulado por endpoint.  
  4. Dado que el gasto estimado llega a 30 USD, cuando se hace otra llamada, entonces el sistema avisa al equipo.  
* **Notas Técnicas / Riesgos:** Reservar unos 10 USD para el ensayo y el día de la entrega. El umbral de aviso de 30 USD es una sugerencia ajustable.

### **Épica 5: Motor de plazos y alertas**

*Convierte el reloj legal en algo visible y accionable. Valor: es lo más cercano al dolor del reto, porque una respuesta tardía es una multa.*

#### **Historia de Usuario: US-016 \- Cálculo del vencimiento en días hábiles**

* **Enunciado:** Como coordinador de atención, quiero que cada PQRSD tenga una fecha de vencimiento calculada según su tipo, para que nadie tenga que contar días a mano.  
* **Prioridad:** Must Have  
* **Story Points:** 5  
* **Criterios de Aceptación:**  
  1. Dado que se radica una PQRSD, cuando se calcula el plazo, entonces se cuentan solo días hábiles y se excluyen sábados, domingos y festivos de Colombia.  
  2. Dado que el tipo de solicitud cambia el término legal, cuando se clasifica, entonces el vencimiento se recalcula con el plazo de ese tipo.  
  3. Dado que los plazos están en un archivo de configuración, cuando se modifican, entonces el cálculo cambia sin tocar el código.  
  4. Dado que una PQRSD se radica un viernes festivo o un fin de semana, cuando se calcula, entonces el conteo empieza el siguiente día hábil.  
* **Notas Técnicas / Riesgos:** Verificar en la Ley 1755 de 2015 los plazos por tipo antes de configurarlos; el reto menciona 15 días hábiles. Mantener la lista de festivos para 2026 y 2027 y confirmar cómo cuenta la entidad el día de radicación. Dependencias: US-002, US-007.

#### **Historia de Usuario: US-017 \- Semáforo de vencimiento**

* **Enunciado:** Como empleado del área, quiero ver un semáforo de color en cada PQRSD, para que identifique de un vistazo cuáles son urgentes.  
* **Prioridad:** Must Have  
* **Story Points:** 2  
* **Criterios de Aceptación:**  
  1. Dado que a una PQRSD le queda más del 50 % del plazo, cuando se muestra, entonces el semáforo es verde.  
  2. Dado que le queda entre el 20 % y el 50 %, cuando se muestra, entonces es amarillo.  
  3. Dado que le queda menos del 20 % o está vencida, cuando se muestra, entonces es rojo y se distingue también por texto o ícono, no solo por color.  
* **Notas Técnicas / Riesgos:** Los porcentajes son una sugerencia y deben ser configurables. Accesibilidad: no depender solo del color. Dependencia: US-016.

#### **Historia de Usuario: US-018 \- Alertas escalonadas**

* **Enunciado:** Como jefe de área, quiero recibir alertas cuando una PQRSD se acerca al vencimiento, para que intervenga antes de que se incumpla el plazo.  
* **Prioridad:** Should Have  
* **Story Points:** 5  
* **Criterios de Aceptación:**  
  1. Dado que una PQRSD llega a estado amarillo, cuando corre la revisión periódica, entonces el empleado asignado ve una alerta en la plataforma.  
  2. Dado que llega a estado rojo y sigue sin respuesta aprobada, cuando corre la revisión, entonces la alerta escala al jefe de área.  
  3. Dado que una PQRSD ya fue respondida, cuando corre la revisión, entonces no genera alertas.  
* **Notas Técnicas / Riesgos:** Las alertas dentro de la plataforma bastan para la demo; el envío por correo queda en US-028. Para la demo se puede simular el paso del tiempo con fechas de radicación en el pasado. Dependencias: US-016, US-017.

### **Épica 6: Bandeja del empleado y edición del borrador**

*Es donde la persona toma la decisión final: ve qué es urgente, revisa el borrador y lo aprueba. Valor: cumple el principio de que la IA propone y el humano decide.*

#### **Historia de Usuario: US-019 \- Bandeja priorizada por vencimiento y área**

* **Enunciado:** Como empleado del área, quiero ver mis PQRSD vigentes ordenadas por cercanía al vencimiento, para que atienda primero las más urgentes.  
* **Prioridad:** Must Have  
* **Story Points:** 5  
* **Criterios de Aceptación:**  
  1. Dado que inicio sesión, cuando abro la bandeja, entonces veo solo las PQRSD de mi área, con tipo, radicado, semáforo y fecha de vencimiento.  
  2. Dado que hay PQRSD de distintos plazos, cuando se ordena la lista, entonces las rojas y las más próximas a vencer aparecen primero.  
  3. Dado que filtro por tipo o estado, cuando aplico el filtro, entonces la lista se actualiza sin recargar la página.  
* **Notas Técnicas / Riesgos:** Con pocos casos de demo no hace falta paginar, pero la consulta debe usar un índice por vencimiento. Dependencias: US-014, US-017.

#### **Historia de Usuario: US-020 \- Editor de borrador con aprobación**

* **Enunciado:** Como empleado del área, quiero abrir una PQRSD, revisar el borrador con sus citas, editarlo y aprobarlo, para que la respuesta salga con mi criterio.  
* **Prioridad:** Must Have  
* **Story Points:** 5  
* **Criterios de Aceptación:**  
  1. Dado que abro una PQRSD, cuando se carga el detalle, entonces veo el texto original, el borrador y las tarjetas de cita con su fuente.  
  2. Dado que edito el borrador a mano, cuando guardo, entonces se conserva la versión original y la editada.  
  3. Dado que apruebo la respuesta, cuando confirmo, entonces el estado pasa a "respondida" y queda registrado quién aprobó y cuándo.  
  4. Dado que no he aprobado, cuando intento enviar, entonces el sistema lo impide.  
* **Notas Técnicas / Riesgos:** El envío real al ciudadano puede simularse en la demo cambiando el estado visible en US-010. Dependencias: US-013, US-019.

#### **Historia de Usuario: US-021 \- Edición del borrador por chat**

* **Enunciado:** Como empleado del área, quiero pedirle cambios al borrador en lenguaje natural, para que lo ajuste sin que tenga que reescribirlo.  
* **Prioridad:** Should Have  
* **Story Points:** 5  
* **Criterios de Aceptación:**  
  1. Dado que escribo "hazlo más formal" o "agrega el plazo", cuando envío la instrucción, entonces el borrador se actualiza y mantiene las citas.  
  2. Dado que el cambio no me gusta, cuando lo deshago, entonces vuelvo a la versión anterior del borrador.  
  3. Dado que pido algo que contradice las fuentes, cuando el agente responde, entonces me avisa en lugar de inventar contenido.  
  4. Dado que uso el chat, cuando se hace la llamada, entonces solo se envían el borrador y la instrucción, no todo el historial.  
* **Notas Técnicas / Riesgos:** Enviar solo lo necesario controla el costo. Dependencias: US-013, US-015, US-020.

#### **Historia de Usuario: US-022 \- Acceso por roles**

* **Enunciado:** Como jefe de área, quiero que cada empleado vea solo lo que le corresponde, para que la información de las solicitudes esté protegida.  
* **Prioridad:** Should Have  
* **Story Points:** 3  
* **Criterios de Aceptación:**  
  1. Dado que no he iniciado sesión, cuando intento abrir la bandeja o el dashboard, entonces soy redirigido al inicio de sesión.  
  2. Dado que soy empleado de un área, cuando consulto PQRSD de otra área, entonces el sistema me lo niega.  
  3. Dado que soy jefe de área, cuando abro el dashboard, entonces veo las métricas de mi área.  
* **Notas Técnicas / Riesgos:** Para la demo basta con usuarios y contraseñas ficticios definidos en variables de entorno o una tabla simple; no usar credenciales corporativas reales. Contraseñas con hash, nunca en texto plano.

### **Épica 7: Aprendizaje, dashboard y métricas**

*Convierte "usamos IA" en evidencia: el sistema mejora con las correcciones y muestra cifras. Valor: argumentos concretos para el jurado y para un cliente real.*

#### **Historia de Usuario: US-023 \- Aprendizaje con las ediciones del empleado**

* **Enunciado:** Como jefe de área, quiero que el sistema aprenda de las correcciones de mi equipo, para que los borradores futuros necesiten menos cambios.  
* **Prioridad:** Should Have  
* **Story Points:** 5  
* **Criterios de Aceptación:**  
  1. Dado que un empleado aprueba una respuesta editada, cuando se guarda, entonces se almacena la pareja borrador original y versión final con su tipo y área.  
  2. Dado que se genera un nuevo borrador del mismo tipo y área, cuando se arma el prompt, entonces incluye como máximo 2 o 3 ejemplos aprobados de esa categoría.  
  3. Dado que no hay ediciones guardadas para esa categoría, cuando se genera el borrador, entonces el flujo funciona igual sin ejemplos.  
* **Notas Técnicas / Riesgos:** Más ejemplos en el prompt aumentan el costo; limitar cantidad y longitud. Riesgo de aprender errores: solo se usan respuestas aprobadas. Dependencias: US-013, US-020.

#### **Historia de Usuario: US-024 \- Dashboard de métricas**

* **Enunciado:** Como jefe de área, quiero un panel con el estado de las PQRSD, para que vea la carga de trabajo y los riesgos de vencimiento.  
* **Prioridad:** Should Have  
* **Story Points:** 5  
* **Criterios de Aceptación:**  
  1. Dado que abro el dashboard, cuando se carga, entonces veo PQRSD por área y por tipo, y cuántas están por vencer o vencidas.  
  2. Dado que hay respuestas aprobadas, cuando consulto, entonces veo el tiempo promedio de respuesta y el porcentaje de borradores aprobados sin cambios.  
  3. Dado que cambia el estado de una PQRSD, cuando recargo el panel, entonces las cifras reflejan el cambio.  
* **Notas Técnicas / Riesgos:** Consultas agregadas directas a PostgreSQL; evitar cálculos pesados en el frontend. Dependencias: US-019, US-020, US-025.

#### **Historia de Usuario: US-025 \- Evaluación de precisión del clasificador**

* **Enunciado:** Como equipo de producto, quiero medir qué tan bien clasifica el sistema, para que podamos mostrar una cifra de precisión y calibrar el umbral de confianza.  
* **Prioridad:** Should Have  
* **Story Points:** 3  
* **Criterios de Aceptación:**  
  1. Dado que existe el set de prueba etiquetado, cuando ejecuto `evaluar_clasificador.py`, entonces obtengo la precisión de tipo y de área.  
  2. Dado que termina la evaluación, cuando reviso el resultado, entonces veo los casos mal clasificados con la confianza que tenían.  
  3. Dado que cambia el prompt del clasificador, cuando repito la evaluación, entonces puedo comparar la precisión con la corrida anterior.  
* **Notas Técnicas / Riesgos:** Correr con un set pequeño (unos 50 casos) para no gastar presupuesto. Dependencias: US-006, US-011.

### **Épica 8: Demo, entrega y extras**

*Asegura que lo construido se pueda mostrar sin fallos y entregar completo el viernes 13 a las 10:30. Los extras solo se abordan si todo lo anterior funciona.*

#### **Historia de Usuario: US-026 \- Guion y ensayo de la demo**

* **Enunciado:** Como equipo de producto, quiero un guion de demo ensayado con casos precargados, para que la presentación muestre el flujo completo sin depender de la suerte.  
* **Prioridad:** Must Have  
* **Story Points:** 3  
* **Criterios de Aceptación:**  
  1. Dado que existe `docs/demo.md`, cuando lo reviso, entonces describe los 3 casos (feliz, plazo crítico y baja confianza o edición) con el orden y el tiempo de cada uno.  
  2. Dado que se ensaya, cuando se ejecuta el flujo, entonces una PQRSD entra y sale clasificada, asignada y con borrador antes del vencimiento.  
  3. Dado que puede fallar algo en vivo, cuando llega la presentación, entonces existe una grabación de respaldo del flujo completo.  
* **Notas Técnicas / Riesgos:** Precargar los casos de demo en la base de datos para no depender de la API durante la presentación. Dependencia: US-006 y las historias Must Have de las épicas 3 a 6\.

#### **Historia de Usuario: US-027 \- Documentación y entrega del código**

* **Enunciado:** Como líder técnico, quiero entregar el repositorio completo y documentado, para que el jurado pueda entenderlo y correrlo, y no se pierda nada al eliminarse el servidor.  
* **Prioridad:** Must Have  
* **Story Points:** 2  
* **Criterios de Aceptación:**  
  1. Dado que se prepara la entrega, cuando reviso el `README`, entonces explica qué es el proyecto, cómo correrlo y quién hizo qué.  
  2. Dado que se revisa `docs/arquitectura.md` y `docs/backlog.md`, cuando los abro, entonces reflejan el flujo de 4 pasos y las decisiones tomadas.  
  3. Dado que el código está en el repositorio, cuando se clona en limpio, entonces no contiene `.env` ni `.pem` y `.env.example` está completo.  
* **Notas Técnicas / Riesgos:** La entrega es el viernes 13 a las 10:30; el servidor y la llave se eliminan al cierre del evento.

#### **Historia de Usuario: US-028 \- Extras: notificaciones por correo, avatar con video o voz**

* **Enunciado:** Como ciudadano o empleado, quiero recibir avisos por correo y, si es posible, interactuar con un avatar más expresivo, para que la experiencia sea más cercana.  
* **Prioridad:** Could Have (el avatar con video o voz es Won't Have en esta iteración)  
* **Story Points:** 8  
* **Criterios de Aceptación:**  
  1. Dado que una PQRSD pasa a estado rojo, cuando corre la revisión de alertas, entonces se envía un correo ficticio o simulado al empleado asignado.  
  2. Dado que el ciudadano abre el chat, cuando se muestra el avatar, entonces es una ilustración animada que no consume llamadas adicionales a la API.  
  3. Dado que todas las historias Must Have están completas y probadas, cuando queda tiempo, entonces se evalúa este trabajo; si no, se descarta sin afectar la entrega.  
* **Notas Técnicas / Riesgos:** El video o la voz realistas consumen presupuesto y tiempo y no suman funcionalidad. Dependencias: US-008, US-018. Usar solo direcciones de correo ficticias.
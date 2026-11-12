# **Propuesta de solución — Gestión inteligente de PQRSD · Coffee Devs**

## **Resumen**

Coffee Devs propone una plataforma que recibe una PQRSD, la clasifica, la asigna al área correcta, redacta un borrador con citas de la normativa y avisa antes de que venza el plazo legal. Un empleado revisa y aprueba cada respuesta: la IA propone, la persona decide.

La plataforma incluye:

* Un **agente de chat** que atiende dudas con la base de conocimiento y, si hace falta, ayuda a radicar la PQRSD.  
* Un **motor de plazos** que calcula el vencimiento en días hábiles y muestra un semáforo con alertas.  
* Un **pipeline de IA** que clasifica (tipo, área, confianza), recupera normativa con RAG y redacta el borrador con citas.  
* Una **bandeja para el empleado** con editor, chat para corregir el borrador y aprobación obligatoria.  
* Un **dashboard** con métricas, incluida la precisión del clasificador.  
* Una **empresa ficticia** con datos y casos en español para toda la demo.

Diferenciadores frente a un sistema tradicional: radicación conversacional, desvío de consultas que no requieren PQRSD, enrutamiento según confianza, edición del borrador por chat, aprendizaje a partir de las correcciones del empleado y precisión del clasificador medida en cifras.

## **Alcance por niveles**

Se construye en este orden; no se empieza un nivel hasta que el anterior funcione de punta a punta.

| Nivel | Qué incluye | Cuándo |
| ----- | ----- | ----- |
| 1\. Imprescindible | Radicación (formulario o chat simple), clasificador (tipo, área, confianza), RAG, borrador con citas, bandeja con semáforo de vencimiento, botón de aprobar, 3 casos de demo ensayados | Miércoles 11 y jueves 12 (mañana) |
| 2\. Diferenciadores | Chat de radicación que extrae campos y detecta datos faltantes, desvío antes de radicar, edición del borrador por chat, dashboard de métricas, aprendizaje con las ediciones, precisión del clasificador | Jueves 12 |
| 3\. Extras | Avatar visual, voz, notificaciones por correo | Solo si sobra tiempo, antes de la entrega del viernes 13 a las 10:30 |

### **Orden de construcción**

1. Servidor, repositorio, Docker Compose y base de datos con pgvector.  
2. Empresa ficticia, base de conocimiento y casos de demo.  
3. Flujo mínimo de punta a punta: radicación, clasificador, RAG y borrador con citas.  
4. Motor de plazos y bandeja con semáforo y aprobación.  
5. Chat de radicación con desvío de consultas.  
6. Edición del borrador por chat, aprendizaje con las ediciones, dashboard y métricas.  
7. Ensayo de la demo, prueba de precisión del clasificador y entrega del código el viernes 13\.

## **Flujo de punta a punta**

Las dudas que la base de conocimiento resuelve no se radican; las demás se clasifican, se asignan y reciben un borrador, y solo salen con la aprobación de un empleado.

## **Componentes**

### **1\. Agente de radicación (chat)**

El ciudadano cuenta su situación en un chat. El agente responde con la base de conocimiento; si la duda se resuelve, no se radica nada (desvío). Si no, o si la persona decide continuar, el agente recoge los campos de la PQRSD (hechos, fechas, datos de contacto, producto o servicio), avisa qué falta y la radica. Para el avatar basta una ilustración fija o animada junto al chat.

**Implementado (US-009, desvío):** `backend/app/pipeline/desvio.py` y `/api/chat`. Para buscar se usan los dos últimos mensajes del ciudadano. Si el RAG no supera el umbral, se responde un mensaje fijo sin llamar a Claude. Si hay contexto, el modelo liviano responde en JSON (`cobertura` y `respuesta`) citando los fragmentos con `[F#]`. Una respuesta sin citas válidas se reemplaza por el mensaje fijo. "Continuar con una PQRSD" solo sugiere asunto y descripción; la radicación la hará US-007/US-008. La tabla `consultas_desvio` permite medir la tasa de desvío (`GET /api/chat/metricas`). El historial de cada conversación vive en memoria del backend.

### **2\. Motor de plazos**

Al radicar, calcula la fecha de vencimiento según el tipo de solicitud, en días hábiles y con festivos colombianos. Los plazos se guardan como configuración, no en el código. Antes de citar la Ley 1755 de 2015, el equipo debe verificar los plazos exactos por tipo (el reto menciona 15 días hábiles, pero la ley distingue otros términos para documentos y consultas).

Semáforo sugerido: verde (más de 50 % del plazo restante), amarillo (entre 20 % y 50 %), rojo (menos de 20 % o vencida). Las alertas escalan: aviso al empleado asignado, luego a su jefe de área.

### **3\. Pipeline de IA**

1. **Clasificador:** tipo (petición, queja, reclamo, sugerencia, denuncia), área y confianza. Modelo liviano, con ejemplos en el prompt.  
2. **RAG:** recupera fragmentos de la normativa y las políticas ficticias desde pgvector.  
3. **Generador:** redacta el borrador citando las fuentes recuperadas; si el contexto no alcanza, lo dice en lugar de inventar.  
4. **Enrutamiento por confianza:** con confianza alta va directo al área; con confianza baja pasa primero a revisión humana de la clasificación.

### **4\. Bandeja del empleado**

Lista de PQRSD vigentes, filtrada por área y ordenada por vencimiento, con el semáforo visible. Al abrir una, el empleado ve el borrador con sus citas y puede aprobarlo, editarlo a mano, regenerarlo o pedir cambios por chat ("hazlo más formal", "agrega el plazo"). Nada se envía sin aprobación.

### **5\. Aprendizaje con las ediciones**

Cada corrección del empleado se guarda junto al borrador original. Las mejores parejas (borrador, versión final) del mismo tipo y área se inyectan como ejemplos en futuros borradores.

### **6\. Dashboard de métricas**

PQRSD por área y por tipo, casos por vencer, tiempo promedio de respuesta, porcentaje de borradores aprobados sin cambios y precisión del clasificador.

## **Estrategia de IA y presupuesto**

Todo el evento tiene 40 USD en API de Claude, y las pruebas gastan más que la demo. La regla es usar el modelo más barato que haga bien cada tarea.

| Tarea | Modelo | Control de costo |
| ----- | ----- | ----- |
| Chat de radicación y respuestas de la base de conocimiento | Liviano (Haiku) | Tope de mensajes por sesión, `max_tokens` bajo |
| Clasificación (tipo, área, confianza) | Liviano (Haiku) | Salida en JSON corto, caché de prompt con los ejemplos fijos |
| Borrador final de respuesta | Más capaz (Sonnet) | Solo se llama cuando el caso ya está clasificado; `max_tokens` acotado |
| Edición del borrador por chat | Liviano o Sonnet según complejidad | Se envía solo el borrador y la instrucción, no todo el historial |

Medidas adicionales:

* Cachear en la base de datos los embeddings y las respuestas a preguntas repetidas.  
* Evaluar el clasificador con un set de prueba pequeño (por ejemplo 50 casos), no con miles de llamadas.  
* Reservar 10 USD para el ensayo de la demo y el día de la entrega; llevar un contador de gasto por endpoint.  
* La API key vive en `.env`, nunca en el repositorio.

## **Arquitectura técnica**

nginx recibe el tráfico: `/` va al frontend y `/api` al backend, que consulta PostgreSQL con pgvector y llama a la API de Claude.

### **Cambios a la estructura de carpetas**

La estructura original se mantiene; se agregan estas piezas (los nombres son una propuesta):

* `backend/app/pipeline/agente_intake.py`: agente de radicación con extracción de campos y detección de datos faltantes.  
* `backend/app/api/chat.py`: endpoint del chat de radicación y de edición del borrador.  
* `backend/app/pipeline/plazos.py`: motor de plazos con días hábiles, festivos y semáforo.  
* `backend/app/models/`: tabla adicional `ediciones` (borrador original y versión final aprobada).  
* `backend/app/pipeline/prompts/`: un `.md` por prompt (radicación, clasificador, generador, edición).  
* `frontend/src/pages/Chat.jsx`: chat de radicación con el avatar como ilustración.  
* `data/scripts/evaluar_clasificador.py`: mide la precisión sobre el set de prueba de `data/ejemplos/`.

## 

## **Datos y base de conocimiento**

La demo usa **una sola empresa ficticia** (por ejemplo, un banco o una aseguradora; el equipo elige una) con datos 100 % inventados, como exigen las reglas del evento.

* **Base de conocimiento (`data/conocimiento/`):** normativa colombiana relevante (Ley 1755 de 2015 y circulares de la Superintendencia Financiera o la SIC, si la empresa es financiera) más políticas, contratos y preguntas frecuentes ficticios, en español.  
* **Casos de prueba (`data/ejemplos/`):** unas 50 PQRSD sintéticas en español, etiquetadas por tipo y área, más los 3 casos de la demo. Pueden generarse con ayuda de Claude y revisarse a mano.  
* **Dataset CFPB:** está en inglés y es de finanzas de EE. UU. Se usa como referencia de categorías o para ideas de casos, no como entrenamiento ni como fuente de la demo.  
* **Términos:** usar PQRSD en todo el documento, el código y el pitch.

## **Demo, métricas de éxito y riesgos**

### **Demo (3 casos)**

1. **Caso feliz:** una queja entra por el chat, se clasifica con confianza alta, llega al área correcta con semáforo verde y borrador con citas; el empleado lo aprueba.  
2. **Caso de plazo crítico:** una PQRSD con semáforo rojo aparece primero en la bandeja y dispara la alerta.  
3. **Caso de baja confianza o edición:** la clasificación pasa a revisión humana, o el empleado corrige el borrador por chat y el sistema guarda la corrección.

El desvío (una duda resuelta sin radicar) puede abrir la demo en 20 segundos.

### **Métricas para el pitch**

| Métrica | Cómo se mide |
| ----- | ----- |
| Precisión del clasificador | Aciertos de tipo y de área sobre el set de prueba |
| Tiempo de radicación a borrador | Segundos, medidos en la demo |
| Borradores aprobados sin cambios | Porcentaje sobre los casos de prueba |
| Casos en rojo atendidos a tiempo | Casos con semáforo rojo gestionados antes del vencimiento |

### 

### **Riesgos y mitigación**

| Riesgo | Mitigación |
| ----- | ----- |
| Alcance demasiado grande para 48 horas | Trabajar por niveles; el nivel 3 se corta sin dudar |
| El borrador inventa normas o datos | RAG obligatorio, citas visibles y aviso cuando el contexto no alcanza |
| Se agota el presupuesto de 40 USD | Modelos livianos, caché, topes y contador de gasto |
| Fallo en vivo durante la demo | Casos de demo precargados y una grabación de respaldo |
| Plazos legales mal citados | Verificar la ley antes de escribirlos y dejarlos configurables |
| Pérdida del código al cerrar el servidor | Subir todo al repositorio a diario; el servidor y la llave se eliminan al final |

## 

## **Qué cambió respecto a la propuesta original**

Se mantiene la idea central: agente conversacional para radicar, dashboard con editor, aprobación humana, el pipeline de 4 pasos y el stack (FastAPI, React, pgvector, Docker). Estos son los cambios:

| Tema | Propuesta original | Ahora |
| :---: | :---: | :---: |
| Entrenamiento | El agente tendría "entrenamiento previo" con el dataset | RAG sobre la base de conocimiento y ejemplos en el prompt (few-shot); un agente con Claude no se entrena |
| Dataset CFPB | Base para entrenar el clasificador | Solo referencia de categorías; la demo usa casos ficticios en español de una sola empresa |
| Avatar | Pieza central del portal | Ilustración junto al chat; avatar con video o voz queda como extra (nivel 3\) |
| Plazos legales | Solo ordenar por fecha | Motor de plazos con días hábiles, festivos, semáforo y alertas escalonadas |
| Radicación | El chat ayuda a diligenciar la PQRS | Además extrae campos, detecta datos faltantes y desvía las dudas que no requieren radicar |
| Clasificación | Clasifica y asigna | Con enrutamiento por confianza: la confianza baja pasa a revisión humana |
| Mejora continua | No estaba | Las ediciones del empleado se guardan y alimentan futuros borradores |
| Métricas | Dashboard de PQRS vigentes | Dashboard con precisión del clasificador y tiempos de respuesta |
| Presupuesto | Mencionado en las restricciones | Modelo por tarea, topes de tokens y mensajes, caché y contador de gasto |
| Carpetas | Sin módulo de chat | Se agregan agente de radicación, plazos, tabla de ediciones, página de chat y script de evaluación |
| Alcance | Sin priorización | Tres niveles y orden de construcción para las 48 horas disponibles |
| Términos | Alterna entre PQRS y PQRSD | Se usa PQRSD en todo el material |



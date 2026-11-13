# **GESTIÓN INTELIGENTE DE PQRS \- COFFEE DEVS** 

## **Problema**

Una PQRS mal clasificada o respondida tarde no es solo un cliente molesto — es una multa. Y el reloj legal corre desde el segundo en que entra.

### **EL RETO**

Automatizar la gestión de PQRS, hoy manual y reactiva, pese a tener términos legales estrictos (15 días hábiles).

### **LA SOLUCIÓN DEBERÁ**

* Clasificar automáticamente la solicitud.  
* Asignarla al área correcta.  
* Redactar un borrador de respuesta.  
* Alertar vencimientos próximos.

### **DEMOSTRACIÓN FINAL**

Una PQRS entra al sistema y sale clasificada, asignada y con borrador de respuesta antes del vencimiento.

### **IMPACTO DE NEGOCIO**

Elimina el riesgo sancionatorio, descarga al equipo de atención y mejora los tiempos de respuesta. Aplica desde alcaldías hasta bancos y aseguradoras, con volúmenes altísimos y casi nula automatización.

### **FUENTES DE DATOS**

El “Consumer Complaint Database” de la CFPB en Kaggle (160.000+ quejas etiquetadas por tipo) para entrenar el clasificadores; complementado con la Ley 1755 de 2015 (derecho de petición), datos abiertos de PQRS en datos.gov.co, radicados históricos anonimizados, y circulares de la Superintendencia Financiera y de la SIC.

## **SERVIDOR Y REGLAS**

### **DATOS DEL SERVIDOR**

* Servidor: nepxa-hackathon-equipo-01  
* IP pública: 184.197.58.196  
* Usuario: ubuntu (solo con llave, sin contraseña)  
* Llave: nepxa-hackathon-equipo-01.pem (adjunta)  
* Comando: ssh \-i nepxa-hackathon-equipo-01.pem ubuntu@184.197.58.196

### **CÓMO CONECTARSE**

1. Guarda el .pem en una carpeta. No lo compartas fuera del equipo ni lo subas a un repositorio.  
2. Linux o macOS, en esa carpeta: chmod 600 nepxa-hackathon-equipo-01.pem  
   1. Windows 10/11, en PowerShell, si avisa que la llave está desprotegida:  
       icacls nepxa-hackathon-equipo-01.pem /inheritance:r /grant:r "$($env:USERNAME):R"  
3. Ejecuta el comando de arriba. La primera vez escribe yes para aceptar la huella del servidor.

### **QUÉ TRAE EL SERVIDOR**

* 2 vCPU, 8 GB de RAM, 50 GB de disco cifrado.  
* Ubuntu 24.04 LTS, Docker y Docker Compose (sin sudo), git, curl y jq.  
* Puertos abiertos: 22 (SSH), 80 y 443 para publicar la solución. Los demás están cerrados.  
* La base de datos se levanta dentro del servidor con Docker (por ejemplo, PostgreSQL).  
* Datasets del evento: [http\://10.20.1.18/](http://10.20.1.18/) (solo desde el servidor). Les avisaremos cuando estén publicados.

### **REGLAS**

* No usen datos reales de clientes ni contraseñas o credenciales corporativas.  
* Las API keys van en variables de entorno o en un .env que no se sube al repositorio.  
* Al cierre del evento el servidor y la llave se eliminan. Descarguen su código antes.

## **schedule:**

### **Miércoles 11**

* 09:30 Presentación de mentores a los equipos  
* 15:30 Mentoría y revisión del alcance · Teams  
* 17:30 Checkpoint y cierre del día

### **Jueves 12**

* 08:00 Revisión de avances y bloqueos  
* 11:00 Mentoría técnica  
* 16:00 Checkpoint de avances  
* 17:30 Revisión y preparación de la entrega

### **Viernes 13**

* 10:30 Entrega de código y documentación

## **Presupuesto y Restricciones de IA**

* **Presupuesto disponible:** 40 USD en API Key de Claude para todo el evento.

* **Estrategia de uso de IA:** Uso de modelos livianos/económicos para clasificación y un modelo más capaz únicamente para la redacción final; optimización mediante límites de max\_tokens y cacheo.

## **Arquitectura del Flujo de Trabajo (PQRSD)**

1. **Clasificador:** Determina tipo (petición, queja, reclamo, sugerencia, denuncia), área (ej. Cartera, Jurídica) y nivel de confianza.  
2. **Motor de Búsqueda (RAG):** Consulta base de conocimiento (políticas internas y normativa) y recupera fragmentos relevantes.  
3. **Generador (Claude API):** Redacta el borrador citando fuentes (sin inventar datos ni normas).  
4. **Validación humana (Human-in-the-loop):** Bandeja donde un agente revisa, edita, regenera o aprueba el borrador antes de enviarlo.

## **Políticas de Seguridad y Repositorio**

* **Versionamiento:** Externo; todo el trabajo debe estar sincronizado en el repositorio del equipo (el servidor se elimina al finalizar).  
* **Seguridad:** Uso estricto de datos ficticios. Variables de entorno (.env) y archivos .pem no deben subirse al repositorio Git.

## **Estructura de carpetas**

```sh
pqrsd-coffedevs/
├── README.md                 # Qué es, cómo correrlo, quién hace qué
├── .gitignore                # .env, *.pem, node_modules, _pycache_, datos
├── .env.example              # Variables sin valores reales (ANTHROPIC_API_KEY=, DB_URL=...)
├── docker-compose.yml        # db + backend + frontend + nginx
├── CLAUDE.md                 # El prompt del proyecto que armamos
│
├── backend/                  # FastAPI
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/
│       ├── main.py           # Arranque de la API
│       ├── config.py         # Lee variables de entorno
│       ├── db.py             # Conexión a PostgreSQL
│       ├── models/           # Tablas: pqrsd, borradores, revisiones
│       ├── api/              # Endpoints
│       │   ├── pqrsd.py      # Radicar y consultar estado
│       │   ├── bandeja.py    # Listar, aprobar, editar, rechazar
│       │   └── metricas.py   # Datos del dashboard
│       └── pipeline/         # El flujo de IA, un archivo por paso
│           ├── clasificador.py   # 1. Tipo y área + confianza
│           ├── rag.py            # 2. Búsqueda en pgvector
│           ├── generador.py      # 3. Borrador con Claude
│           └── prompts/          # Prompts en archivos .md, no dentro del código
│
├── frontend/                 # React
│   ├── Dockerfile
│   ├── package.json
│   └── src/
│       ├── pages/            # Radicar, Confirmación, Estado, Bandeja, Detalle, Dashboard
│       ├── components/       # Botones, semáforo, tarjetas de cita, etc.
│       ├── services/api.js   # Llamadas al backend
│       └── styles/           # Tokens de color y tipografía (guía visual)
│
├── data/
│   ├── conocimiento/         # Normativa y políticas ficticias para el RAG
│   ├── ejemplos/             # PQRSD de prueba y los 3 casos de la demo
│   └── scripts/
│       ├── cargar_conocimiento.py  # Genera embeddings y llena pgvector
│       └── descargar_datasets.sh   # Baja los datasets del evento (desde el servidor)
│
├── nginx/
│   └── nginx.conf            # Puerto 80/443: / al front, /api al back
│
└── docs/
    ├── arquitectura.md       # El flujo de 4 pasos y decisiones tomadas
    ├── backlog.md            # O enlace al tablero
    └── demo.md               # Guion del pitch
```

# **SOLUCIÓN PROPUESTA V1**

Plataforma web para la diligenciar y gestionar PQRS asistidos por inteligencia artificial

### **Agente de IA**

Los usuarios que quieran diligenciar una PQRS ingresarán al portal y se encontrarán con un avatar de IA con el cual podrán dialogar para comentarle su situación. El avatar estará controlado por un agente de IA que tendrá un entrenamiento previo con el dataset entregado para este reto, para poder responder las dudas de los usuarios de manera acorde. 

Además, este tendrá una fuente de conocimiento con el contexto del negocio, para poder responder de manera puntual a las preguntas o quejas que realicen los usuarios, de acuerdo a las normas, documentación y contratos de la empresa.

En caso de que el agente no pueda resolver la solicitud del usuario, o que el usuario decida continuar con el proceso de PQRS, el chat podrá ayudar a los usuarios a diligenciar su PQRS para subirla al sistema.

### **Dashboard de PQRS**

Los empleados de la empresa podrán ingresar a la plataforma y podrán visualizar las PQRS vigentes, auto clasificadas por las áreas/departamentos que maneja la organización, y ordenadas por fecha, para poder dar prioridad a aquellas PQRS que están más próximas a vencer. 

Al seleccionar una PQRS, se abrirá un editor de texto en el cual ya hay habrá un borrador con la respuesta propuesta por el agente de IA,  el empleado podrá enviar o editar de manera manual está respuesta segun su criterio, o podra dialogar con el agente para pedirle las correcciones u observaciones que considere necesarias.

### **Observaciones**

La idea no es hacer un sistema de PQRS tradicional, y meterle solo un poco de IA que ayude a clasificar y hacer borradores de respuestas, queremos hacer una integración que pueda ir mas allá. 


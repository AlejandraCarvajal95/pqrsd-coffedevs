# Dataset de entrenamiento de los SVM del embudo de clasificación

Dataset en español para entrenar los SVM que clasifican cada PQRSD por capas: tipo, área, tema, sentimiento y riesgo de fraude. **No contiene datos sintéticos**: todos los textos vienen de fuentes públicas reales. **No contiene datos personales reales**: los nombres, documentos, teléfonos, correos, direcciones y números de radicado se reemplazaron por valores ficticios.

Los datos generados viven en `data/datasets/`, que está en `.gitignore`. Este directorio solo versiona el código para regenerarlos.

## Fuentes

| Fuente | Qué aporta | Idioma | Licencia |
| --- | --- | --- | --- |
| [CFPB Consumer Complaint Database](https://huggingface.co/datasets/Bob-68/cfpb-consumer-complaints) | Quejas bancarias reales: tarjetas, cobranza, centrales de riesgo, suplantación, seguro de deuda | Inglés (se traduce) | Dominio público (EE. UU.) |
| [BANKING77](https://huggingface.co/datasets/PolyAI/banking77) | Preguntas y peticiones reales de clientes sobre tarjetas | Inglés (se traduce) | CC BY 4.0 |
| [Amazon Reviews Multi, español](https://huggingface.co/datasets/SetFit/amazon_reviews_multi_es) | Sentimiento (estrellas) y sugerencias reales | Español | Licencia de Amazon, uso académico |
| [Alcaldía de Flandes](https://www.datos.gov.co/d/gb9w-jt96) | PQRS reales con texto completo del ciudadano | Español | Datos abiertos de Colombia |
| [MinDeporte](https://www.datos.gov.co/d/bx26-pux4) | Peticiones, quejas y denuncias reales | Español | Datos abiertos de Colombia |
| [Contraloría del Valle](https://www.datos.gov.co/d/5nek-piwp), [Contraloría de Villavicencio](https://www.datos.gov.co/d/ru4m-fu5i) | Denuncias y peticiones reales | Español | Datos abiertos de Colombia |
| [Superfinanciera: quejas por producto y motivo](https://www.datos.gov.co/d/xyy7-rn7p) | La taxonomía de temas (motivos oficiales de queja) | Español | Datos abiertos de Colombia |

## Pasos

```bash
docker build -t pqrsd-dataset data/scripts/dataset
docker run --rm -v "$PWD/data:/data" pqrsd-dataset python scripts/dataset/01_descargar.py cfpb banking77 amazon_es datos_gov
docker run --rm -v "$PWD/data:/data" pqrsd-dataset python scripts/dataset/02_extraer.py
docker run --rm -v "$PWD/data:/data" pqrsd-dataset python scripts/dataset/03_anonimizar.py
docker compose run --rm --user root -v "$PWD/data/datasets:/data/datasets" backend python /data/scripts/dataset/04_reetiquetar.py
docker compose run --rm --user root -v "$PWD/data/datasets:/data/datasets" backend python /data/scripts/dataset/06_traducir.py enviar
docker compose run --rm --user root -v "$PWD/data/datasets:/data/datasets" backend python /data/scripts/dataset/06_traducir.py recoger   # cuando el lote termine
docker run --rm -v "$PWD/data:/data" pqrsd-dataset python scripts/dataset/05_construir.py
```

| Paso | Qué hace |
| --- | --- |
| `01_descargar.py` | Baja las fuentes a `crudo/` |
| `02_extraer.py` | Filtra y muestrea cada fuente, mapea el CFPB y BANKING77 a área y tema (`config.py`) y unifica todo en un esquema común |
| `03_anonimizar.py` | Reemplaza los datos personales por datos ficticios (spaCy + expresiones regulares + Faker `es_CO`). Desde aquí el texto original ya no se usa |
| `04_reetiquetar.py` | Claude (modelo liviano) corrige el tipo, pone el sentimiento y marca posibles datos personales que se escaparon. Usa `costos.llamar_claude`, así que el gasto queda en `/api/costos` |
| `06_traducir.py` | Traduce, localiza (pesos, entidades colombianas) y reetiqueta el CFPB y BANKING77 con la Batch API (50 % más barata). Limpia localmente las censuras que el modelo deje y registra el gasto en `/api/costos` |
| `05_construir.py` | Arma `final/maestro` y un archivo balanceado por capa con su split. En tipo y sentimiento intercala las fuentes para que ninguna clase quede asociada al estilo de una sola fuente |

Costo real de la primera corrida: 0,93 USD el reetiquetado y 0,62 USD la traducción, con Claude Haiku 5.5.

## Resultado (`data/datasets/final/`)

| Archivo | Contenido |
| --- | --- |
| `maestro.parquet` / `.csv` | Todas las filas con todas las etiquetas conocidas y su origen |
| `capas/tipo` | petición, queja, reclamo, sugerencia, denuncia |
| `capas/area` | tarjetas, cartera, seguros, jurídica, fuera de competencia |
| `capas/tema_<área>` | Motivos de la Superfinanciera dentro de cada área |
| `capas/sentimiento` | negativo, neutral, positivo |
| `capas/fraude` | sí, no |
| `muestra_revision_humana.csv` | 100 filas cuyo tipo cambió al reetiquetar, para revisión del equipo |
| `resumen.json` | Conteos por capa, clase, fuente y split |

Cada capa trae la columna `split` (`train` 70 %, `val` 15 %, `test` 15 %), estratificada por clase y determinista. Las clases se limitan a un cupo y **no se duplican filas** para emparejarlas: las clases más chicas se compensan con `class_weight="balanced"` al entrenar.

La métrica que se reporta en la demo sale del **golden set escrito a mano por el equipo**, que no está en este dataset y nunca se usa para entrenar.

## Decisiones y límites

- **Etiquetas:** las de datos.gov.co las eligió el ciudadano en un formulario y muchas estaban mal (por ejemplo, "sugerencias" que eran peticiones de paz y salvo). Por eso todas se reetiquetaron. El tipo original queda en `tipo_fuente` para auditar.
- **CFPB:** el tipo inicial sale del mapeo de `issue` y `sub_issue` (`config.mapear_cfpb`) y se corrige al traducir. Los reportes de crédito posteriores a 2022 se excluyen porque en su mayoría son cartas plantilla.
- **Seguros de Vida:** solo hay unas 525 quejas reales (seguro de deuda de tarjeta del CFPB) y todas caen en un tema, así que esa área no tiene SVM de tema.
- **Sentimiento:** las estrellas de Amazon distinguen negativo, neutral y positivo, no grados de enojo.
- **Datos personales:** toda fila que el reetiquetado marque como sospechosa se descarta, aunque sus datos ya parezcan ficticios.

# Métricas de los SVM

Evaluación en el split de test (el modelo nunca lo vio). La métrica de la demo debe salir del golden set escrito por el equipo.

| Capa | Clases | F1 macro | Exactitud | C | Test |
| --- | --- | --- | --- | --- | --- |
| area | 5 | 0.767 | 0.790 | 0.05 | 649 |
| fraude | 2 | 0.810 | 0.810 | 0.2 | 226 |
| sentimiento | 3 | 0.790 | 0.777 | 0.2 | 1246 |
| tema_cartera | 4 | 0.623 | 0.629 | 0.2 | 143 |
| tema_juridica | 2 | 0.750 | 0.750 | 0.05 | 88 |
| tema_tarjetas | 7 | 0.783 | 0.802 | 0.2 | 248 |
| tipo | 5 | 0.650 | 0.638 | 0.2 | 686 |

## area

| Clase | Precisión | Exhaustividad | F1 | n |
| --- | --- | --- | --- | --- |
| cartera | 0.73 | 0.72 | 0.73 | 145 |
| fuera_de_competencia | 0.98 | 0.99 | 0.99 | 149 |
| juridica | 0.79 | 0.77 | 0.78 | 133 |
| seguros | 0.59 | 0.56 | 0.57 | 73 |
| tarjetas | 0.75 | 0.79 | 0.77 | 149 |

Acierto por fuente: banking77 100%, cfpb 68%, datos_gov_contraloria_valle 100%, datos_gov_contraloria_villavicencio 100%, datos_gov_flandes 100%, datos_gov_mindeporte 97%

Umbral de confianza → cobertura / precisión: ≥0.5: 92% / 83%, ≥0.6: 78% / 88%, ≥0.7: 67% / 90%, ≥0.8: 54% / 95%, ≥0.9: 33% / 99%

## fraude

| Clase | Precisión | Exhaustividad | F1 | n |
| --- | --- | --- | --- | --- |
| no | 0.81 | 0.81 | 0.81 | 113 |
| si | 0.81 | 0.81 | 0.81 | 113 |

Acierto por fuente: banking77 90%, cfpb 79%

Umbral de confianza → cobertura / precisión: ≥0.5: 100% / 81%, ≥0.6: 87% / 85%, ≥0.7: 74% / 88%, ≥0.8: 53% / 92%, ≥0.9: 28% / 94%

## sentimiento

| Clase | Precisión | Exhaustividad | F1 | n |
| --- | --- | --- | --- | --- |
| negativo | 0.73 | 0.73 | 0.73 | 449 |
| neutral | 0.69 | 0.77 | 0.73 | 449 |
| positivo | 0.99 | 0.84 | 0.91 | 348 |

Acierto por fuente: amazon_es 86%, banking77 78%, cfpb 17%, datos_gov_contraloria_valle 61%, datos_gov_contraloria_villavicencio 74%, datos_gov_flandes 77%, datos_gov_mindeporte 88%

Umbral de confianza → cobertura / precisión: ≥0.5: 95% / 80%, ≥0.6: 78% / 85%, ≥0.7: 57% / 90%, ≥0.8: 34% / 94%, ≥0.9: 13% / 96%

## tema_cartera

| Clase | Precisión | Exhaustividad | F1 | n |
| --- | --- | --- | --- | --- |
| acuerdos_de_pago | 0.80 | 0.86 | 0.83 | 36 |
| cobranza | 0.60 | 0.50 | 0.55 | 36 |
| reporte_centrales_riesgo | 0.57 | 0.71 | 0.63 | 35 |
| saldo_paz_y_salvo | 0.53 | 0.44 | 0.48 | 36 |

Acierto por fuente: cfpb 63%

Umbral de confianza → cobertura / precisión: ≥0.5: 64% / 74%, ≥0.6: 44% / 82%, ≥0.7: 27% / 90%, ≥0.8: 6% / 100%

## tema_juridica

| Clase | Precisión | Exhaustividad | F1 | n |
| --- | --- | --- | --- | --- |
| suplantacion_identidad | 0.73 | 0.80 | 0.76 | 44 |
| uso_indebido_datos | 0.78 | 0.70 | 0.74 | 44 |

Acierto por fuente: cfpb 75%

Umbral de confianza → cobertura / precisión: ≥0.5: 100% / 75%, ≥0.6: 86% / 79%, ≥0.7: 75% / 85%, ≥0.8: 52% / 89%, ≥0.9: 24% / 90%

## tema_tarjetas

| Clase | Precisión | Exhaustividad | F1 | n |
| --- | --- | --- | --- | --- |
| atencion_y_canales | 0.77 | 0.81 | 0.79 | 32 |
| cancelacion | 0.68 | 0.89 | 0.77 | 26 |
| cobros_comisiones_intereses | 0.82 | 0.72 | 0.77 | 39 |
| entrega_activacion_bloqueo | 0.95 | 0.84 | 0.89 | 44 |
| pagos | 0.65 | 0.55 | 0.59 | 20 |
| transaccion_mal_aplicada | 0.80 | 0.91 | 0.85 | 44 |
| transaccion_no_reconocida | 0.85 | 0.79 | 0.82 | 43 |

Acierto por fuente: banking77 94%, cfpb 67%

Umbral de confianza → cobertura / precisión: ≥0.5: 78% / 90%, ≥0.6: 60% / 93%, ≥0.7: 45% / 96%, ≥0.8: 29% / 99%, ≥0.9: 9% / 100%

## tipo

| Clase | Precisión | Exhaustividad | F1 | n |
| --- | --- | --- | --- | --- |
| denuncia | 0.80 | 0.85 | 0.82 | 149 |
| peticion | 0.58 | 0.60 | 0.59 | 149 |
| queja | 0.51 | 0.51 | 0.51 | 149 |
| reclamo | 0.53 | 0.47 | 0.50 | 149 |
| sugerencia | 0.80 | 0.86 | 0.83 | 90 |

Acierto por fuente: amazon_es 73%, banking77 68%, cfpb 46%, datos_gov_contraloria_valle 91%, datos_gov_contraloria_villavicencio 81%, datos_gov_flandes 55%, datos_gov_mindeporte 55%

Umbral de confianza → cobertura / precisión: ≥0.5: 75% / 73%, ≥0.6: 54% / 80%, ≥0.7: 38% / 86%, ≥0.8: 22% / 93%, ≥0.9: 5% / 100%

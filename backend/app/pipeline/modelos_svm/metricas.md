# Métricas de los SVM

Evaluación en el split de test (el modelo nunca lo vio). La métrica de la demo debe salir del golden set escrito por el equipo.

| Capa | Clases | F1 macro | Exactitud | C | Test |
| --- | --- | --- | --- | --- | --- |
| area | 5 | 0.773 | 0.795 | 0.2 | 649 |
| fraude | 2 | 0.810 | 0.810 | 0.2 | 226 |
| sentimiento | 3 | 0.793 | 0.780 | 1.0 | 1246 |
| tema_cartera | 4 | 0.623 | 0.629 | 0.2 | 143 |
| tema_juridica | 2 | 0.750 | 0.750 | 0.05 | 88 |
| tema_tarjetas | 7 | 0.751 | 0.774 | 1.0 | 248 |
| tipo | 5 | 0.656 | 0.644 | 0.2 | 686 |

## area

| Clase | Precisión | Exhaustividad | F1 | n |
| --- | --- | --- | --- | --- |
| cartera | 0.74 | 0.72 | 0.73 | 145 |
| fuera_de_competencia | 0.98 | 0.99 | 0.99 | 149 |
| juridica | 0.76 | 0.76 | 0.76 | 133 |
| seguros | 0.61 | 0.59 | 0.60 | 73 |
| tarjetas | 0.77 | 0.80 | 0.79 | 149 |

Acierto por fuente: banking77 100%, cfpb 69%, datos_gov_contraloria_valle 100%, datos_gov_contraloria_villavicencio 100%, datos_gov_flandes 100%, datos_gov_mindeporte 97%

Umbral de confianza → cobertura / precisión: ≥0.5: 93% / 83%, ≥0.6: 77% / 89%, ≥0.7: 67% / 92%, ≥0.8: 53% / 95%, ≥0.9: 31% / 99%

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
| negativo | 0.74 | 0.75 | 0.75 | 449 |
| neutral | 0.69 | 0.77 | 0.73 | 449 |
| positivo | 0.99 | 0.83 | 0.90 | 348 |

Acierto por fuente: amazon_es 85%, banking77 80%, cfpb 26%, datos_gov_contraloria_valle 60%, datos_gov_contraloria_villavicencio 73%, datos_gov_flandes 80%, datos_gov_mindeporte 89%

Umbral de confianza → cobertura / precisión: ≥0.5: 95% / 80%, ≥0.6: 75% / 86%, ≥0.7: 54% / 90%, ≥0.8: 33% / 93%, ≥0.9: 12% / 96%

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
| atencion_y_canales | 0.78 | 0.78 | 0.78 | 32 |
| cancelacion | 0.64 | 0.89 | 0.74 | 26 |
| cobros_comisiones_intereses | 0.78 | 0.72 | 0.75 | 39 |
| entrega_activacion_bloqueo | 0.92 | 0.82 | 0.87 | 44 |
| pagos | 0.60 | 0.45 | 0.51 | 20 |
| transaccion_mal_aplicada | 0.81 | 0.86 | 0.83 | 44 |
| transaccion_no_reconocida | 0.77 | 0.77 | 0.77 | 43 |

Acierto por fuente: banking77 93%, cfpb 62%

Umbral de confianza → cobertura / precisión: ≥0.5: 76% / 90%, ≥0.6: 59% / 94%, ≥0.7: 46% / 96%, ≥0.8: 29% / 99%, ≥0.9: 11% / 96%

## tipo

| Clase | Precisión | Exhaustividad | F1 | n |
| --- | --- | --- | --- | --- |
| denuncia | 0.82 | 0.85 | 0.84 | 149 |
| peticion | 0.58 | 0.61 | 0.59 | 149 |
| queja | 0.52 | 0.52 | 0.52 | 149 |
| reclamo | 0.54 | 0.46 | 0.49 | 149 |
| sugerencia | 0.80 | 0.87 | 0.83 | 90 |

Acierto por fuente: amazon_es 71%, banking77 72%, cfpb 48%, datos_gov_contraloria_valle 91%, datos_gov_contraloria_villavicencio 85%, datos_gov_flandes 54%, datos_gov_mindeporte 55%

Umbral de confianza → cobertura / precisión: ≥0.5: 75% / 72%, ≥0.6: 55% / 80%, ≥0.7: 39% / 85%, ≥0.8: 23% / 94%, ≥0.9: 6% / 100%

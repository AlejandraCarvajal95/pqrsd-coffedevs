# Resumen normativo — Ley 1755 de 2015 (derecho de petición) y plazos de respuesta

**Documento:** normativa_ley_1755
**Propósito:** guía interna de Banco Andino Ficticio para calcular los vencimientos de las PQRSD.
**Aviso:** es un resumen interno para una demostración; no reemplaza el texto oficial de la ley. Antes de usarlo en una entidad real, debe verificarse contra el texto vigente.

## 1. Qué es la Ley 1755 de 2015

La Ley 1755 de 2015 regula el derecho fundamental de petición. Sustituyó el Título II del Código de Procedimiento Administrativo y de lo Contencioso Administrativo (Ley 1437 de 2011, CPACA). Reconoce que toda persona puede presentar peticiones respetuosas, por motivos de interés general o particular, y obtener una respuesta de fondo, clara, precisa y congruente.

Según el artículo 13, el derecho de petición comprende, entre otras, las solicitudes de información, las consultas, el examen y la copia de documentos, las quejas, los reclamos, las denuncias y la interposición de recursos. El artículo 32 permite ejercerlo también ante organizaciones privadas, en los casos que la ley señala.

## 2. Tabla de plazos para calcular el vencimiento

Esta tabla es la fuente para el motor de plazos. Los plazos se cuentan en **días hábiles**, a partir del día siguiente a la recepción.

| Clave de plazo | Tipo de solicitud | Plazo máximo de respuesta | Fundamento |
| --- | --- | --- | --- |
| `peticion_general` | Petición general | 15 días hábiles | Art. 14, regla general |
| `peticion_informacion` | Petición de documentos o de información | 10 días hábiles | Art. 14, numeral 1 |
| `consulta` | Consulta sobre materias a cargo de la entidad | 30 días hábiles | Art. 14, numeral 2 |
| `queja` | Queja | 15 días hábiles | Arts. 13 y 14, regla general |
| `reclamo` | Reclamo | 15 días hábiles | Arts. 13 y 14, regla general |
| `sugerencia` | Sugerencia | 15 días hábiles | Término general, por criterio del Banco (ver nota) |
| `denuncia` | Denuncia ante la entidad | 15 días hábiles | Arts. 13 y 14, regla general |

**Nota sobre sugerencias y denuncias.** La ley no fija un plazo propio para las sugerencias. El Banco les aplica el término general de 15 días hábiles por criterio interno. Una denuncia penal, disciplinaria o fiscal se presenta ante la autoridad competente y no se rige por estos plazos. En el Banco, una denuncia es el aviso de una posible irregularidad o fraude, y se responde en 15 días hábiles.

**Regla para la clasificación del plazo.** Si una solicitud mezcla varios tipos, se aplica el plazo del componente más corto, salvo que el área Jurídica indique otro.

## 3. Reglas de conteo

1. **Día de inicio:** el día de la radicación no se cuenta. El día 1 del plazo es el siguiente día hábil.
2. **Días hábiles:** lunes a viernes. No cuentan sábados, domingos ni festivos de Colombia.
3. **Radicación en día no hábil:** el Banco la considera recibida el siguiente día hábil (criterio interno).
4. **Vencimiento:** el último día del plazo es el día hábil número 15 (o 10, o 30), contado desde el día 1. La respuesta debe estar enviada a más tardar ese día.
5. **Festivos de Colombia, noviembre y diciembre de 2026:** 2 de noviembre (Todos los Santos), 16 de noviembre (Independencia de Cartagena), 8 de diciembre (Inmaculada Concepción) y 25 de diciembre (Navidad). La lista completa de festivos de 2026 y 2027 debe mantenerse como configuración.

### Ejemplo de cálculo con 15 días hábiles
PQRSD tipo queja radicada el martes 3 de noviembre de 2026.
- Día 1: miércoles 4 de noviembre.
- Días 1 a 3: 4, 5 y 6 de noviembre.
- Días 4 a 8: 9, 10, 11, 12 y 13 de noviembre.
- El lunes 16 de noviembre es festivo y no cuenta.
- Días 9 a 12: 17, 18, 19 y 20 de noviembre.
- Días 13 a 15: 23, 24 y 25 de noviembre.
- **Vencimiento: miércoles 25 de noviembre de 2026.**

### Ejemplo de cálculo con 10 días hábiles
Petición de información radicada el martes 3 de noviembre de 2026.
- Días 1 a 3: 4, 5 y 6 de noviembre.
- Días 4 a 8: 9, 10, 11, 12 y 13 de noviembre.
- Días 9 y 10: 17 y 18 de noviembre.
- **Vencimiento: miércoles 18 de noviembre de 2026.**

## 4. Casos especiales

### 4.1 Prórroga por imposibilidad de responder a tiempo
Si no es posible responder dentro del plazo, la entidad debe informar al peticionario **antes de que venza el plazo**, explicar los motivos y señalar una fecha razonable de respuesta. Esa nueva fecha no puede exceder el **doble del plazo inicial** (art. 14, parágrafo).

| Plazo inicial | Máximo con prórroga |
| --- | --- |
| 10 días hábiles | 20 días hábiles |
| 15 días hábiles | 30 días hábiles |
| 30 días hábiles | 60 días hábiles |

### 4.2 Silencio en solicitudes de documentos o información
Si la entidad no responde una petición de documentos o información dentro de los 10 días, se entiende aceptada la solicitud y debe entregar los documentos dentro de los 3 días siguientes (art. 14, parágrafo 1).

### 4.3 Falta de competencia
Si la entidad no es competente, debe informarlo al peticionario dentro de los 5 días siguientes a la recepción y trasladar la solicitud a la entidad competente (art. 21).

### 4.4 Solicitud incompleta
Si la solicitud está incompleta, la entidad debe pedir al peticionario que la complete dentro de los 10 días siguientes a la radicación. Si el peticionario no lo hace en el plazo de un mes, se entiende que desistió, salvo que pida prórroga (art. 17). Mientras se espera la información, el plazo de respuesta se suspende.

### 4.5 Peticiones irrespetuosas, oscuras o reiterativas
Se pueden rechazar si no es posible identificar el objeto de la petición o si es irrespetuosa. La decisión debe ser motivada y notificada (art. 19). Si el peticionario repite una solicitud ya resuelta, la entidad puede remitirse a la respuesta anterior (art. 19).

## 5. Contenido mínimo de la respuesta

La respuesta debe ser de fondo, clara, precisa y congruente con lo solicitado. Para un borrador del Banco, esto implica:

1. Citar el radicado de la PQRSD.
2. Responder cada punto planteado por el cliente.
3. Indicar las fuentes de la ley o del Banco en que se apoya.
4. Señalar los recursos o las instancias a las que el cliente puede acudir, como el defensor del consumidor financiero o la Superintendencia Financiera de Colombia, cuando aplique.
5. Si no hay fuente que respalde una afirmación, decirlo y derivar el caso a una persona.

### 5.1 Estructura de la respuesta
Toda respuesta del Banco a una PQRSD sigue este orden:

1. **Identificación:** nombre del Banco, área que responde y funcionario responsable.
2. **Radicado** de la PQRSD y fecha de recepción.
3. **Análisis de la solicitud:** qué pidió o planteó el cliente, en sus propios términos.
4. **Respuesta sustentada:** los hechos verificados y las fuentes que la respaldan (contrato, política del Banco o ley).
5. **Decisión expresa:** se concede, se niega, se explica o se orienta. Si se niega, se dice por qué.
6. **Recursos e instancias:** a dónde puede acudir el cliente si no queda conforme.
7. **Firma** del funcionario competente.

Fuente: guía "Cómo deben responder las entidades públicas las PQRSD en Colombia", Politécnico Colombiano Jaime Isaza Cadavid, adaptada al Banco. El derecho de petición también se ejerce ante particulares (Ley 1755 de 2015, art. 32).

### 5.2 Principios de la respuesta
- **Gratuidad:** responder una PQRSD no tiene costo para el cliente.
- **Legalidad:** no se exigen requisitos ni documentos distintos a los que pide la ley o el contrato.
- **Lenguaje claro:** frases cortas, sin tecnicismos innecesarios y con trato respetuoso.
- **Accesibilidad:** se atiende sin discriminación y se ajusta la comunicación a quien la necesite.
- **Medio solicitado:** se responde por el canal que el cliente pidió, cuando sea posible.

### 5.3 Errores que el Banco evita
1. Respuestas genéricas que no se refieren al caso concreto.
2. Comunicaciones de trámite ("recibimos su solicitud") que no resuelven lo pedido. Un acuse de recibo no cuenta como respuesta.
3. Omitir los recursos o las instancias a las que puede acudir el cliente.
4. Exigir documentos innecesarios o que el Banco ya tiene.
5. Responder fuera del plazo legal sin justificación ni aviso de prórroga.

## 6. Regulación complementaria para el sector financiero

- **Ley 1328 de 2009:** régimen de protección al consumidor financiero, incluido el defensor del consumidor financiero.
- **Ley 1266 de 2008, modificada por la Ley 2157 de 2021:** protección de datos financieros y reportes en centrales de riesgo, que exige una comunicación previa al titular antes de un reporte negativo. Esta ley tiene sus propios términos para consultas y reclamos de datos, que deben verificarse en su texto antes de aplicarlos.
- **Ley 1581 de 2012:** protección general de datos personales.

## 7. Alcance y límites de este resumen

1. Este resumen no cita jurisprudencia ni circulares específicas de la Superintendencia Financiera.
2. Los plazos de la tabla de la sección 2 provienen de la Ley 1755 de 2015, art. 14. Para sugerencias y denuncias, el Banco aplica el término general por criterio interno.
3. Si una pregunta no está cubierta por este resumen, la respuesta debe decir que no hay fundamento disponible y derivar el caso al área Jurídica.

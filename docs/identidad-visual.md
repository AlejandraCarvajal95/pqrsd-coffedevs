# PQRSD Coffee Devs — Identidad visual

> Ventanilla de radicación en un taller técnico. Papel blanco cálido, capas translúcidas de solicitudes apiladas y un solo control menta encendido marcan la dirección visual.

**Tema:** claro

Los tokens de este documento están implementados en [`frontend/src/styles/identidad.css`](../frontend/src/styles/identidad.css). Si cambias un valor aquí, cámbialo también allá.

PQRSD Coffee Devs: el ciudadano radica en un espacio de trabajo claro y ordenado. La interfaz es un lienzo blanco cálido interrumpido por paneles grafito, con menta y lima como señales operativas puntuales, no como decoración de fondo. Los titulares grandes y de tracking apretado dan una voz compacta y decidida; la navegación y los textos de apoyo en Inter mantienen tranquilo el resto del sistema. Los diagramas del flujo (radicación → clasificación → borrador → revisión) flotan como hojas técnicas blancas con líneas de construcción grises y tenues, mientras las tarjetas oscuras enmarcan detalles de implementación, radicados y estados.

## Tokens — Colores

Los neutros usan una escala piedra (gris con un toque cálido, en vez del zinc frío) para darle a la marca un tono de café sin perder sobriedad.

| Nombre | Valor | Token | Uso |
|--------|-------|-------|-----|
| Papel | `#fffdfa` | `--color-papel` | Fondos de página, tarjetas claras, navegación y texto claro sobre paneles grafito |
| Tinta | `#1c1917` | `--color-tinta` | Titulares, texto principal, logo, franjas oscuras e íconos de alto contraste |
| Grafito | `#292524` | `--color-grafito` | Tarjetas oscuras, paneles de código, botones utilitarios oscuros y demostraciones del producto |
| Nube | `#f5f5f4` | `--color-nube` | Superficies de sección atenuadas y fondos pálidos de tarjetas técnicas |
| Acero | `#d6d3d1` | `--color-acero` | Separadores finos, contornos de diagramas y bordes discretos |
| Pizarra | `#78716c` | `--color-pizarra` | Etiquetas de navegación, texto de apoyo, pestañas inactivas e íconos secundarios |
| Carbón | `#44403c` | `--color-carbon` | Texto enfatizado y etiquetas explicativas densas |
| Menta Señal | `#8ff5dc` | `--color-menta-senal` | Botones de acción principal (radicar), marcadores seleccionados y pequeños realces en diagramas: la señal fría que hace que el flujo se sienta vivo |
| Lima Aviso | `#dff39b` | `--color-lima-aviso` | Franjas de anuncio a todo el ancho y controles promocionales ligeros |
| Lima Voltio | `#c8ef5a` | `--color-lima-voltio` | Botones de la ruta técnica/documentación y realces compactos |
| Barrido Señal | `linear-gradient(90deg, #10c9b4 52%, #a8e01c 100%)` | `--gradiente-barrido-senal` | Acento horizontal escaso para líneas de conexión y trayectos del flujo |

### Colores semánticos

No son parte de la marca: existen para que los estados se lean bien.

| Nombre | Valor | Token | Uso |
|--------|-------|-------|-----|
| Niebla | `#a8a29e` | `--color-niebla` | Texto secundario sobre Tinta y Grafito (contraste 6.9:1 y 6.0:1) |
| Alerta | `#b42318` | `--color-alerta` | Errores de formulario y sistema sin conexión, siempre con texto |
| Alerta fondo | `#fdeceb` | `--color-alerta-fondo` | Fondo de los avisos de error |
| En línea | `#0f766e` | `--color-en-linea` | Marca de sistema en línea y etiquetas de fuente `[F1]` del chat |

Pizarra sobre Nube da 4.4:1 y no alcanza para texto normal: sobre Nube se usa Carbón.

## Cómo se aplicó en el frontend

- El texto de lectura del ciudadano va a 16px (token `--texto-lectura`); los 14px quedan para navegación, botones y etiquetas.
- El titular de portada llega a 72px, no a 80, y usa interlineado 0.92: con 0.8 se recortan tildes y descendentes en español.
- Los botones mantienen el relleno compacto pero nunca miden menos de 44px de alto, para poder tocarlos con el dedo.
- El tema es claro y fijo, como define esta guía; no hay modo oscuro.
- Animaciones: entrada del titular y del diagrama, ruta que se dibuja al hacer scroll, mensajes del chat, radicado que cae letra por letra y riel de etapas. Todas se apagan con `prefers-reduced-motion`.

## Tokens — Tipografía

Todas las familias están en Google Fonts (gratuitas).

### Inter Tight — display · `--fuente-display`
- **Alternativas:** Arial Narrow, Helvetica Neue
- **Pesos:** 400, 500, 700
- **Tamaños:** 32px, 56px, 64px, 80px
- **Interlineado:** 0.80, 0.90, 1.00, 1.20
- **Tracking:** -3.2px a 80px; -2.24px a 56px; -0.96px a 32px
- **Uso:** titulares de portada y de sección. El tracking de -0.04em y el interlineado de 0.8 a 80px aprietan las palabras en una voz densa, no en un titular editorial espacioso. El peso 700 a 32px (tracking -0.32px) queda para encabezados de característica que necesitan una silueta más firme.

### Inter — interfaz · `--fuente-interfaz`
- **Alternativas:** system-ui, Arial, sans-serif
- **Pesos:** 500, 600, 700
- **Tamaños:** 14px, 16px, 18px, 24px, 32px
- **Interlineado:** 1.00, 1.14, 1.20, 1.30, 1.40, 1.50
- **Tracking:** -1.28px a 32px; -0.32px a 16px; -0.14px a 14px
- **Uso:** navegación, botones, etiquetas, texto corrido y citas grandes. A 14px es compacta y firme; a 32px funciona como cita suave y de bajo contraste sobre paneles oscuros.

### Chivo Mono — etiquetas técnicas · `--fuente-mono`
- **Alternativas:** IBM Plex Mono, ui-monospace, monospace
- **Pesos:** 400
- **Tamaños:** 14px
- **Interlineado:** 1.50
- **Uso:** metadatos técnicos, números de radicado (`PQRSD-2026-XXXXXX`), fechas de vencimiento y detalles de implementación.

### Kode Mono — código · `--fuente-codigo`
- **Alternativas:** JetBrains Mono, ui-monospace, monospace
- **Pesos:** 400, 600
- **Tamaños:** 8px, 12px, 14px, 16px
- **Interlineado:** 0.90, 1.00, 1.20
- **Tracking:** -0.32px a 16px; 0.24px a 12px
- **Uso:** fragmentos de código y anotaciones diminutas en diagramas.

### Escala tipográfica

| Rol | Familia | Peso | Tamaño | Interlineado | Tracking | Token |
|-----|---------|------|--------|--------------|----------|-------|
| navegación | Inter | 500 | 14px | 1 | 0px | `--texto-nav` |
| cuerpo | Inter | 500 | 14px | 1.4 | -0.098px | `--texto-cuerpo` |
| cuerpo compacto | Inter | 500 | 14px | 1.14 | -0.14px | `--texto-cuerpo-compacto` |
| botón | Inter | 500 | 14px | 1 | -0.14px | `--texto-boton` |
| etiqueta técnica | Chivo Mono | 400 | 14px | 1.5 | 0px | `--texto-etiqueta-tecnica` |
| encabezado de característica | Inter Tight | 500 | 32px | 1.2 | -0.96px | `--texto-encabezado` |
| cita | Inter | 500 | 32px | 1.3 | -1.28px | `--texto-cita` |
| display de sección | Inter Tight | 400 | 56px | 1 | -2.24px | `--texto-display-seccion` |
| display de sección inverso | Inter Tight | 500 | 56px | 1 | -2.24px | `--texto-display-seccion` |
| display de portada | Inter Tight | 400 | 80px | 0.8 | -3.2px | `--texto-display-portada` |

## Tokens — Espaciado y formas

**Densidad:** compacta

### Escala de espaciado

`4, 8, 10, 12, 16, 22, 24, 30, 32, 40, 48, 56, 72, 88, 112, 120` px → tokens `--espacio-4` … `--espacio-120`.

### Radios

| Elemento | Valor |
|----------|-------|
| tarjetas | 16px |
| enlaces | 4px |
| píldoras | 1000px |
| imágenes | 1000px |
| botones | 12px |

### Sombras

| Nombre | Valor | Token |
|--------|-------|-------|
| sutil | `rgba(255, 255, 255, 0.13) 0 0 0 2px inset` | `--sombra-sutil` |
| sutil 2 | `rgba(255, 255, 255, 0.03) 0 0 0 1px inset` | `--sombra-sutil-2` |

### Diseño

- **Espacio entre secciones:** 40px
- **Relleno de tarjeta:** 16px
- **Espacio entre elementos:** 8px

## Componentes

### Franja de aviso lima
**Uso:** aviso general sobre la navegación (por ejemplo, horario de atención o plazos legales).

Barra a todo el ancho en `#dff39b`, esquinas rectas, relleno de 8px vertical y 16px horizontal. Mensaje en Inter 500 14px/21px, `#1c1917` al 80 % de opacidad, centrado en una sola línea.

### Barra de navegación
**Uso:** navegación superior con logo, grupos de enlaces y controles de acción.

Fondo `#fffdfa` con etiquetas Inter 500 14px en `#78716c`; 16px entre controles y 24px entre grupos. Logo e íconos en `#1c1917`; radio de 4px solo para el foco de enlaces pequeños. Se separa del contenido oscuro siguiente con una línea de 1px `#d6d3d1`.

### Botón grafito de cabecera
**Uso:** acción compacta de alta jerarquía en la navegación (p. ej. "Consultar estado").

Relleno `#292524`, texto blanco Inter 500 14px, radio 12px, relleno 8px 16px. Borde interior: `0 0 0 2px rgba(255, 255, 255, 0.13) inset`.

### Botón menta de acción principal
**Uso:** acción principal en secciones claras (p. ej. "Radicar PQRSD").

Relleno `#8ff5dc`, texto `#1c1917` Inter 500 14px, radio 16px, relleno 12px 16px 12px 22px. 8px entre la etiqueta y la flecha.

### Botón secundario translúcido
**Uso:** acción secundaria sobre superficies oscuras.

Relleno `rgba(255, 255, 255, 0.1)`, texto blanco Inter 500 14px, radio 16px, relleno 12px 22px. Usar `0 0 0 2px rgba(255, 255, 255, 0.13) inset` en vez de un borde opaco.

### Botón lima de documentación
**Uso:** ruta técnica (documentación, API, panel del equipo).

Relleno `#c8ef5a`, texto `#1c1917` Inter 500 14px, radio 12px, relleno 8px 16px. No usarlo como acción principal del ciudadano.

### Fila de capacidades
**Uso:** lista de puntos clave bajo el texto de portada.

Tres elementos en fila con 16px de separación. Cada etiqueta lleva un ícono en mosaico oscuro de 12px; texto Inter 500 14px en `#1c1917`, 8px entre ícono y etiqueta.

### Fila de filtros por tipo
**Uso:** selector de categoría (Petición, Queja, Reclamo, Sugerencia, Denuncia).

Etiquetas Inter 500 14px con 16px de separación y 8px entre ícono y etiqueta. El elemento seleccionado lleva un pequeño mosaico relleno `#8ff5dc`; los no seleccionados van en `#78716c`.

### Diagrama del flujo en capas
**Uso:** visual de portada y de características para explicar el recorrido de una PQRSD.

Hojas superpuestas en `#fffdfa` y `#f5f5f4` con esquinas de 16px, contornos finos `#d6d3d1` y etiquetas técnicas escasas. Un mosaico central `#292524` flota sobre las hojas; `#8ff5dc` y `#c8ef5a` solo como señales diminutas de ruta o ícono.

### Tarjeta nube
**Uso:** vista previa clara de un paso del flujo.

Fondo `#f5f5f4`, radio 16px y la elevación "Tarjeta nube". Sin relleno en el marco exterior; las capas visuales van de borde a borde dentro del marco redondeado.

### Tarjeta grafito de código
**Uso:** vista de implementación o bloque técnico oscuro.

Fondo `#292524`, radio 16px y la elevación "Tarjeta grafito". Código en Chivo Mono o Kode Mono 14px/21px; blanco para la sintaxis base y colores de sintaxis solo dentro del código.

### Panel inverso de testimonio
**Uso:** sección oscura de prueba social o casos de uso.

Franja `#1c1917` con titular blanco Inter Tight 56px y cita Inter 500 32px/41.6px en `rgba(255, 255, 255, 0.5)`. Las tarjetas dentro de la franja van en `#292524` con radio 16px.

## Sí y no

### Sí
- Usar `#fffdfa` como lienzo por defecto y `#1c1917` para todos los titulares grandes en tema claro.
- Poner el titular de portada en Inter Tight 80px/64px, peso 400, tracking -3.2px.
- Poner los titulares de sección en Inter Tight 56px/56px, tracking -2.24px.
- Usar `#8ff5dc` solo para acciones principales, marcadores seleccionados y pequeños acentos de ruta.
- Radio de 16px para tarjetas y botones grandes (menta o translúcidos).
- Radio de 12px con relleno 8px 16px para botones compactos (`#292524` y `#c8ef5a`).
- Construir el ritmo de la interfaz con separaciones de 4, 8, 16, 24 y 32px.

### No
- No usar `#8ff5dc` como fondo de página ni de secciones amplias.
- No redondear tarjetas más de 16px ni convertir todos los controles en píldoras de 1000px.
- No usar `#c8ef5a` para la acción principal del ciudadano; dejarlo para la ruta técnica.
- No poner titulares display en Inter; reservar Inter Tight para la escala de 32, 56 y 80px.
- No aflojar el tracking de los titulares; mantenerlo entre -0.96px y -3.2px.
- No reemplazar las líneas finas `#d6d3d1` por bordes gruesos.
- No poner color saturado en el texto corrido, la navegación ni superficies amplias.

## Superficies

| Nivel | Nombre | Valor | Uso |
|-------|--------|-------|-----|
| 0 | Lienzo papel | `#fffdfa` | Página, cabecera, portada y zonas claras |
| 1 | Superficie nube | `#f5f5f4` | Tarjetas atenuadas y superficies técnicas alternas |
| 2 | Panel grafito | `#292524` | Bloques de código, tarjetas oscuras y detalle del producto |
| 3 | Franja tinta | `#1c1917` | Transiciones oscuras a todo el ancho y secciones inversas |

## Elevación

- **Tarjeta nube:** `0 0 0 1px rgba(0,0,0,0.08), 0 0.6px 2.29px -1.25px rgba(0,0,0,0.18), 0 2.29px 8.7px -2.5px rgba(0,0,0,0.16), 0 10px 38px -3.75px rgba(0,0,0,0.06)`
- **Tarjeta grafito:** `0 0.6px 2.53px -1.25px rgba(0,0,0,0.18), 0 2.29px 9.61px -2.5px rgba(0,0,0,0.16), 0 10px 42px -3.75px rgba(0,0,0,0.06)`
- **Tarjeta técnica blanca:** `0 2.77px 2.21px rgba(0,0,0,0.02), 0 6.65px 5.32px rgba(0,0,0,0.03)`

## Imágenes

Ilustraciones contenidas del producto, no fotografías: hojas técnicas blancas o gris pálido superpuestas en ángulos leves, con bordes de línea de construcción y sombras suaves. Un mosaico oscuro central (el radicado), pequeñas ventanas de chat o formulario, líneas finas de ruta e íconos mínimos explican el flujo sin volverse arte a sangre. Los íconos son glifos compactos, casi siempre monocromos y oscuros, con mosaicos menta ocasionales. Las imágenes ocupan un lado de las composiciones divididas; el texto sigue siendo la masa dominante.

## Composición

Una franja lima estrecha sobre una navegación blanca con el logo a la izquierda, grupos de enlaces al centro y los controles de acción a la derecha. La portada usa dos columnas asimétricas: a la izquierda, titular grande, texto de apoyo, fila de capacidades y acciones; a la derecha, el diagrama del flujo en capas. Un divisor grafito a todo el ancho da paso a secciones editoriales alineadas a la izquierda: introducciones con título grande, texto explicativo dividido y fila de filtros por tipo, seguidas de bloques de características que alternan texto y tarjetas de código o diagrama superpuestas. Fuera de los visuales técnicos domina el texto, con amplios campos blancos entre secciones y espaciado interno denso, en múltiplos de 8px.

## Guía rápida para prompts

Colores:
- Papel `#fffdfa` · Tinta `#1c1917` · Grafito `#292524` · Nube `#f5f5f4` · Acero `#d6d3d1` · Pizarra `#78716c` · Carbón `#44403c`
- Menta Señal `#8ff5dc` · Lima Aviso `#dff39b` · Lima Voltio `#c8ef5a`
- Barrido Señal `linear-gradient(90deg, #10c9b4 52%, #a8e01c 100%)`

Ejemplos:
- Portada blanca a dos columnas: a la izquierda, titular `#1c1917` en Inter Tight 80px/64px peso 400 con tracking -3.2px, texto de apoyo Inter 14px en `#78716c` y botón menta `#8ff5dc` "Radicar PQRSD" con radio 16px; a la derecha, diagrama del flujo en capas `#fffdfa` y `#f5f5f4` con contornos `#d6d3d1`.
- Sección de implementación sobre `#1c1917` con titular blanco Inter Tight 56px/56px peso 500, tarjeta de código `#292524` de radio 16px y etiquetas Chivo Mono 14px/21px.
- Introducción por tipo de PQRSD sobre `#fffdfa` con titular Inter Tight 56px/56px peso 400 `#1c1917`, párrafos divididos en `#44403c` y `#78716c`, y fila de filtros Inter 14px cuyo mosaico seleccionado es `#8ff5dc`.
- Cabecera compacta bajo una franja `#dff39b`: navegación Inter 14px `#78716c`, botón `#292524` de radio 12px con texto blanco y fondo `#fffdfa`.

// Íconos propios, dibujados para este portal: trazo recto y esquinas vivas,
// a juego con las líneas de construcción de la identidad visual.

const BASE = {
  width: 16,
  height: 16,
  viewBox: '0 0 16 16',
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 1.5,
  strokeLinecap: 'square',
  'aria-hidden': true,
  focusable: false,
}

// Logo: una hoja de solicitud, la ficha oscura del radicado encima y la marca
// menta de "recibida". Es el mismo motivo del diagrama de portada, reducido.
// El mismo dibujo está en public/logo.svg para el ícono de la pestaña.
export function Logo({ tamano = 28 }) {
  return (
    <svg className="logo" width={tamano} height={tamano} viewBox="0 0 28 28" aria-hidden="true" focusable="false">
      <rect className="logo__hoja" x="3" y="3" width="17" height="17" rx="4" />
      <rect className="logo__ficha" x="9" y="9" width="16" height="16" rx="4" />
      <rect className="logo__marca" x="13" y="17" width="4" height="4" rx="1" />
    </svg>
  )
}

export function IconoFlecha(props) {
  return (
    <svg {...BASE} className="icono-flecha" {...props}>
      <path d="M2.5 8h10M8.5 3.5 13 8l-4.5 4.5" />
    </svg>
  )
}

export function IconoCheck(props) {
  return (
    <svg {...BASE} {...props}>
      <path d="m3 8.5 3.2 3L13 4.5" />
    </svg>
  )
}

export function IconoCopiar(props) {
  return (
    <svg {...BASE} {...props}>
      <path d="M5.5 5.5h8v8h-8z" />
      <path d="M10.5 5.5v-3h-8v8h3" />
    </svg>
  )
}

export function IconoAlerta(props) {
  return (
    <svg {...BASE} {...props}>
      <path d="M8 2 14.5 13.5h-13z" />
      <path d="M8 6.5v3.2M8 11.6v.2" />
    </svg>
  )
}

export function IconoEnviar(props) {
  return (
    <svg {...BASE} {...props}>
      <path d="M8 13V3M3.5 7.5 8 3l4.5 4.5" />
    </svg>
  )
}

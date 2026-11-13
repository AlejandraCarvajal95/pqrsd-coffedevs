import { textoDeDias } from '../utils/formato.js'

// Semáforo de vencimiento (US-017). No depende solo del color: cada estado
// tiene su forma (círculo, triángulo, cuadrado) y su texto.

const NOMBRES = { verde: 'A tiempo', amarillo: 'Por vencer', rojo: 'Urgente' }

function Forma({ color }) {
  if (color === 'amarillo') {
    return (
      <svg viewBox="0 0 12 12" width="12" height="12" aria-hidden="true">
        <path d="M6 1 11.5 11H.5Z" fill="currentColor" />
      </svg>
    )
  }
  if (color === 'rojo') {
    return (
      <svg viewBox="0 0 12 12" width="12" height="12" aria-hidden="true">
        <rect x="1.5" y="1.5" width="9" height="9" rx="1.5" fill="currentColor" />
      </svg>
    )
  }
  return (
    <svg viewBox="0 0 12 12" width="12" height="12" aria-hidden="true">
      <circle cx="6" cy="6" r="5" fill="currentColor" />
    </svg>
  )
}

export default function Semaforo({ item, compacto = false }) {
  if (!item.semaforo) {
    return <span className="semaforo" data-color="ninguno">Sin plazo</span>
  }
  const nombre = item.vencida ? 'Vencida' : NOMBRES[item.semaforo]
  return (
    <span className="semaforo" data-color={item.semaforo}>
      <Forma color={item.semaforo} />
      <span>
        <strong>{nombre}</strong>
        {!compacto && <span className="semaforo__dias"> · {textoDeDias(item)}</span>}
      </span>
    </span>
  )
}

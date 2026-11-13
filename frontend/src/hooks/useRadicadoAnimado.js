import { useEffect, useState } from 'react'
import { prefiereMenosMovimiento } from './useEnVista.js'

// Mismo alfabeto del backend: sin 0/O ni 1/I/L.
const ALFABETO = 'ABCDEFGHJKMNPQRSTUVWXYZ23456789'

function azar() {
  return ALFABETO[Math.floor(Math.random() * ALFABETO.length)]
}

// Muestra el sufijo del radicado "sorteándose" y lo fija letra por letra.
// Refleja que el radicado real es aleatorio y no consecutivo.
export function useRadicadoAnimado(sufijo, activo) {
  const [texto, setTexto] = useState(sufijo)

  useEffect(() => {
    if (!activo || prefiereMenosMovimiento()) {
      setTexto(sufijo)
      return undefined
    }
    let paso = 0
    const PASOS_POR_LETRA = 5
    const total = sufijo.length * PASOS_POR_LETRA
    const intervalo = setInterval(() => {
      paso += 1
      const fijas = Math.floor(paso / PASOS_POR_LETRA)
      setTexto(
        sufijo
          .split('')
          .map((letra, i) => (i < fijas ? letra : azar()))
          .join(''),
      )
      if (paso >= total) clearInterval(intervalo)
    }, 45)
    return () => clearInterval(intervalo)
  }, [sufijo, activo])

  return texto
}

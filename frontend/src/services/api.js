// Cliente HTTP del frontend. Siempre usa la ruta relativa /api:
// nginx la reenvía al backend, así no hay URLs ni puertos escritos a mano.
const BASE_API = '/api'

export async function solicitar(ruta, opciones = {}) {
  const respuesta = await fetch(`${BASE_API}${ruta}`, {
    ...opciones,
    headers: {
      'Content-Type': 'application/json',
      ...(opciones.headers || {}),
    },
  })
  if (!respuesta.ok) {
    throw new Error(`HTTP ${respuesta.status} en ${ruta}`)
  }
  return respuesta.json()
}

export function obtenerSalud() {
  return solicitar('/health')
}

// Cliente HTTP del frontend. Siempre usa la ruta relativa /api:
// nginx la reenvía al backend, así no hay URLs ni puertos escritos a mano.
const BASE_API = '/api'

export class ErrorApi extends Error {
  constructor(mensaje, estado) {
    super(mensaje)
    this.estado = estado
  }
}

export async function solicitar(ruta, opciones = {}) {
  const respuesta = await fetch(`${BASE_API}${ruta}`, {
    ...opciones,
    headers: {
      'Content-Type': 'application/json',
      ...(opciones.headers || {}),
    },
  })
  if (!respuesta.ok) {
    // El backend devuelve {"detail": "mensaje en español"} en sus errores.
    let mensaje = `Error ${respuesta.status} al consultar el servidor.`
    try {
      const cuerpo = await respuesta.json()
      if (typeof cuerpo.detail === 'string') mensaje = cuerpo.detail
    } catch {
      // La respuesta no era JSON: se deja el mensaje genérico.
    }
    throw new ErrorApi(mensaje, respuesta.status)
  }
  return respuesta.json()
}

function enviar(ruta, cuerpo) {
  return solicitar(ruta, { method: 'POST', body: JSON.stringify(cuerpo) })
}

export function obtenerSalud() {
  return solicitar('/health')
}

// --- Chat de desvío (US-009) ---

export function consultarChat(sesionId, mensaje) {
  return enviar('/chat/consulta', { sesion_id: sesionId, mensaje })
}

export function registrarResultadoChat(sesionId, resolvio) {
  return enviar('/chat/resultado', { sesion_id: sesionId, resolvio })
}

export function continuarConPqrsd(sesionId) {
  return enviar('/chat/continuar', { sesion_id: sesionId })
}

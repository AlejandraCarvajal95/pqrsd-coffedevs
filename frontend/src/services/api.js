// Cliente HTTP del frontend. Siempre usa la ruta relativa /api:
// nginx la reenvía al backend, así no hay URLs ni puertos escritos a mano.
const BASE_API = '/api'

export class ErrorApi extends Error {
  constructor(mensaje, estado, campos = []) {
    super(mensaje)
    this.estado = estado
    this.campos = campos // en errores 422: nombres de los campos inválidos
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
    let campos = []
    try {
      const cuerpo = await respuesta.json()
      if (typeof cuerpo.detail === 'string') mensaje = cuerpo.detail
      if (Array.isArray(cuerpo.campos)) campos = cuerpo.campos
    } catch {
      // La respuesta no era JSON: se deja el mensaje genérico.
    }
    throw new ErrorApi(mensaje, respuesta.status, campos)
  }
  return respuesta.json()
}

function enviar(ruta, cuerpo) {
  return solicitar(ruta, { method: 'POST', body: JSON.stringify(cuerpo) })
}

export function obtenerSalud() {
  return solicitar('/health')
}

// --- Radicación (US-007) ---

export function radicarPqrsd(datos) {
  return enviar('/pqrsd', datos)
}

// --- Estado de una PQRSD (US-010) ---

export function consultarEstado(radicado) {
  return solicitar(`/pqrsd/${encodeURIComponent(radicado.trim())}`)
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

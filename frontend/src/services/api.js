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
  let respuesta
  try {
    respuesta = await fetch(`${BASE_API}${ruta}`, {
      ...opciones,
      headers: {
        'Content-Type': 'application/json',
        ...(opciones.headers || {}),
      },
    })
  } catch {
    // fetch solo falla así cuando no hay conexión con el servidor ("Failed to fetch").
    throw new ErrorApi(
      'No pudimos conectarnos con el servidor. Revise su conexión e intente de nuevo; sus datos siguen en el formulario.',
      0,
    )
  }
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

// --- Chat de radicación (US-008) ---

export function enviarMensajeRadicacion(sesionId, mensaje) {
  return enviar('/chat/radicacion/mensaje', { sesion_id: sesionId, mensaje })
}

export function confirmarRadicacionChat(sesionId) {
  return enviar('/chat/radicacion/confirmar', { sesion_id: sesionId })
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

// --- Panel administrativo (US-017, US-019, US-020, US-022) ---
// El token vive en sessionStorage: se borra al cerrar la pestaña.

const CLAVE_TOKEN = 'pqrsd_admin_token'

export function tokenAdmin() {
  try {
    return sessionStorage.getItem(CLAVE_TOKEN)
  } catch {
    return null
  }
}

export function cerrarSesionAdmin() {
  try {
    sessionStorage.removeItem(CLAVE_TOKEN)
  } catch {
    // Sin almacenamiento disponible no hay nada que borrar.
  }
}

export function obtenerModoAdmin() {
  return solicitar('/admin/modo')
}

export async function iniciarSesionAdmin(usuario, clave) {
  const datos = await enviar('/admin/login', { usuario, clave })
  sessionStorage.setItem(CLAVE_TOKEN, datos.token)
  return datos
}

async function solicitarAdmin(ruta, opciones = {}) {
  try {
    return await solicitar(ruta, {
      ...opciones,
      headers: { ...(opciones.headers || {}), Authorization: `Bearer ${tokenAdmin() || ''}` },
    })
  } catch (error) {
    // 401: la sesión venció o no existe. La página redirige al acceso.
    if (error.estado === 401) cerrarSesionAdmin()
    throw error
  }
}

export function listarBandeja(filtros = {}) {
  const parametros = new URLSearchParams()
  for (const [clave, valor] of Object.entries(filtros)) {
    if (valor !== '' && valor !== null && valor !== undefined) parametros.set(clave, valor)
  }
  const consulta = parametros.toString()
  return solicitarAdmin(`/bandeja${consulta ? `?${consulta}` : ''}`)
}

export function obtenerMetricas() {
  return solicitarAdmin('/metricas')
}

export function obtenerDetalleAdmin(radicado) {
  return solicitarAdmin(`/bandeja/${encodeURIComponent(radicado)}`)
}

export function confirmarClasificacion(radicado, tipo, area) {
  return solicitarAdmin(`/bandeja/${encodeURIComponent(radicado)}/clasificacion`, {
    method: 'PATCH',
    body: JSON.stringify({ tipo, area }),
  })
}

export function pedirBorrador(radicado) {
  return solicitarAdmin(`/bandeja/${encodeURIComponent(radicado)}/borrador/generar`, {
    method: 'POST',
  })
}

export function guardarBorrador(radicado, texto) {
  return solicitarAdmin(`/bandeja/${encodeURIComponent(radicado)}/borrador`, {
    method: 'PUT',
    body: JSON.stringify({ texto }),
  })
}

export function aprobarRespuesta(radicado, texto) {
  return solicitarAdmin(`/bandeja/${encodeURIComponent(radicado)}/aprobar`, {
    method: 'POST',
    body: JSON.stringify({ texto }),
  })
}

// Descarga el CSV con la sesión del panel (un enlace directo no llevaría el token).
export async function descargarCsv() {
  let respuesta
  try {
    respuesta = await fetch(`${BASE_API}/bandeja/exportar/csv`, {
      headers: { Authorization: `Bearer ${tokenAdmin() || ''}` },
    })
  } catch {
    throw new ErrorApi('No pudimos conectarnos con el servidor para descargar el archivo.', 0)
  }
  if (!respuesta.ok) {
    if (respuesta.status === 401) cerrarSesionAdmin()
    throw new ErrorApi('No se pudo descargar el archivo. Inicie sesión de nuevo.', respuesta.status)
  }
  const nombre =
    /filename="([^"]+)"/.exec(respuesta.headers.get('Content-Disposition') || '')?.[1] ||
    'pqrsd.csv'
  const enlace = document.createElement('a')
  enlace.href = URL.createObjectURL(await respuesta.blob())
  enlace.download = nombre
  document.body.appendChild(enlace)
  enlace.click()
  enlace.remove()
  URL.revokeObjectURL(enlace.href)
}

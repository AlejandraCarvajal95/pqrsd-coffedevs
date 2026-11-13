// Textos y formatos compartidos por las páginas del panel administrativo.

export const ETIQUETAS_ESTADO = {
  recibida: 'Recibida',
  clasificada: 'Clasificada, sin borrador',
  pendiente_revision_clasificacion: 'Revisar clasificación',
  asignada: 'Asignada',
  borrador_listo: 'Borrador listo',
  respondida: 'Respondida',
}

export const ETIQUETAS_TIPO = {
  peticion: 'Petición',
  queja: 'Queja',
  reclamo: 'Reclamo',
  sugerencia: 'Sugerencia',
  denuncia: 'Denuncia',
}

export const ETIQUETAS_MOTIVO = {
  tipo_discrepante: 'Los dos clasificadores proponen tipos distintos.',
  baja_confianza: 'La clasificación automática tiene baja confianza.',
  posible_fuera_de_competencia: 'Puede no ser competencia del banco (posible traslado).',
  claude_no_disponible: 'El clasificador no respondió; clasifíquela a mano.',
}

export const ETIQUETAS_ACCION = {
  editado: 'Editó el borrador',
  aprobado: 'Aprobó y envió la respuesta',
  rechazado: 'Rechazó el borrador',
  regenerado: 'Pidió un borrador nuevo',
}

export function etiquetaTipo(tipo) {
  return ETIQUETAS_TIPO[tipo] || 'Sin clasificar'
}

export function legible(valor) {
  // "cobros_comisiones_intereses" -> "Cobros comisiones intereses"
  if (!valor) return 'Sin dato'
  const texto = String(valor).replaceAll('_', ' ')
  return texto.charAt(0).toUpperCase() + texto.slice(1)
}

// Las fechas "AAAA-MM-DD" se arman a mano: new Date() las correría un día por la zona horaria.
export function fechaLocal(valor) {
  const [anio, mes, dia] = String(valor).slice(0, 10).split('-').map(Number)
  return new Date(anio, mes - 1, dia)
}

export function claveDeFecha(fecha) {
  const mes = String(fecha.getMonth() + 1).padStart(2, '0')
  const dia = String(fecha.getDate()).padStart(2, '0')
  return `${fecha.getFullYear()}-${mes}-${dia}`
}

export function formatearFecha(valor, opciones = { day: 'numeric', month: 'short', year: 'numeric' }) {
  if (!valor) return 'Sin fecha'
  return fechaLocal(valor).toLocaleDateString('es-CO', opciones)
}

export function formatearFechaHora(valor) {
  if (!valor) return 'Sin fecha'
  return new Date(valor).toLocaleString('es-CO', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  })
}

export function textoDeDias(item) {
  const dias = item.dias_habiles_restantes
  if (dias === null || dias === undefined) return 'Sin fecha de vencimiento'
  if (item.vencida) {
    return dias === 0 ? 'plazo cumplido' : `hace ${-dias} día${dias === -1 ? '' : 's'} hábil${dias === -1 ? '' : 'es'}`
  }
  if (dias === 0) return 'Vence hoy'
  return `${dias} día${dias === 1 ? '' : 's'} hábil${dias === 1 ? '' : 'es'}`
}

// Mismas reglas que el backend (bloqueos_de_aprobacion): nada interno llega al ciudadano.
export function bloqueosDeAprobacion(texto) {
  const bloqueos = []
  if (!texto.trim()) bloqueos.push('El texto de la respuesta está vacío.')
  if (texto.includes('[AVISO AUTOMÁTICO DEL SISTEMA]') || texto.includes('[FIN DEL AVISO]')) {
    bloqueos.push('Retire el aviso automático del sistema.')
  }
  if (texto.includes('[NOTA INTERNA')) bloqueos.push('Retire la nota interna para el analista.')
  if (texto.includes('[COMPLETAR')) bloqueos.push('Complete los campos marcados con [COMPLETAR: …].')
  if (texto.includes('[Nombre del funcionario]') || texto.includes('[Cargo]')) {
    bloqueos.push('Complete la firma: nombre y cargo de quien responde.')
  }
  return bloqueos
}

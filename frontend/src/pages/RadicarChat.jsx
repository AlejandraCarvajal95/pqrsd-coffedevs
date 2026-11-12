import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import FormularioPqrsd, { Confirmacion, estilosFormulario } from '../components/FormularioPqrsd.jsx'
import { confirmarRadicacionChat, enviarMensajeRadicacion } from '../services/api.js'

// Chat de radicación (US-008): el ciudadano cuenta su caso, el agente extrae los
// campos y pide los que faltan; al confirmar el resumen se radica la PQRSD con el
// mismo flujo del formulario. Si el chat se queda sin mensajes, se pasa al
// formulario ya llenado con lo reunido.

const MAX_CARACTERES = 1000

const SALUDO =
  'Hola, soy el asistente de radicación. Cuénteme con sus palabras qué ocurrió y yo armo su PQRSD. ' +
  'Use solo datos ficticios y no escriba su cédula, números de tarjeta ni claves.'

const PENDIENTES = {
  nombre_ciudadano: 'su nombre',
  contacto: 'un correo o teléfono de contacto',
  hechos: 'lo que ocurrió',
}

const estilos = {
  pagina: { fontFamily: 'system-ui, sans-serif', maxWidth: 720, margin: '2rem auto', padding: '0 1rem', color: '#1a1a1a' },
  historial: { display: 'flex', flexDirection: 'column', gap: '0.75rem', margin: '1rem 0', padding: 0, listStyle: 'none' },
  ciudadano: { alignSelf: 'flex-end', background: '#e8f0fe', borderRadius: 8, padding: '0.6rem 0.9rem', maxWidth: '85%', whiteSpace: 'pre-wrap' },
  asistente: { alignSelf: 'flex-start', background: '#f4f4f4', borderRadius: 8, padding: '0.6rem 0.9rem', maxWidth: '85%', whiteSpace: 'pre-wrap' },
  botonSecundario: { padding: '0.6rem 1.1rem', borderRadius: 6, border: '1px solid #1a4fa0', background: '#fff', color: '#1a4fa0', cursor: 'pointer', fontSize: '1rem', marginTop: '1rem', marginLeft: '0.5rem' },
  tarjeta: { border: '1px solid #ccc', borderRadius: 8, padding: '1rem', marginTop: '1rem' },
  nota: { fontSize: '0.85rem', color: '#555' },
  campo: estilosFormulario.campo,
}

function Resumen({ resumen }) {
  return (
    <dl style={{ margin: 0 }}>
      <dt style={{ fontWeight: 600 }}>Nombre</dt>
      <dd style={{ margin: '0 0 0.6rem' }}>{resumen.nombre_ciudadano}</dd>
      <dt style={{ fontWeight: 600 }}>Contacto</dt>
      <dd style={{ margin: '0 0 0.6rem' }}>{resumen.contacto}</dd>
      <dt style={{ fontWeight: 600 }}>Asunto</dt>
      <dd style={{ margin: '0 0 0.6rem' }}>{resumen.asunto}</dd>
      <dt style={{ fontWeight: 600 }}>Descripción</dt>
      <dd style={{ margin: 0, whiteSpace: 'pre-wrap' }}>{resumen.descripcion}</dd>
    </dl>
  )
}

export default function RadicarChat() {
  const [sesionId, setSesionId] = useState(null)
  const [mensajes, setMensajes] = useState([{ rol: 'asistente', texto: SALUDO }])
  const [texto, setTexto] = useState('')
  const [enviando, setEnviando] = useState(false)
  const [confirmando, setConfirmando] = useState(false)
  const [error, setError] = useState(null)
  const [estado, setEstado] = useState(null) // última respuesta del backend
  const [usarFormulario, setUsarFormulario] = useState(false)
  const [radicada, setRadicada] = useState(null)
  const finRef = useRef(null)

  useEffect(() => {
    finRef.current?.scrollIntoView?.({ behavior: 'smooth' })
  }, [mensajes, estado, radicada])

  const limiteAlcanzado = Boolean(estado?.limite_alcanzado)
  // Sin mensajes y con datos faltantes solo queda el formulario.
  const formularioObligado = limiteAlcanzado && !estado?.listo_para_confirmar
  const mostrarFormulario = !radicada && (usarFormulario || formularioObligado)
  const mostrarResumen = !radicada && !mostrarFormulario && estado?.listo_para_confirmar
  const puedeEscribir = !radicada && !limiteAlcanzado

  async function enviarMensaje(evento) {
    evento.preventDefault()
    const mensaje = texto.trim()
    if (!mensaje || enviando || !puedeEscribir) return
    setError(null)
    setEnviando(true)
    setMensajes((previos) => [...previos, { rol: 'ciudadano', texto: mensaje }])
    setTexto('')
    try {
      const datos = await enviarMensajeRadicacion(sesionId, mensaje)
      setSesionId(datos.sesion_id)
      setEstado(datos)
      setMensajes((previos) => [...previos, { rol: 'asistente', texto: datos.respuesta }])
    } catch (e) {
      setError(e.message)
    } finally {
      setEnviando(false)
    }
  }

  async function confirmar() {
    setError(null)
    setConfirmando(true)
    try {
      setRadicada(await confirmarRadicacionChat(sesionId))
    } catch (e) {
      setError(e.message)
    } finally {
      setConfirmando(false)
    }
  }

  const pendientes = (estado?.faltantes || []).map((campo) => PENDIENTES[campo] || campo)

  return (
    <main style={estilos.pagina}>
      <p><Link to="/">Inicio</Link> · <Link to="/radicar">Usar el formulario</Link> · <Link to="/estado">Consultar estado</Link></p>
      <h1 style={{ marginBottom: '0.25rem' }}>Radicar mi PQRSD con el asistente</h1>
      <p style={estilos.nota}>
        Cuente su caso en un chat y el asistente armará la PQRSD. Antes de radicar podrá revisar
        el resumen. Una persona del banco revisará y aprobará la respuesta.
      </p>

      <ol style={estilos.historial} aria-live="polite" aria-label="Conversación">
        {mensajes.map((mensaje, i) => (
          <li key={i} style={mensaje.rol === 'ciudadano' ? estilos.ciudadano : estilos.asistente}>
            <span style={{ position: 'absolute', left: -9999 }}>
              {mensaje.rol === 'ciudadano' ? 'Usted dijo:' : 'El asistente respondió:'}
            </span>
            {mensaje.texto}
          </li>
        ))}
        {enviando && <li style={estilos.asistente}>Escribiendo…</li>}
      </ol>

      {!radicada && estado && pendientes.length > 0 && !mostrarFormulario && (
        <p style={estilos.nota}>Todavía falta: {pendientes.join(', ')}.</p>
      )}

      {mostrarResumen && (
        <section style={estilos.tarjeta} aria-labelledby="titulo-resumen">
          <h2 id="titulo-resumen" style={{ marginTop: 0, fontSize: '1.15rem' }}>Resumen de su PQRSD</h2>
          <Resumen resumen={estado.resumen} />
          <button type="button" style={estilosFormulario.boton} onClick={confirmar} disabled={confirmando}>
            {confirmando ? 'Radicando…' : 'Confirmar y radicar'}
          </button>
          <button type="button" style={estilos.botonSecundario} onClick={() => setUsarFormulario(true)}>
            Ajustar en el formulario
          </button>
          <p style={estilos.nota}>
            Si algo no está bien, puede seguir escribiendo en el chat para corregirlo.
          </p>
        </section>
      )}

      {mostrarFormulario && (
        <section style={estilos.tarjeta} aria-labelledby="titulo-formulario">
          <h2 id="titulo-formulario" style={{ marginTop: 0, fontSize: '1.15rem' }}>Complete su PQRSD en el formulario</h2>
          <FormularioPqrsd
            canal="chat"
            valoresIniciales={estado?.resumen}
            alRadicar={setRadicada}
          />
        </section>
      )}

      {radicada && <Confirmacion resultado={radicada} />}

      {error && (
        <p role="alert" style={estilosFormulario.error}>{error}</p>
      )}

      {puedeEscribir && (
        <form onSubmit={enviarMensaje} style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', marginTop: '1rem' }}>
          <label htmlFor="mensaje">Escriba su mensaje</label>
          <textarea
            id="mensaje"
            style={{ ...estilos.campo, minHeight: 80 }}
            value={texto}
            maxLength={MAX_CARACTERES}
            onChange={(e) => setTexto(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) enviarMensaje(e)
            }}
            disabled={enviando}
          />
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={estilos.nota}>{texto.length}/{MAX_CARACTERES}</span>
            <button type="submit" style={estilosFormulario.boton} disabled={enviando || !texto.trim()}>
              {enviando ? 'Enviando…' : 'Enviar'}
            </button>
          </div>
        </form>
      )}
      <div ref={finRef} />
    </main>
  )
}

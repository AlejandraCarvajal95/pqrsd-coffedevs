import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import FormularioPqrsd from '../components/FormularioPqrsd.jsx'
import {
  consultarChat,
  continuarConPqrsd,
  registrarResultadoChat,
} from '../services/api.js'

// Chat de desvío (US-009): el ciudadano pregunta y, si la base de conocimiento
// tiene la respuesta, la recibe con sus fuentes sin radicar una PQRSD.
// US-008 ampliará esta página con la radicación conversacional.

const MAX_CARACTERES = 1000

const estilos = {
  pagina: { fontFamily: 'system-ui, sans-serif', maxWidth: 720, margin: '2rem auto', padding: '0 1rem', color: '#1a1a1a' },
  historial: { display: 'flex', flexDirection: 'column', gap: '0.75rem', margin: '1rem 0', padding: 0, listStyle: 'none' },
  ciudadano: { alignSelf: 'flex-end', background: '#e8f0fe', borderRadius: 8, padding: '0.6rem 0.9rem', maxWidth: '85%', whiteSpace: 'pre-wrap' },
  asistente: { alignSelf: 'flex-start', background: '#f4f4f4', borderRadius: 8, padding: '0.6rem 0.9rem', maxWidth: '85%', whiteSpace: 'pre-wrap' },
  fuentes: { fontSize: '0.85rem', color: '#444', marginTop: '0.5rem', paddingLeft: '1.1rem' },
  acciones: { display: 'flex', flexWrap: 'wrap', gap: '0.5rem', marginTop: '0.6rem' },
  boton: { padding: '0.5rem 0.9rem', borderRadius: 6, border: '1px solid #1a4fa0', background: '#1a4fa0', color: '#fff', cursor: 'pointer', fontSize: '0.95rem' },
  botonSecundario: { padding: '0.5rem 0.9rem', borderRadius: 6, border: '1px solid #1a4fa0', background: '#fff', color: '#1a4fa0', cursor: 'pointer', fontSize: '0.95rem' },
  error: { background: '#fdecea', color: '#8a1c1c', border: '1px solid #f5c2c0', borderRadius: 6, padding: '0.6rem 0.9rem' },
  formulario: { display: 'flex', flexDirection: 'column', gap: '0.5rem' },
  campo: { width: '100%', boxSizing: 'border-box', padding: '0.6rem', fontSize: '1rem', borderRadius: 6, border: '1px solid #999', fontFamily: 'inherit' },
  tarjeta: { border: '1px solid #ccc', borderRadius: 8, padding: '1rem', marginTop: '1rem' },
  nota: { fontSize: '0.85rem', color: '#555' },
}

function Fuentes({ fuentes }) {
  if (!fuentes?.length) return null
  return (
    <div>
      <strong style={{ fontSize: '0.85rem' }}>Fuentes:</strong>
      <ul style={estilos.fuentes}>
        {fuentes.map((fuente) => (
          <li key={fuente.etiqueta}>
            [{fuente.etiqueta}] {fuente.documento} › {fuente.seccion}
          </li>
        ))}
      </ul>
    </div>
  )
}

function RadicacionSugerida({ sugerida }) {
  // Usa el formulario de US-007 con lo conversado; el ciudadano revisa y confirma.
  return (
    <section style={estilos.tarjeta} aria-labelledby="titulo-pqrsd">
      <h2 id="titulo-pqrsd" style={{ marginTop: 0, fontSize: '1.15rem' }}>Continuar con una PQRSD</h2>
      <p>{sugerida.mensaje}</p>
      <FormularioPqrsd
        canal="chat"
        valoresIniciales={{ asunto: sugerida.asunto, descripcion: sugerida.descripcion }}
      />
    </section>
  )
}

export default function Chat() {
  const [sesionId, setSesionId] = useState(null)
  const [mensajes, setMensajes] = useState([])
  const [texto, setTexto] = useState('')
  const [enviando, setEnviando] = useState(false)
  const [error, setError] = useState(null)
  const [mostrarContinuar, setMostrarContinuar] = useState(false)
  const [sugerida, setSugerida] = useState(null)
  const finRef = useRef(null)

  useEffect(() => {
    finRef.current?.scrollIntoView?.({ behavior: 'smooth' })
  }, [mensajes, sugerida])

  function actualizarUltimo(cambios) {
    setMensajes((previos) => previos.map((m, i) => (i === previos.length - 1 ? { ...m, ...cambios } : m)))
  }

  async function enviarPregunta(evento) {
    evento.preventDefault()
    const pregunta = texto.trim()
    if (!pregunta || enviando) return
    setError(null)
    setEnviando(true)
    setMensajes((previos) => [...previos, { rol: 'ciudadano', texto: pregunta }])
    setTexto('')
    try {
      const datos = await consultarChat(sesionId, pregunta)
      setSesionId(datos.sesion_id)
      setMensajes((previos) => [
        ...previos,
        {
          rol: 'asistente',
          texto: datos.respuesta,
          fuentes: datos.fuentes,
          preguntaResuelto: datos.pregunta_resuelto,
        },
      ])
      if (datos.ofrecer_radicar) setMostrarContinuar(true)
    } catch (e) {
      setError(e.message)
    } finally {
      setEnviando(false)
    }
  }

  async function marcarResultado(resolvio) {
    setError(null)
    try {
      await registrarResultadoChat(sesionId, resolvio)
      actualizarUltimo({ preguntaResuelto: false, resultado: resolvio ? 'resuelta' : 'no_resuelta' })
      if (!resolvio) setMostrarContinuar(true)
    } catch (e) {
      setError(e.message)
    }
  }

  async function continuar() {
    setError(null)
    try {
      const datos = await continuarConPqrsd(sesionId)
      setSugerida({ mensaje: datos.mensaje, ...datos.radicacion_sugerida })
      setMostrarContinuar(false)
    } catch (e) {
      setError(e.message)
    }
  }

  const ultimo = mensajes[mensajes.length - 1]

  return (
    <main style={estilos.pagina}>
      <p><Link to="/">Inicio</Link></p>
      <h1 style={{ marginBottom: '0.25rem' }}>Asistente virtual</h1>
      <p style={estilos.nota}>
        Resuelva sus dudas sobre productos y atención del banco. Las respuestas salen de la
        información oficial del banco y muestran sus fuentes. No comparta datos sensibles como
        su cédula, números de tarjeta o claves.
      </p>

      <ol style={estilos.historial} aria-live="polite" aria-label="Conversación">
        {mensajes.map((mensaje, i) => (
          <li key={i} style={mensaje.rol === 'ciudadano' ? estilos.ciudadano : estilos.asistente}>
            <span style={{ position: 'absolute', left: -9999 }}>
              {mensaje.rol === 'ciudadano' ? 'Usted dijo:' : 'El asistente respondió:'}
            </span>
            {mensaje.texto}
            {mensaje.rol === 'asistente' && <Fuentes fuentes={mensaje.fuentes} />}
            {mensaje.resultado === 'resuelta' && <p style={estilos.nota}>Gracias por confirmarlo.</p>}
          </li>
        ))}
        {enviando && <li style={estilos.asistente}>Buscando en la base de conocimiento…</li>}
      </ol>

      {ultimo?.rol === 'asistente' && ultimo.preguntaResuelto && (
        <div style={estilos.acciones} role="group" aria-label="¿Se resolvió su duda?">
          <span>¿Se resolvió su duda?</span>
          <button type="button" style={estilos.boton} onClick={() => marcarResultado(true)}>
            Resolvió mi duda
          </button>
          <button type="button" style={estilos.botonSecundario} onClick={() => marcarResultado(false)}>
            Necesito más ayuda
          </button>
        </div>
      )}

      {mostrarContinuar && sesionId && !sugerida && (
        <div style={estilos.acciones}>
          <button type="button" style={estilos.boton} onClick={continuar}>
            Continuar con una PQRSD
          </button>
        </div>
      )}

      {sugerida && <RadicacionSugerida sugerida={sugerida} />}

      {error && (
        <p role="alert" style={{ ...estilos.error, marginTop: '1rem' }}>
          {error}
        </p>
      )}

      <form onSubmit={enviarPregunta} style={{ ...estilos.formulario, marginTop: '1rem' }}>
        <label htmlFor="pregunta">Escriba su pregunta</label>
        <textarea
          id="pregunta"
          style={{ ...estilos.campo, minHeight: 80 }}
          value={texto}
          maxLength={MAX_CARACTERES}
          onChange={(e) => setTexto(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) enviarPregunta(e)
          }}
          disabled={enviando}
        />
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span style={estilos.nota}>{texto.length}/{MAX_CARACTERES}</span>
          <button type="submit" style={estilos.boton} disabled={enviando || !texto.trim()}>
            {enviando ? 'Enviando…' : 'Enviar'}
          </button>
        </div>
      </form>
      <div ref={finRef} />
    </main>
  )
}

import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import FormularioPqrsd from '../components/FormularioPqrsd.jsx'
import { IconoAlerta, IconoEnviar, IconoFlecha } from '../components/Iconos.jsx'
import {
  consultarChat,
  continuarConPqrsd,
  registrarResultadoChat,
} from '../services/api.js'

// Chat de desvío (US-009): el ciudadano pregunta y, si la base de conocimiento
// tiene la respuesta, la recibe con sus fuentes sin radicar una PQRSD.
// US-008 ampliará esta página con la radicación conversacional.

const MAX_CARACTERES = 1000

// Tomadas de data/ejemplos/consultas_desvio.json (grupo "cubierta").
const PREGUNTAS_DE_EJEMPLO = [
  '¿Por qué me cobran cuota de manejo si no he usado la tarjeta este mes?',
  '¿Me pueden reportar en una central de riesgo sin avisarme antes?',
  'En mi extracto aparece una compra que yo no hice, ¿qué debo hacer?',
]

function Fuentes({ fuentes }) {
  if (!fuentes?.length) return null
  return (
    <div className="fuentes">
      <p className="fuentes__titulo">Fuentes</p>
      <ul>
        {fuentes.map((fuente) => (
          <li key={fuente.etiqueta} className="etiqueta-tecnica">
            <span className="fuentes__etiqueta">[{fuente.etiqueta}]</span> {fuente.documento} › {fuente.seccion}
          </li>
        ))}
      </ul>
    </div>
  )
}

function RadicacionSugerida({ sugerida, referencia }) {
  // Usa el formulario de US-007 con lo conversado; el ciudadano revisa y confirma.
  return (
    <section ref={referencia} className="tarjeta tarjeta--tecnica chat__radicacion" aria-labelledby="titulo-pqrsd">
      <h2 id="titulo-pqrsd" className="encabezado">Continuar con una PQRSD</h2>
      <p className="texto-apoyo">{sugerida.mensaje}</p>
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
  const radicacionRef = useRef(null)

  useEffect(() => {
    // Sin mensajes no se desplaza: la página abre arriba, en el título.
    if (!mensajes.length) return
    finRef.current?.scrollIntoView?.({ behavior: 'smooth', block: 'nearest' })
  }, [mensajes, enviando])

  useEffect(() => {
    // Al abrirse el formulario sugerido, se lleva a su comienzo.
    if (sugerida) radicacionRef.current?.scrollIntoView?.({ behavior: 'smooth', block: 'start' })
  }, [sugerida])

  function actualizarUltimo(cambios) {
    setMensajes((previos) => previos.map((m, i) => (i === previos.length - 1 ? { ...m, ...cambios } : m)))
  }

  async function preguntar(pregunta) {
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

  function enviarPregunta(evento) {
    evento.preventDefault()
    preguntar(texto.trim())
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
  const vacio = mensajes.length === 0

  return (
    <div className="contenedor contenedor--angosto pagina chat">
      <h1 className="display-seccion pagina__titulo">Resolver una duda</h1>
      <p className="pagina__bajada texto-apoyo">
        Resuelva sus dudas sobre productos y atención del banco. Las respuestas salen de la
        información oficial del banco y muestran sus fuentes. No comparta datos sensibles como su
        cédula, números de tarjeta o claves.
      </p>
      <p className="pagina__bajada texto-apoyo">
        ¿Quiere radicar en lugar de preguntar?{' '}
        <Link className="enlace" to="/radicar/chat">Hágalo con el asistente</Link> o{' '}
        <Link className="enlace" to="/radicar">por su cuenta con el formulario</Link>.
      </p>

      <div className="tarjeta tarjeta--nube chat__panel">
        {vacio && (
          <div className="chat__vacio">
            <p className="texto-enfasis">Aún no hay mensajes. Escriba su pregunta abajo o pruebe con una de estas:</p>
            <ul className="chat__ejemplos">
              {PREGUNTAS_DE_EJEMPLO.map((pregunta) => (
                <li key={pregunta}>
                  <button type="button" className="chat__ejemplo" onClick={() => preguntar(pregunta)}>
                    {pregunta}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}

        <ol className="chat__historial" aria-live="polite" aria-label="Conversación">
          {mensajes.map((mensaje, i) => (
            <li key={i} className={`mensaje mensaje--${mensaje.rol}`}>
              <span className="solo-lectores">
                {mensaje.rol === 'ciudadano' ? 'Usted dijo:' : 'El asistente respondió:'}
              </span>
              {mensaje.texto}
              {mensaje.rol === 'asistente' && <Fuentes fuentes={mensaje.fuentes} />}
              {mensaje.resultado === 'resuelta' && (
                <p className="mensaje__nota">Gracias por confirmarlo.</p>
              )}
            </li>
          ))}
          {enviando && (
            <li className="mensaje mensaje--asistente mensaje--espera">
              <span className="puntos" aria-hidden="true"><span /><span /><span /></span>
              Buscando en la base de conocimiento…
            </li>
          )}
        </ol>

        {ultimo?.rol === 'asistente' && ultimo.preguntaResuelto && (
          <div className="chat__acciones" role="group" aria-label="¿Se resolvió su duda?">
            <span className="chat__pregunta">¿Se resolvió su duda?</span>
            <button type="button" className="boton boton--grafito" onClick={() => marcarResultado(true)}>
              Resolvió mi duda
            </button>
            <button type="button" className="boton boton--linea" onClick={() => marcarResultado(false)}>
              Necesito más ayuda
            </button>
          </div>
        )}

        {mostrarContinuar && sesionId && !sugerida && (
          <div className="chat__acciones">
            <button type="button" className="boton boton--menta" onClick={continuar}>
              Continuar con una PQRSD <IconoFlecha />
            </button>
          </div>
        )}

        {error && (
          <p role="alert" className="aviso-error">
            <IconoAlerta />
            <span>{error}</span>
          </p>
        )}

        <form onSubmit={enviarPregunta} className="redactor">
          <label htmlFor="pregunta" className="campo__etiqueta">Escriba su pregunta</label>
          <div className="redactor__caja">
            <textarea
              id="pregunta"
              className="redactor__texto"
              rows={2}
              value={texto}
              maxLength={MAX_CARACTERES}
              onChange={(e) => setTexto(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) enviarPregunta(e)
              }}
              disabled={enviando}
              aria-describedby="pregunta-ayuda"
            />
            <button
              type="submit"
              className="boton boton--menta redactor__enviar"
              disabled={enviando || !texto.trim()}
            >
              {enviando ? 'Enviando…' : 'Enviar'}
              {!enviando && <IconoEnviar />}
            </button>
          </div>
          <p id="pregunta-ayuda" className="campo__pie etiqueta-tecnica">
            <span>Enter envía. Mayús + Enter hace un salto de línea.</span>
            <span>{texto.length}/{MAX_CARACTERES}</span>
          </p>
        </form>
        <div ref={finRef} />
      </div>

      {sugerida && <RadicacionSugerida sugerida={sugerida} referencia={radicacionRef} />}
    </div>
  )
}

import { useEffect, useRef, useState } from 'react'
import { conversarConAsistente } from '../services/api.js'
import { legible } from '../utils/formato.js'
import { IconoAlerta, IconoCheck, IconoEnviar } from './Iconos.jsx'

// Chat del empleado para ajustar el borrador (US-021), al estilo de un asistente
// conversacional: la persona pide cambios con sus palabras y la carta que propone
// la IA se aplica sola al documento (y se guarda), con opción de deshacer.
// El texto original se conserva siempre y nada llega al ciudadano sin que una
// persona pulse "Aprobar y enviar".

const SUGERENCIAS = [
  { etiqueta: 'Más empático', texto: 'Haz el tono más empático, sin cambiar el fondo de la respuesta.' },
  { etiqueta: 'Explicar plazos y normativa', texto: 'Explica los tiempos de respuesta y la normativa o política aplicable, citando las fuentes.' },
  { etiqueta: 'Lenguaje sencillo', texto: 'Simplifica el lenguaje: frases cortas y sin términos legales.' },
]

const ALTO_MAXIMO_CAJA = 200

export default function AsistenteBorrador({
  radicado,
  texto,
  intro,
  bloqueo,
  deshabilitado,
  onAplicar,
  onVerDocumento,
  onFuentesNuevas,
  onSesionVencida,
}) {
  // { rol, texto, propuesta?, fuentes?, textoAnterior?, deshecha? }
  const [turnos, setTurnos] = useState([])
  const [mensaje, setMensaje] = useState('')
  const [enviando, setEnviando] = useState(false)
  const [error, setError] = useState(null)
  const [restantes, setRestantes] = useState(null)
  const final = useRef(null)
  const caja = useRef(null)

  useEffect(() => {
    final.current?.scrollIntoView({ block: 'end', behavior: 'smooth' })
  }, [turnos, enviando])

  // La caja crece con el texto hasta un tope, como en los chats de IA.
  useEffect(() => {
    const elemento = caja.current
    if (!elemento) return
    elemento.style.height = 'auto'
    elemento.style.height = `${Math.min(elemento.scrollHeight, ALTO_MAXIMO_CAJA)}px`
  }, [mensaje])

  async function enviar(instruccion) {
    const limpio = instruccion.trim()
    if (!limpio || enviando || bloqueo) return
    setError(null)
    setEnviando(true)
    const historial = turnos.map(({ rol, texto: contenido }) => ({ rol, texto: contenido }))
    const textoAnterior = texto
    setTurnos((previos) => [...previos, { rol: 'empleado', texto: limpio }])
    setMensaje('')
    try {
      const datos = await conversarConAsistente(radicado, {
        mensaje: limpio,
        historial,
        borrador_actual: texto,
      })
      setTurnos((previos) => [
        ...previos,
        {
          rol: 'asistente',
          texto: datos.respuesta_asistente,
          propuesta: datos.borrador_propuesto,
          fuentes: datos.fuentes,
          textoAnterior,
        },
      ])
      setRestantes(datos.mensajes_restantes)
      if (datos.borrador_propuesto) await onAplicar(datos.borrador_propuesto)
      if (datos.fuentes.some((fuente) => fuente.nueva)) onFuentesNuevas?.()
    } catch (e) {
      if (e.estado === 401) {
        onSesionVencida?.(e)
        return
      }
      // La instrucción que falló no cuenta: se retira y vuelve a la caja de texto.
      setTurnos((previos) => previos.slice(0, -1))
      setMensaje(limpio)
      setError(e.message)
    } finally {
      setEnviando(false)
    }
  }

  async function deshacer(indice) {
    await onAplicar(turnos[indice].textoAnterior)
    setTurnos((previos) => previos.map((turno, i) => (i === indice ? { ...turno, deshecha: true } : turno)))
  }

  // Solo se deshace el último cambio: deshacer uno anterior pisaría los siguientes.
  let ultimoCambio = -1
  turnos.forEach((turno, i) => {
    if (turno.propuesta) ultimoCambio = i
  })

  const sinCupo = restantes === 0
  const bloqueado = Boolean(bloqueo) || deshabilitado || enviando || sinCupo

  return (
    <section className="panel panel--chat" aria-labelledby="titulo-chat">
      <h2 id="titulo-chat" className="visualmente-oculto">Conversación con el asistente de redacción</h2>

      <ol className="chat__mensajes" aria-live="polite">
        {intro && <li className="chat__intro">{intro}</li>}

        {turnos.map((turno, i) => (
          <li key={i} className="chat__turno" data-rol={turno.rol}>
            {turno.rol === 'asistente' && <span className="chat__autor">Asistente</span>}
            <p className="chat__texto">{turno.texto}</p>

            {turno.propuesta && (
              <div className="chat__cambio" data-deshecho={Boolean(turno.deshecha)}>
                <p className="chat__cambio-titulo">
                  {turno.deshecha ? (
                    'Cambio deshecho: el documento volvió a la versión anterior.'
                  ) : (
                    <>
                      <IconoCheck width={14} height={14} /> Cambios aplicados al documento
                    </>
                  )}
                </p>
                {turno.fuentes.length > 0 && !turno.deshecha && (
                  <p className="chat__fuentes">
                    Fuentes:{' '}
                    {turno.fuentes
                      .map((fuente) => `[${fuente.etiqueta}] ${legible(fuente.documento)}${fuente.nueva ? ' (nueva)' : ''}`)
                      .join(' · ')}
                  </p>
                )}
                <div className="chat__cambio-acciones">
                  <button type="button" className="chat__enlace chat__solo-angosto" onClick={onVerDocumento}>
                    Ver documento
                  </button>
                  {i === ultimoCambio && !turno.deshecha && (
                    <button
                      type="button"
                      className="chat__enlace"
                      disabled={deshabilitado || enviando}
                      onClick={() => deshacer(i)}
                    >
                      Deshacer
                    </button>
                  )}
                </div>
              </div>
            )}
          </li>
        ))}

        {enviando && (
          <li className="chat__turno" data-rol="asistente" role="status">
            <span className="chat__autor">Asistente</span>
            <p className="chat__texto texto-apoyo">
              <span className="puntos" aria-hidden="true"><span /><span /><span /></span> Editando el documento…
            </p>
          </li>
        )}
        <li ref={final} aria-hidden="true" />
      </ol>

      <form
        className="chat__compositor"
        onSubmit={(evento) => {
          evento.preventDefault()
          enviar(mensaje)
        }}
      >
        {error && (
          <p role="alert" className="aviso-error">
            <IconoAlerta />
            <span>{error}</span>
          </p>
        )}

        {!bloqueo && (
          <div className="chat__sugerencias" role="group" aria-label="Sugerencias rápidas">
            {SUGERENCIAS.map((sugerencia) => (
              <button
                key={sugerencia.etiqueta}
                type="button"
                className="chat__chip"
                disabled={bloqueado}
                onClick={() => enviar(sugerencia.texto)}
              >
                {sugerencia.etiqueta}
              </button>
            ))}
          </div>
        )}

        <label htmlFor="instruccion-asistente" className="visualmente-oculto">
          Instrucción para el asistente
        </label>
        <div className="chat__caja" data-bloqueada={Boolean(bloqueo) || sinCupo}>
          <textarea
            id="instruccion-asistente"
            ref={caja}
            className="chat__entrada"
            rows={1}
            maxLength={1000}
            value={mensaje}
            placeholder={bloqueo ? 'El asistente no está disponible' : 'Pida un cambio al documento…'}
            disabled={Boolean(bloqueo) || deshabilitado || sinCupo}
            onChange={(e) => setMensaje(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                enviar(mensaje)
              }
            }}
          />
          <button
            type="submit"
            className="chat__enviar"
            aria-label="Enviar instrucción"
            disabled={bloqueado || !mensaje.trim()}
          >
            <IconoEnviar width={18} height={18} />
          </button>
        </div>
        <p className="chat__pie">
          {bloqueo
            ? bloqueo
            : sinCupo
              ? 'Esta conversación llegó al máximo de instrucciones. Puede seguir editando el documento a mano.'
              : restantes === null
                ? 'Enter para enviar · Mayús + Enter para un salto de línea. Cada instrucción consume presupuesto de IA.'
                : `Quedan ${restantes} instrucción${restantes === 1 ? '' : 'es'} en esta conversación.`}
        </p>
      </form>
    </section>
  )
}

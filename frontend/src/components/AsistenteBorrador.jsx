import { useEffect, useRef, useState } from 'react'
import { conversarConAsistente } from '../services/api.js'
import { legible } from '../utils/formato.js'
import { IconoAlerta, IconoCheck, IconoEnviar } from './Iconos.jsx'

// Asistente de redacción del empleado (US-021). La persona pide cambios en
// lenguaje natural; la IA responde y, si aplica, propone la carta completa.
// Nada cambia en el editor hasta que la persona pulsa "Aplicar al editor",
// y puede deshacerlo. El borrador original se conserva siempre.

const SUGERENCIAS = [
  { etiqueta: 'Hacer más empático', texto: 'Haz el tono más empático, sin cambiar el fondo de la respuesta.' },
  { etiqueta: 'Explicar tiempos y normativa', texto: 'Explica los tiempos de respuesta y la normativa o política aplicable, citando las fuentes.' },
  { etiqueta: 'Simplificar lenguaje', texto: 'Simplifica el lenguaje: frases cortas y sin términos legales.' },
]

export default function AsistenteBorrador({ radicado, texto, deshabilitado, onAplicar, onFuentesNuevas, onSesionVencida }) {
  const [turnos, setTurnos] = useState([]) // { rol, texto, propuesta?, fuentes? }
  const [mensaje, setMensaje] = useState('')
  const [enviando, setEnviando] = useState(false)
  const [error, setError] = useState(null)
  const [restantes, setRestantes] = useState(null)
  const [aplicada, setAplicada] = useState(null) // { indice, textoAnterior }
  const final = useRef(null)

  useEffect(() => {
    final.current?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
  }, [turnos, enviando])

  async function enviar(instruccion) {
    const limpio = instruccion.trim()
    if (!limpio || enviando) return
    setError(null)
    setEnviando(true)
    const historial = turnos.map(({ rol, texto: contenido }) => ({ rol, texto: contenido }))
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
        },
      ])
      setRestantes(datos.mensajes_restantes)
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

  function aplicar(indice) {
    setAplicada({ indice, textoAnterior: texto })
    onAplicar(turnos[indice].propuesta)
  }

  function deshacer() {
    onAplicar(aplicada.textoAnterior)
    setAplicada(null)
  }

  const sinCupo = restantes === 0
  const bloqueado = deshabilitado || enviando || sinCupo

  return (
    <section className="tarjeta tarjeta--tecnica caso__bloque asistente" aria-labelledby="titulo-asistente">
      <header className="asistente__cabecera">
        <h2 id="titulo-asistente" className="caso__subtitulo">Asistente de redacción</h2>
        <span className="pildora" data-tono="neutro">IA · usted decide qué aplicar</span>
      </header>
      <p className="asistente__bajada texto-apoyo">
        Pídale cambios al borrador con sus palabras. La propuesta solo entra al editor cuando usted
        la aplica, y puede deshacerla.
      </p>

      <div className="asistente__sugerencias" role="group" aria-label="Sugerencias rápidas">
        {SUGERENCIAS.map((sugerencia) => (
          <button
            key={sugerencia.etiqueta}
            type="button"
            className="asistente__chip"
            disabled={bloqueado}
            onClick={() => enviar(sugerencia.texto)}
          >
            {sugerencia.etiqueta}
          </button>
        ))}
      </div>

      {turnos.length > 0 && (
        <ol className="asistente__conversacion" aria-live="polite">
          {turnos.map((turno, i) => (
            <li key={i} className="asistente__turno" data-rol={turno.rol}>
              <span className="asistente__autor">{turno.rol === 'empleado' ? 'Usted' : 'Asistente'}</span>
              <p className="asistente__texto">{turno.texto}</p>

              {turno.propuesta && (
                <div className="asistente__propuesta">
                  <details>
                    <summary>Ver la carta propuesta</summary>
                    <p className="asistente__carta">{turno.propuesta}</p>
                  </details>
                  {turno.fuentes.length > 0 && (
                    <p className="asistente__fuentes texto-apoyo">
                      Fuentes:{' '}
                      {turno.fuentes
                        .map((fuente) => `[${fuente.etiqueta}] ${legible(fuente.documento)}${fuente.nueva ? ' (nueva)' : ''}`)
                        .join(' · ')}
                    </p>
                  )}
                  {aplicada?.indice === i ? (
                    <div className="asistente__aplicada">
                      <span className="pildora" data-tono="ok">
                        <IconoCheck width={12} height={12} /> Aplicada al editor
                      </span>
                      <button type="button" className="boton boton--linea" onClick={deshacer}>
                        Deshacer
                      </button>
                    </div>
                  ) : (
                    <button
                      type="button"
                      className="boton boton--menta asistente__aplicar"
                      disabled={deshabilitado}
                      onClick={() => aplicar(i)}
                    >
                      Aplicar al editor
                    </button>
                  )}
                </div>
              )}
            </li>
          ))}
          {enviando && (
            <li className="asistente__turno" data-rol="asistente" role="status">
              <span className="asistente__autor">Asistente</span>
              <p className="asistente__texto texto-apoyo">
                <span className="puntos" aria-hidden="true"><span /><span /><span /></span> Redactando la
                propuesta…
              </p>
            </li>
          )}
          <li ref={final} aria-hidden="true" />
        </ol>
      )}

      {error && (
        <p role="alert" className="aviso-error">
          <IconoAlerta />
          <span>{error}</span>
        </p>
      )}

      <form
        className="asistente__formulario"
        onSubmit={(evento) => {
          evento.preventDefault()
          enviar(mensaje)
        }}
      >
        <label htmlFor="instruccion-asistente" className="campo__etiqueta">
          Instrucción para el asistente
        </label>
        <div className="asistente__entrada">
          <textarea
            id="instruccion-asistente"
            className="campo__control asistente__caja"
            rows={2}
            maxLength={1000}
            value={mensaje}
            placeholder="Por ejemplo: resume el segundo párrafo y explica el plazo de reversión"
            disabled={deshabilitado || sinCupo}
            onChange={(e) => setMensaje(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                enviar(mensaje)
              }
            }}
          />
          <button type="submit" className="boton boton--grafito" disabled={bloqueado || !mensaje.trim()}>
            {enviando ? 'Enviando…' : 'Enviar'}
            {!enviando && <IconoEnviar />}
          </button>
        </div>
        <p className="asistente__pie texto-apoyo">
          {sinCupo
            ? 'Esta conversación llegó al máximo de instrucciones. Aplique la última propuesta o edite a mano.'
            : restantes === null
              ? 'Cada instrucción consulta a la IA y consume presupuesto.'
              : `Quedan ${restantes} instrucción${restantes === 1 ? '' : 'es'} en esta conversación.`}
        </p>
      </form>
    </section>
  )
}

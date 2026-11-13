import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import FormularioPqrsd, { Confirmacion } from '../components/FormularioPqrsd.jsx'
import { IconoAlerta, IconoEnviar, IconoFlecha } from '../components/Iconos.jsx'
import { confirmarRadicacionChat, enviarMensajeRadicacion } from '../services/api.js'

// Chat de radicación (US-008): el ciudadano cuenta su caso, el agente extrae los
// campos y pide los que faltan; al confirmar el resumen se radica la PQRSD con el
// mismo flujo del formulario. Si el chat se queda sin mensajes, se pasa al
// formulario ya llenado con lo reunido.

const MAX_CARACTERES = 1000

const SALUDO =
  'Hola, soy el asistente de radicación. Cuénteme con sus palabras qué ocurrió y yo armo su PQRSD.'

const PENDIENTES = {
  nombre_ciudadano: 'su nombre',
  contacto: 'un correo o teléfono de contacto',
  hechos: 'lo que ocurrió',
}

function Resumen({ resumen }) {
  return (
    <dl className="resumen-chat">
      <div>
        <dt className="etiqueta-tecnica">Nombre</dt>
        <dd>{resumen.nombre_ciudadano}</dd>
      </div>
      <div>
        <dt className="etiqueta-tecnica">Contacto</dt>
        <dd>{resumen.contacto}</dd>
      </div>
      <div>
        <dt className="etiqueta-tecnica">Asunto</dt>
        <dd>{resumen.asunto}</dd>
      </div>
      <div>
        <dt className="etiqueta-tecnica">Descripción</dt>
        <dd className="resumen-chat__descripcion">{resumen.descripcion}</dd>
      </div>
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
  const haHablado = mensajes.length > 1

  useEffect(() => {
    // Con solo el saludo no se desplaza: la página abre arriba, en el título.
    if (!haHablado && !radicada) return
    finRef.current?.scrollIntoView?.({ behavior: 'smooth', block: 'nearest' })
  }, [mensajes, enviando, estado, radicada, haHablado])

  const limiteAlcanzado = Boolean(estado?.limite_alcanzado)
  // Sin mensajes y con datos faltantes solo queda el formulario.
  const formularioObligado = limiteAlcanzado && !estado?.listo_para_confirmar
  const mostrarFormulario = !radicada && (usarFormulario || formularioObligado)
  const mostrarResumen = !radicada && !mostrarFormulario && estado?.listo_para_confirmar
  const puedeEscribir = !radicada && !limiteAlcanzado && !usarFormulario

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
    <div className="contenedor contenedor--angosto pagina chat">
      <h1 className="display-seccion pagina__titulo">Radicar con el asistente</h1>
      <p className="pagina__bajada texto-apoyo">
        Cuente qué ocurrió con sus palabras y el asistente le irá preguntando lo que falte para
        armar su PQRSD. Antes de radicar podrá revisar el resumen, y una persona del banco
        revisará y aprobará la respuesta. No escriba su cédula, números de tarjeta ni claves.
        ¿Prefiere llenar los campos usted mismo?{' '}
        <Link className="enlace" to="/radicar">Radique por su cuenta con el formulario</Link>.
      </p>

      <div className="tarjeta tarjeta--nube chat__panel">
        <ol className="chat__historial" aria-live="polite" aria-label="Conversación">
          {mensajes.map((mensaje, i) => (
            <li key={i} className={`mensaje mensaje--${mensaje.rol}`}>
              <span className="solo-lectores">
                {mensaje.rol === 'ciudadano' ? 'Usted dijo:' : 'El asistente respondió:'}
              </span>
              {mensaje.texto}
            </li>
          ))}
          {enviando && (
            <li className="mensaje mensaje--asistente mensaje--espera">
              <span className="puntos" aria-hidden="true"><span /><span /><span /></span>
              Escribiendo…
            </li>
          )}
        </ol>

        {!radicada && estado && pendientes.length > 0 && !mostrarFormulario && (
          <p className="chat__pendiente etiqueta-tecnica">
            Todavía falta: {pendientes.join(', ')}.
          </p>
        )}

        {mostrarResumen && (
          <section className="tarjeta tarjeta--tecnica chat__radicacion" aria-labelledby="titulo-resumen">
            <h2 id="titulo-resumen" className="encabezado">Resumen de su PQRSD</h2>
            <Resumen resumen={estado.resumen} />
            <div className="chat__acciones">
              <button type="button" className="boton boton--menta" onClick={confirmar} disabled={confirmando}>
                {confirmando ? 'Radicando…' : 'Confirmar y radicar'}
                {!confirmando && <IconoFlecha />}
              </button>
              <button type="button" className="boton boton--linea" onClick={() => setUsarFormulario(true)}>
                Ajustar en el formulario
              </button>
            </div>
            <p className="texto-apoyo">
              Si algo no está bien, siga escribiendo en el chat para corregirlo.
            </p>
          </section>
        )}

        {mostrarFormulario && (
          <section className="tarjeta tarjeta--tecnica chat__radicacion" aria-labelledby="titulo-formulario">
            <h2 id="titulo-formulario" className="encabezado">Complete su PQRSD en el formulario</h2>
            <p className="texto-apoyo">
              {limiteAlcanzado
                ? 'Llegamos al máximo de mensajes. Ya llené el formulario con lo que me contó: revíselo y complete lo que falte.'
                : 'Revise los datos y ajústelos antes de radicar.'}
            </p>
            <FormularioPqrsd canal="chat" valoresIniciales={estado?.resumen} alRadicar={setRadicada} />
          </section>
        )}

        {radicada && <Confirmacion resultado={radicada} />}

        {error && (
          <p role="alert" className="aviso-error">
            <IconoAlerta />
            <span>{error}</span>
          </p>
        )}

        {puedeEscribir && (
          <form onSubmit={enviarMensaje} className="redactor">
            <label htmlFor="mensaje" className="campo__etiqueta">Escriba su mensaje</label>
            <div className="redactor__caja">
              <textarea
                id="mensaje"
                className="redactor__texto"
                rows={2}
                value={texto}
                maxLength={MAX_CARACTERES}
                onChange={(e) => setTexto(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) enviarMensaje(e)
                }}
                disabled={enviando}
                aria-describedby="mensaje-ayuda"
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
            <p id="mensaje-ayuda" className="campo__pie etiqueta-tecnica">
              <span>Enter envía. Mayús + Enter hace un salto de línea.</span>
              <span>{texto.length}/{MAX_CARACTERES}</span>
            </p>
          </form>
        )}
        <div ref={finRef} />
      </div>
    </div>
  )
}

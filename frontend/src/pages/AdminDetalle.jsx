import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import Aprendizaje from '../components/Aprendizaje.jsx'
import AsistenteBorrador from '../components/AsistenteBorrador.jsx'
import { IconoAlerta, IconoCheck } from '../components/Iconos.jsx'
import Semaforo from '../components/Semaforo.jsx'
import {
  aprobarRespuesta,
  confirmarClasificacion,
  guardarBorrador,
  obtenerDetalleAdmin,
  pedirBorrador,
  respuestaPdfAdmin,
} from '../services/api.js'
import {
  ETIQUETAS_ACCION,
  ETIQUETAS_ESTADO,
  ETIQUETAS_MOTIVO,
  bloqueosDeAprobacion,
  etiquetaTipo,
  formatearFecha,
  formatearFechaHora,
  legible,
} from '../utils/formato.js'

// Detalle de una PQRSD (US-020 y US-021) con distribución de asistente de IA:
// a la izquierda el chat, que abre con la solicitud del ciudadano; a la derecha
// el documento de respuesta. Lo que se pide en el chat se aplica solo al
// documento. Clasificación, aprendizajes e historial van en "Detalles del caso".

const ESPERA_BORRADOR_MS = 3000
const INTENTOS_BORRADOR = 40 // unos dos minutos
const DURACION_RESALTADO_MS = 1400

function Clasificacion({ pqrsd, ocupado, onConfirmar }) {
  const { clasificacion, opciones } = pqrsd
  const [tipo, setTipo] = useState(clasificacion.tipo || '')
  const [area, setArea] = useState(clasificacion.area || '')
  const respondida = pqrsd.estado === 'respondida'
  const sinCambios = tipo === (clasificacion.tipo || '') && area === (clasificacion.area || '')

  useEffect(() => {
    setTipo(clasificacion.tipo || '')
    setArea(clasificacion.area || '')
  }, [clasificacion.tipo, clasificacion.area])

  function enviar(evento) {
    evento.preventDefault()
    if (tipo && area) onConfirmar(tipo, area)
  }

  return (
    <section className="tarjeta tarjeta--tecnica caso__bloque" aria-labelledby="titulo-clasificacion">
      <h2 id="titulo-clasificacion" className="caso__subtitulo">Clasificación</h2>

      {pqrsd.requiere_revision && (
        <div className="aviso-revision" role="status">
          <strong>Una persona debe confirmar la clasificación.</strong>
          <ul>
            {clasificacion.motivos_revision.map((motivo) => (
              <li key={motivo}>{ETIQUETAS_MOTIVO[motivo] || legible(motivo)}</li>
            ))}
          </ul>
          {clasificacion.tipos_candidatos.length > 1 && (
            <p>Tipos propuestos: {clasificacion.tipos_candidatos.map(etiquetaTipo).join(' o ')}.</p>
          )}
        </div>
      )}

      <dl className="datos">
        <div><dt>Tipo</dt><dd>{etiquetaTipo(clasificacion.tipo)}</dd></div>
        <div><dt>Área</dt><dd>{clasificacion.area || 'Sin área'}</dd></div>
        <div><dt>Tema</dt><dd>{legible(clasificacion.tema)}</dd></div>
        <div><dt>Sentimiento</dt><dd>{legible(clasificacion.sentimiento)}</dd></div>
        <div>
          <dt>Riesgo de fraude</dt>
          <dd>
            {clasificacion.riesgo_fraude === null
              ? 'Sin determinar'
              : clasificacion.riesgo_fraude
                ? <span className="pildora" data-tono="alerta">Sí, verificar antes de responder</span>
                : 'No'}
          </dd>
        </div>
        <div>
          <dt>Confianza</dt>
          <dd>{clasificacion.confianza === null ? 'Sin dato' : `${Math.round(clasificacion.confianza * 100)} %`}</dd>
        </div>
      </dl>
      {clasificacion.justificacion && (
        <p className="caso__justificacion texto-apoyo">Motivo de la IA: {clasificacion.justificacion}</p>
      )}
      {clasificacion.revision_humana && (
        <p className="caso__justificacion texto-apoyo">
          Confirmada por {clasificacion.revision_humana.revisor} ·{' '}
          {formatearFechaHora(clasificacion.revision_humana.fecha)}
        </p>
      )}

      {!respondida && (
        <form className="reclasificar" onSubmit={enviar}>
          <div className="campo">
            <label htmlFor="tipo" className="campo__etiqueta">Tipo</label>
            <select id="tipo" className="campo__control" value={tipo} onChange={(e) => setTipo(e.target.value)} required>
              <option value="" disabled>Elija un tipo</option>
              {opciones.tipos.map((valor) => <option key={valor} value={valor}>{etiquetaTipo(valor)}</option>)}
            </select>
          </div>
          <div className="campo">
            <label htmlFor="area" className="campo__etiqueta">Área</label>
            <select id="area" className="campo__control" value={area} onChange={(e) => setArea(e.target.value)} required>
              <option value="" disabled>Elija un área</option>
              {opciones.areas.map((valor) => <option key={valor}>{valor}</option>)}
            </select>
          </div>
          <button
            type="submit"
            className={`boton ${pqrsd.requiere_revision ? 'boton--menta' : 'boton--linea'} reclasificar__boton`}
            disabled={ocupado || !tipo || !area || (sinCambios && !pqrsd.requiere_revision)}
          >
            {pqrsd.requiere_revision
              ? pqrsd.tiene_borrador ? 'Confirmar clasificación' : 'Confirmar y generar borrador'
              : 'Corregir clasificación'}
          </button>
        </form>
      )}
    </section>
  )
}

function Fuentes({ citas }) {
  if (!citas.length) {
    return (
      <p className="fuentes-citadas__vacio texto-apoyo">
        Este borrador no cita ninguna fuente de la base de conocimiento.
      </p>
    )
  }
  return (
    <ul className="fuentes-citadas">
      {citas.map((cita) => (
        <li key={cita.etiqueta}>
          <details className="fuente">
            <summary>
              <span className="fuente__etiqueta">[{cita.etiqueta}]</span>
              <span className="fuente__origen">{legible(cita.documento)} › {cita.seccion}</span>
              <span className="fuente__similitud">{Math.round(cita.similitud * 100)} % de similitud</span>
            </summary>
            <p className="fuente__texto">
              {cita.contenido || 'El fragmento ya no está en la base de conocimiento (se recargó).'}
            </p>
          </details>
        </li>
      ))}
    </ul>
  )
}

// Primer mensaje del chat: la solicitud tal como la escribió el ciudadano y lo
// que hizo la IA con ella, para que el contexto quede siempre a la vista.
function IntroCaso({ pqrsd, onVerDetalles }) {
  const { clasificacion } = pqrsd
  const resumen = [
    etiquetaTipo(clasificacion.tipo),
    clasificacion.area,
    clasificacion.confianza === null ? null : `${Math.round(clasificacion.confianza * 100)} % de confianza`,
  ].filter(Boolean)

  return (
    <>
      <article className="chat__caso" aria-label="Solicitud del ciudadano">
        <p className="chat__autor">
          {pqrsd.nombre_ciudadano} · {legible(pqrsd.canal)} · {formatearFechaHora(pqrsd.fecha_radicacion)}
        </p>
        <p className="chat__caso-texto">{pqrsd.descripcion}</p>
      </article>
      <div className="chat__turno" data-rol="asistente">
        <span className="chat__autor">Asistente</span>
        <p className="chat__texto">
          {pqrsd.requiere_revision
            ? 'No pude clasificar esta solicitud con seguridad. Confirme el tipo y el área en el panel del documento para que redacte el borrador.'
            : `La clasifiqué como ${resumen.join(' · ')}.`}
          {clasificacion.riesgo_fraude && ' Tiene señales de posible fraude: verifíquelo antes de responder.'}
        </p>
        {pqrsd.borrador && pqrsd.estado !== 'respondida' && (
          <p className="chat__texto">
            El borrador está en el documento. Pídame aquí los cambios que necesite y los aplico
            directamente; usted revisa y aprueba el envío.
          </p>
        )}
        <button type="button" className="chat__enlace" onClick={onVerDetalles}>
          Ver detalles del caso
        </button>
      </div>
    </>
  )
}

export default function AdminDetalle() {
  const { radicado } = useParams()
  const navegar = useNavigate()
  const [pqrsd, setPqrsd] = useState(null)
  const [texto, setTexto] = useState('')
  const [error, setError] = useState(null)
  const [aviso, setAviso] = useState(null)
  const [ocupado, setOcupado] = useState(false)
  const [guardando, setGuardando] = useState(false)
  const [resaltar, setResaltar] = useState(false)
  const [esperandoBorrador, setEsperandoBorrador] = useState(false)
  // En pantallas angostas se ve un panel a la vez.
  const [vista, setVista] = useState('chat')
  const dialogo = useRef(null)
  const detalles = useRef(null)
  const relojResaltado = useRef(null)

  const manejarError = useCallback(
    (e) => {
      if (e.estado === 401) navegar('/admin/login', { replace: true, state: { desde: `/admin/pqrsd/${radicado}` } })
      else setError(e.message)
    },
    [navegar, radicado],
  )

  // conservarTexto: no pisa lo que la persona tiene escrito y aún no guarda.
  const aplicar = useCallback((datos, conservarTexto = false) => {
    setPqrsd(datos)
    if (!conservarTexto) setTexto(datos.borrador ? datos.borrador.texto_actual : '')
  }, [])

  useEffect(() => {
    let vigente = true
    setPqrsd(null)
    setError(null)
    obtenerDetalleAdmin(radicado)
      .then((datos) => vigente && aplicar(datos))
      .catch((e) => vigente && manejarError(e))
    return () => {
      vigente = false
    }
  }, [radicado, aplicar, manejarError])

  useEffect(() => () => clearTimeout(relojResaltado.current), [])

  // Mientras el borrador se redacta en segundo plano, se consulta hasta que aparezca.
  useEffect(() => {
    if (!esperandoBorrador) return undefined
    let intentos = 0
    const reloj = setInterval(async () => {
      intentos += 1
      try {
        const datos = await obtenerDetalleAdmin(radicado)
        if (datos.borrador) {
          aplicar(datos)
          setEsperandoBorrador(false)
          setAviso('El borrador está listo para revisar.')
        } else if (intentos >= INTENTOS_BORRADOR) {
          setEsperandoBorrador(false)
          setError('El borrador no se generó. Revise el presupuesto de IA o inténtelo de nuevo.')
        }
      } catch (e) {
        setEsperandoBorrador(false)
        manejarError(e)
      }
    }, ESPERA_BORRADOR_MS)
    return () => clearInterval(reloj)
  }, [esperandoBorrador, radicado, aplicar, manejarError])

  // El asistente puede sumar fuentes al borrador: se recargan sin pisar el editor.
  function refrescarFuentes() {
    obtenerDetalleAdmin(radicado)
      .then((datos) => aplicar(datos, true))
      .catch(manejarError)
  }

  // Cambio pedido en el chat (o su deshacer): entra al documento y se guarda,
  // así la persona no tiene que aplicar ni guardar a mano.
  async function cambiarDesdeAsistente(nuevo) {
    setTexto(nuevo)
    setResaltar(true)
    clearTimeout(relojResaltado.current)
    relojResaltado.current = setTimeout(() => setResaltar(false), DURACION_RESALTADO_MS)
    setGuardando(true)
    setError(null)
    setAviso(null)
    try {
      aplicar(await guardarBorrador(radicado, nuevo), true)
    } catch (e) {
      manejarError(e)
    } finally {
      setGuardando(false)
    }
  }

  async function ejecutar(accion, mensaje, conservarTexto = false) {
    setOcupado(true)
    setError(null)
    setAviso(null)
    try {
      const datos = await accion()
      if (datos?.radicado && datos.clasificacion) aplicar(datos, conservarTexto)
      if (datos?.borrador_en_proceso) setEsperandoBorrador(true)
      else if (mensaje) setAviso(mensaje)
      return true
    } catch (e) {
      manejarError(e)
      return false
    } finally {
      setOcupado(false)
    }
  }

  if (!pqrsd) {
    return (
      <div className="contenedor pagina admin">
        <Link className="enlace" to="/admin">← Volver a la bandeja</Link>
        {error ? (
          <p role="alert" className="aviso-error"><IconoAlerta /><span>{error}</span></p>
        ) : (
          <p className="vacio texto-apoyo" role="status">Cargando la PQRSD…</p>
        )}
      </div>
    )
  }

  const { borrador } = pqrsd
  const respondida = pqrsd.estado === 'respondida'
  const editable = Boolean(borrador) && !respondida
  const sinGuardar = Boolean(borrador) && texto !== borrador.texto_actual
  const bloqueos = editable ? bloqueosDeAprobacion(texto) : []
  const tieneAviso = texto.includes('[AVISO AUTOMÁTICO DEL SISTEMA]') || texto.includes('[NOTA INTERNA')
  const clasificacionEnDocumento = !borrador && pqrsd.requiere_revision && !respondida

  const bloqueoChat = respondida
    ? 'Esta PQRSD ya fue respondida: el documento no se puede cambiar.'
    : !borrador
      ? 'El asistente se activa cuando el borrador esté listo.'
      : null

  const estadoGuardado = guardando
    ? 'Guardando…'
    : sinGuardar
      ? 'Cambios sin guardar'
      : borrador?.editado
        ? 'Guardado · editado'
        : 'Guardado'

  async function aprobar() {
    dialogo.current?.close()
    await ejecutar(() => aprobarRespuesta(radicado, texto), 'Respuesta aprobada y enviada al ciudadano.')
  }

  function confirmar(tipo, area) {
    return ejecutar(
      () => confirmarClasificacion(radicado, tipo, area),
      'Clasificación guardada.',
      Boolean(pqrsd.borrador),
    )
  }

  return (
    <div className="espacio" data-vista={vista}>
      <header className="espacio__barra">
        <Link className="espacio__volver" to="/admin" aria-label="Volver a la bandeja">←</Link>
        <div className="espacio__titulo">
          <p className="etiqueta-tecnica">{pqrsd.radicado}</p>
          <h1 title={pqrsd.asunto}>{pqrsd.asunto}</h1>
        </div>
        <div className="espacio__estado">
          {respondida ? (
            <span className="pildora" data-tono="ok"><IconoCheck width={12} height={12} /> Respondida</span>
          ) : (
            <Semaforo item={pqrsd} />
          )}
          {!respondida && <span className="pildora" data-tono="neutro">{ETIQUETAS_ESTADO[pqrsd.estado]}</span>}
          <button type="button" className="boton boton--linea espacio__detalles" onClick={() => detalles.current?.showModal()}>
            Detalles del caso
          </button>
        </div>
      </header>

      {(error || aviso) && (
        <div className="espacio__avisos">
          {error && <p role="alert" className="aviso-error"><IconoAlerta /><span>{error}</span></p>}
          {aviso && <p role="status" className="aviso-ok"><IconoCheck /><span>{aviso}</span></p>}
        </div>
      )}

      <div className="espacio__vistas" role="group" aria-label="Panel visible">
        <button type="button" aria-pressed={vista === 'chat'} onClick={() => setVista('chat')}>Chat</button>
        <button type="button" aria-pressed={vista === 'documento'} onClick={() => setVista('documento')}>
          Documento{sinGuardar ? ' •' : ''}
        </button>
      </div>

      <div className="espacio__paneles">
        <AsistenteBorrador
          radicado={radicado}
          texto={texto}
          intro={<IntroCaso pqrsd={pqrsd} onVerDetalles={() => detalles.current?.showModal()} />}
          bloqueo={bloqueoChat}
          deshabilitado={ocupado || guardando}
          onAplicar={cambiarDesdeAsistente}
          onVerDocumento={() => setVista('documento')}
          onFuentesNuevas={refrescarFuentes}
          onSesionVencida={manejarError}
        />

        <section className="panel panel--documento" aria-labelledby="titulo-documento">
          <header className="documento__barra">
            <h2 id="titulo-documento" className="documento__titulo">
              {respondida ? 'Respuesta enviada' : 'Respuesta al ciudadano'}
            </h2>
            {respondida && pqrsd.respuesta && (
              <div className="documento__acciones">
                <button
                  type="button"
                  className="boton boton--linea"
                  onClick={() => respuestaPdfAdmin(radicado).catch(manejarError)}
                >
                  Ver PDF
                </button>
                <button
                  type="button"
                  className="boton boton--grafito"
                  onClick={() => respuestaPdfAdmin(radicado, true).catch(manejarError)}
                >
                  Descargar PDF
                </button>
              </div>
            )}
            {editable && (
              <span className="documento__guardado" data-pendiente={sinGuardar} role="status">
                {estadoGuardado}
              </span>
            )}
            {editable && (
              <div className="documento__acciones">
                <button
                  type="button"
                  className="boton boton--linea"
                  disabled={ocupado || guardando || texto === borrador.texto_original}
                  onClick={() => setTexto(borrador.texto_original)}
                  title="Vuelve al texto que redactó la IA (no se guarda hasta que pulse Guardar)"
                >
                  Restaurar original
                </button>
                <button
                  type="button"
                  className="boton boton--grafito"
                  disabled={ocupado || guardando || !sinGuardar || !texto.trim()}
                  onClick={() => ejecutar(() => guardarBorrador(radicado, texto), 'Cambios guardados.')}
                >
                  Guardar
                </button>
                <button
                  type="button"
                  className="boton boton--menta"
                  disabled={ocupado || guardando || bloqueos.length > 0}
                  onClick={() => dialogo.current?.showModal()}
                >
                  Aprobar y enviar
                </button>
              </div>
            )}
          </header>

          <div className="documento__cuerpo">
            {esperandoBorrador && (
              <p className="estado__cargando texto-apoyo" role="status">
                <span className="puntos" aria-hidden="true"><span /><span /><span /></span>
                La IA está redactando el borrador. Suele tardar menos de un minuto.
              </p>
            )}

            {clasificacionEnDocumento && !esperandoBorrador && (
              <>
                <p className="documento__nota">
                  Confirme el tipo y el área. Con la clasificación confirmada se redacta el borrador aquí.
                </p>
                <Clasificacion pqrsd={pqrsd} ocupado={ocupado || esperandoBorrador} onConfirmar={confirmar} />
              </>
            )}

            {!borrador && !esperandoBorrador && !clasificacionEnDocumento && !respondida && (
              <div className="sin-borrador">
                <p>Esta PQRSD todavía no tiene borrador (puede que la IA no respondiera o que se agotara el presupuesto).</p>
                {pqrsd.estado === 'clasificada' && (
                  <button
                    type="button"
                    className="boton boton--menta"
                    disabled={ocupado}
                    onClick={() => ejecutar(() => pedirBorrador(radicado))}
                  >
                    Generar borrador
                  </button>
                )}
              </div>
            )}

            {respondida && pqrsd.respuesta && (
              <>
                <p className="documento__nota">
                  Aprobada por {pqrsd.respuesta.revisor} · {formatearFechaHora(pqrsd.respuesta.fecha)}
                </p>
                <div className="documento__hoja documento__hoja--lectura">{pqrsd.respuesta.texto_final}</div>
              </>
            )}

            {editable && (
              <>
                {tieneAviso && (
                  <div className="aviso-sistema" role="note">
                    <IconoAlerta />
                    <div>
                      <strong>Este borrador necesita atención antes de enviarse.</strong>
                      {borrador.avisos.length > 0 ? (
                        <ul>{borrador.avisos.map((linea) => <li key={linea}>{linea}</li>)}</ul>
                      ) : (
                        <p>Trae una nota interna de la IA. Pídale al asistente que la resuelva o retírela del texto.</p>
                      )}
                    </div>
                  </div>
                )}

                <label htmlFor="texto-borrador" className="visualmente-oculto">Texto de la respuesta</label>
                <textarea
                  id="texto-borrador"
                  className="documento__hoja documento__editor"
                  data-resaltar={resaltar}
                  value={texto}
                  maxLength={12000}
                  onChange={(e) => setTexto(e.target.value)}
                  spellCheck
                  lang="es"
                />

                {bloqueos.length > 0 && (
                  <div className="bloqueos">
                    <p>Para poder aprobar:</p>
                    <ul>{bloqueos.map((linea) => <li key={linea}>{linea}</li>)}</ul>
                  </div>
                )}
              </>
            )}

            {borrador && (
              <details className="documento__fuentes">
                <summary>
                  Fuentes citadas ({borrador.citas.length})
                  <span className="texto-apoyo"> · las etiquetas [F1], [F2]… se retiran solas al enviar</span>
                </summary>
                <Fuentes citas={borrador.citas} />
                <p className="fuentes-citadas__pie texto-apoyo">
                  Redactado por {borrador.modelo} · {borrador.tokens_entrada.toLocaleString('es-CO')} tokens de
                  entrada y {borrador.tokens_salida.toLocaleString('es-CO')} de salida.
                </p>
              </details>
            )}
          </div>
        </section>
      </div>

      <dialog ref={detalles} className="cajon" aria-labelledby="titulo-detalles">
        <header className="cajon__cabecera">
          <h2 id="titulo-detalles" className="caso__subtitulo">Detalles del caso</h2>
          <button type="button" className="boton boton--linea" onClick={() => detalles.current?.close()}>
            Cerrar
          </button>
        </header>
        <div className="cajon__contenido">
          <section className="tarjeta tarjeta--tecnica caso__bloque" aria-labelledby="titulo-caso">
            <h3 id="titulo-caso" className="caso__subtitulo">Solicitud del ciudadano</h3>
            <dl className="datos">
              <div><dt>Nombre</dt><dd>{pqrsd.nombre_ciudadano}</dd></div>
              <div><dt>Contacto</dt><dd>{pqrsd.contacto}</dd></div>
              <div><dt>Canal</dt><dd>{legible(pqrsd.canal)}</dd></div>
              <div><dt>Radicada</dt><dd>{formatearFechaHora(pqrsd.fecha_radicacion)}</dd></div>
              <div>
                <dt>Vence</dt>
                <dd>{formatearFecha(pqrsd.fecha_vencimiento, { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })}</dd>
              </div>
            </dl>
            <p className="caso__texto">{pqrsd.descripcion}</p>
          </section>

          {!clasificacionEnDocumento && (
            <Clasificacion pqrsd={pqrsd} ocupado={ocupado || esperandoBorrador} onConfirmar={confirmar} />
          )}

          <Aprendizaje
            radicado={radicado}
            areas={pqrsd.opciones.areas}
            areaInicial={pqrsd.clasificacion.area}
            onGuardado={(mensaje) => {
              setError(null)
              setAviso(mensaje)
            }}
            onSesionVencida={manejarError}
          />

          {pqrsd.revisiones.length > 0 && (
            <section className="tarjeta tarjeta--tecnica caso__bloque" aria-labelledby="titulo-historial">
              <h3 id="titulo-historial" className="caso__subtitulo">Historial de revisión</h3>
              <ol className="historial">
                {pqrsd.revisiones.map((revision, i) => (
                  <li key={`${revision.fecha}-${i}`}>
                    <strong>{revision.revisor}</strong> · {ETIQUETAS_ACCION[revision.accion] || revision.accion}
                    <span className="texto-apoyo"> · {formatearFechaHora(revision.fecha)}</span>
                  </li>
                ))}
              </ol>
            </section>
          )}
        </div>
      </dialog>

      <dialog ref={dialogo} className="dialogo" aria-labelledby="titulo-dialogo">
        <h2 id="titulo-dialogo" className="dialogo__titulo">¿Aprobar y enviar esta respuesta?</h2>
        <p>
          La PQRSD {pqrsd.radicado} quedará como respondida y el ciudadano lo verá al consultar su
          estado. Después no se puede editar.
        </p>
        <div className="dialogo__acciones">
          <button type="button" className="boton boton--linea" onClick={() => dialogo.current?.close()}>
            Seguir revisando
          </button>
          <button type="button" className="boton boton--menta" onClick={aprobar}>
            Sí, aprobar y enviar
          </button>
        </div>
      </dialog>
    </div>
  )
}

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

// Detalle de una PQRSD (US-020): a la izquierda el caso y su clasificación;
// a la derecha el borrador de la IA, sus fuentes y la aprobación.

const ESPERA_BORRADOR_MS = 3000
const INTENTOS_BORRADOR = 40 // unos dos minutos

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

export default function AdminDetalle() {
  const { radicado } = useParams()
  const navegar = useNavigate()
  const [pqrsd, setPqrsd] = useState(null)
  const [texto, setTexto] = useState('')
  const [error, setError] = useState(null)
  const [aviso, setAviso] = useState(null)
  const [ocupado, setOcupado] = useState(false)
  const [esperandoBorrador, setEsperandoBorrador] = useState(false)
  const dialogo = useRef(null)

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
  const sinGuardar = Boolean(borrador) && texto !== borrador.texto_actual
  const bloqueos = borrador && !respondida ? bloqueosDeAprobacion(texto) : []
  const tieneAviso = texto.includes('[AVISO AUTOMÁTICO DEL SISTEMA]') || texto.includes('[NOTA INTERNA')

  async function aprobar() {
    dialogo.current?.close()
    await ejecutar(() => aprobarRespuesta(radicado, texto), 'Respuesta aprobada y enviada al ciudadano.')
  }

  return (
    <div className="contenedor pagina admin">
      <Link className="enlace" to="/admin">← Volver a la bandeja</Link>

      <header className="caso__cabecera">
        <div>
          <p className="etiqueta-tecnica texto-apoyo">{pqrsd.radicado}</p>
          <h1 className="encabezado">{pqrsd.asunto}</h1>
        </div>
        <div className="caso__estado">
          {respondida ? (
            <span className="pildora" data-tono="ok"><IconoCheck width={12} height={12} /> Respondida</span>
          ) : (
            <Semaforo item={pqrsd} />
          )}
          {!respondida && <span className="pildora" data-tono="neutro">{ETIQUETAS_ESTADO[pqrsd.estado]}</span>}
        </div>
      </header>

      {error && <p role="alert" className="aviso-error"><IconoAlerta /><span>{error}</span></p>}
      {aviso && <p role="status" className="aviso-ok"><IconoCheck /><span>{aviso}</span></p>}

      <div className="caso">
        <div className="caso__columna">
          <section className="tarjeta tarjeta--tecnica caso__bloque" aria-labelledby="titulo-caso">
            <h2 id="titulo-caso" className="caso__subtitulo">Solicitud del ciudadano</h2>
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

          <Clasificacion
            pqrsd={pqrsd}
            ocupado={ocupado || esperandoBorrador}
            onConfirmar={(tipo, area) =>
              ejecutar(
                () => confirmarClasificacion(radicado, tipo, area),
                'Clasificación guardada.',
                Boolean(pqrsd.borrador),
              )
            }
          />

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
              <h2 id="titulo-historial" className="caso__subtitulo">Historial de revisión</h2>
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

        <div className="caso__columna">
          <section className="tarjeta tarjeta--tecnica caso__bloque" aria-labelledby="titulo-borrador">
            <h2 id="titulo-borrador" className="caso__subtitulo">
              {respondida ? 'Respuesta enviada' : 'Borrador de respuesta'}
            </h2>

            {esperandoBorrador && (
              <p className="estado__cargando texto-apoyo" role="status">
                <span className="puntos" aria-hidden="true"><span /><span /><span /></span>
                La IA está redactando el borrador. Suele tardar menos de un minuto.
              </p>
            )}

            {!borrador && !esperandoBorrador && (
              <div className="sin-borrador">
                {pqrsd.requiere_revision ? (
                  <p>Confirme primero el tipo y el área. Con la clasificación confirmada se redacta el borrador.</p>
                ) : (
                  <>
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
                  </>
                )}
              </div>
            )}

            {respondida && pqrsd.respuesta && (
              <>
                <p className="texto-apoyo">
                  Aprobada por {pqrsd.respuesta.revisor} · {formatearFechaHora(pqrsd.respuesta.fecha)}
                </p>
                <p className="caso__texto caso__texto--respuesta">{pqrsd.respuesta.texto_final}</p>
              </>
            )}

            {borrador && !respondida && (
              <>
                {tieneAviso && (
                  <div className="aviso-sistema" role="note">
                    <IconoAlerta />
                    <div>
                      <strong>Este borrador necesita atención antes de enviarse.</strong>
                      {borrador.avisos.length > 0 ? (
                        <ul>{borrador.avisos.map((linea) => <li key={linea}>{linea}</li>)}</ul>
                      ) : (
                        <p>Trae una nota interna de la IA: léala y retírela del texto.</p>
                      )}
                    </div>
                  </div>
                )}

                <label htmlFor="texto-borrador" className="campo__etiqueta">
                  Texto de la respuesta {borrador.editado && <span className="pildora" data-tono="neutro">Editado</span>}
                </label>
                <textarea
                  id="texto-borrador"
                  className="campo__control editor"
                  value={texto}
                  maxLength={12000}
                  onChange={(e) => setTexto(e.target.value)}
                  spellCheck
                  lang="es"
                />
                <p className="editor__pie texto-apoyo">
                  Las etiquetas [F1], [F2]… señalan la fuente de cada afirmación y se retiran solas al enviar.
                  {sinGuardar && <strong> Tiene cambios sin guardar.</strong>}
                </p>

                <div className="editor__acciones">
                  <button
                    type="button"
                    className="boton boton--linea"
                    disabled={ocupado || texto === borrador.texto_original}
                    onClick={() => setTexto(borrador.texto_original)}
                  >
                    Restaurar texto original
                  </button>
                  <button
                    type="button"
                    className="boton boton--grafito"
                    disabled={ocupado || !sinGuardar || !texto.trim()}
                    onClick={() => ejecutar(() => guardarBorrador(radicado, texto), 'Cambios guardados.')}
                  >
                    Guardar cambios
                  </button>
                  <button
                    type="button"
                    className="boton boton--menta"
                    disabled={ocupado || bloqueos.length > 0}
                    onClick={() => dialogo.current?.showModal()}
                  >
                    Aprobar y enviar respuesta
                  </button>
                </div>

                {bloqueos.length > 0 && (
                  <div className="bloqueos">
                    <p>Para poder aprobar:</p>
                    <ul>{bloqueos.map((linea) => <li key={linea}>{linea}</li>)}</ul>
                  </div>
                )}
              </>
            )}
          </section>

          {borrador && !respondida && (
            <AsistenteBorrador
              radicado={radicado}
              texto={texto}
              deshabilitado={ocupado}
              onAplicar={setTexto}
              onFuentesNuevas={refrescarFuentes}
              onSesionVencida={manejarError}
            />
          )}

          {borrador && (
            <section className="tarjeta tarjeta--tecnica caso__bloque" aria-labelledby="titulo-fuentes">
              <h2 id="titulo-fuentes" className="caso__subtitulo">
                {respondida ? 'Fuentes del borrador' : 'Fuentes citadas'}
              </h2>
              <Fuentes citas={borrador.citas} />
              <p className="fuentes-citadas__pie texto-apoyo">
                Redactado por {borrador.modelo} · {borrador.tokens_entrada.toLocaleString('es-CO')} tokens de
                entrada y {borrador.tokens_salida.toLocaleString('es-CO')} de salida.
              </p>
            </section>
          )}
        </div>
      </div>

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

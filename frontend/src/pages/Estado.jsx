import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { IconoAlerta, IconoCheck, IconoFlecha } from '../components/Iconos.jsx'
import { consultarEstado, urlRespuestaPdf } from '../services/api.js'

// Página para que el ciudadano consulte el estado de su PQRSD (US-010).
// Solo muestra estado y fechas; nunca borradores ni datos internos. Cuando ya
// está respondida, ofrece la carta aprobada en PDF.

const ETAPAS = [
  { clave: 'recibida', etiqueta: 'Recibida', detalle: 'El banco tiene su solicitud.' },
  { clave: 'en_tramite', etiqueta: 'En trámite', detalle: 'Un área del banco la está atendiendo.' },
  { clave: 'respondida', etiqueta: 'Respondida', detalle: 'La respuesta fue aprobada y enviada.' },
]

function formatearFecha(valor) {
  // Las fechas "AAAA-MM-DD" se arman a mano: new Date() las correría un día por la zona horaria.
  const [anio, mes, dia] = valor.slice(0, 10).split('-').map(Number)
  return new Date(anio, mes - 1, dia).toLocaleDateString('es-CO', {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  })
}

function mensajeDeError(e) {
  // FastAPI responde "Not Found" cuando la ruta no existe: el backend desplegado
  // todavía no incluye la consulta de estado.
  if (e.estado === 404 && e.message === 'Not Found') {
    return 'La consulta de estado todavía no está disponible en este servidor.'
  }
  return e.message
}

function Resultado({ resultado }) {
  const actual = Math.max(0, ETAPAS.findIndex((etapa) => etapa.clave === resultado.estado))
  return (
    <section role="status" className="tarjeta tarjeta--tecnica estado__resultado">
      <p className="etiqueta-tecnica texto-apoyo">Radicado</p>
      <p className="estado__radicado">{resultado.radicado}</p>
      <h2 className="encabezado estado__etiqueta">Estado: {resultado.etiqueta}</h2>

      <ol className="etapas" style={{ '--avance': actual / (ETAPAS.length - 1) }}>
        {ETAPAS.map((etapa, i) => {
          const situacion = i < actual ? 'hecha' : i === actual ? 'actual' : 'pendiente'
          return (
            <li
              key={etapa.clave}
              className="etapas__paso"
              data-situacion={situacion}
              aria-current={situacion === 'actual' ? 'step' : undefined}
              style={{ '--orden': i }}
            >
              <span className="etapas__marca" aria-hidden="true">
                {situacion !== 'pendiente' && <IconoCheck width={12} height={12} />}
              </span>
              <span className="etapas__nombre">
                {etapa.etiqueta}
                <span className="solo-lectores">
                  {situacion === 'hecha' ? ' (completada)' : situacion === 'actual' ? ' (etapa actual)' : ' (pendiente)'}
                </span>
              </span>
              <span className="etapas__detalle">{etapa.detalle}</span>
            </li>
          )
        })}
      </ol>

      <dl className="estado__fechas">
        <div>
          <dt>Radicada</dt>
          <dd>{formatearFecha(resultado.fecha_radicacion)}</dd>
        </div>
        <div>
          <dt>Fecha de vencimiento</dt>
          <dd>
            {resultado.fecha_vencimiento
              ? formatearFecha(resultado.fecha_vencimiento)
              : 'Pendiente de cálculo'}
          </dd>
        </div>
      </dl>

      {resultado.estado === 'respondida' && (
        <div className="estado__respuesta">
          <p>
            <strong>Su respuesta está lista.</strong> Es la carta que aprobó el banco, en PDF.
          </p>
          <div className="estado__respuesta-acciones">
            <a
              className="boton boton--menta"
              href={urlRespuestaPdf(resultado.radicado)}
              target="_blank"
              rel="noopener"
            >
              Ver respuesta
            </a>
            <a className="boton boton--linea" href={urlRespuestaPdf(resultado.radicado, true)} download>
              Descargar PDF
            </a>
          </div>
        </div>
      )}
    </section>
  )
}

export default function Estado() {
  const [parametros, setParametros] = useSearchParams()
  const radicadoInicial = parametros.get('radicado') || ''
  const [radicado, setRadicado] = useState(radicadoInicial)
  const [resultado, setResultado] = useState(null)
  const [error, setError] = useState(null)
  const [consultando, setConsultando] = useState(false)

  async function buscar(valor) {
    setError(null)
    setResultado(null)
    setConsultando(true)
    try {
      setResultado(await consultarEstado(valor))
    } catch (e) {
      setError(mensajeDeError(e))
    } finally {
      setConsultando(false)
    }
  }

  // Si la página se abre con ?radicado=… (desde la confirmación o el inicio), consulta de una vez.
  useEffect(() => {
    if (radicadoInicial.trim()) buscar(radicadoInicial)
  }, [radicadoInicial])

  function consultar(evento) {
    evento.preventDefault()
    const valor = radicado.trim()
    if (!valor) {
      setResultado(null)
      setError('Escriba el número de radicado que recibió al radicar.')
      return
    }
    if (valor === radicadoInicial) buscar(valor)
    else setParametros({ radicado: valor })
  }

  return (
    <div className="contenedor contenedor--angosto pagina">
      <h1 className="display-seccion pagina__titulo">Consultar el estado de su PQRSD</h1>
      <p className="pagina__bajada texto-apoyo">
        Escriba el número que recibió al radicar. Tiene esta forma: PQRSD-2026-XXXXXX.
      </p>

      <form onSubmit={consultar} noValidate className="estado__formulario">
        <div className="campo estado__campo">
          <label htmlFor="radicado" className="campo__etiqueta">Número de radicado</label>
          <input
            id="radicado"
            className="campo__control estado__entrada"
            value={radicado}
            maxLength={40}
            onChange={(e) => setRadicado(e.target.value.toUpperCase())}
            placeholder="PQRSD-2026-XXXXXX"
            autoComplete="off"
            autoCapitalize="characters"
            spellCheck={false}
            aria-invalid={Boolean(error) && !radicado.trim()}
          />
        </div>
        <button type="submit" className="boton boton--menta" disabled={consultando}>
          {consultando ? 'Consultando…' : 'Consultar estado'}
          {!consultando && <IconoFlecha />}
        </button>
      </form>

      {consultando && (
        <p className="estado__cargando texto-apoyo" role="status">
          <span className="puntos" aria-hidden="true"><span /><span /><span /></span>
          Buscando el radicado…
        </p>
      )}

      {error && (
        <p role="alert" className="aviso-error">
          <IconoAlerta />
          <span>{error}</span>
        </p>
      )}

      {resultado && <Resultado resultado={resultado} />}

      {!resultado && !error && !consultando && (
        <p className="estado__vacio texto-apoyo">
          ¿Aún no tiene un radicado? <Link className="enlace" to="/radicar">Radique su PQRSD</Link> o{' '}
          <Link className="enlace" to="/chat">pregunte primero al asistente</Link>.
        </p>
      )}
    </div>
  )
}

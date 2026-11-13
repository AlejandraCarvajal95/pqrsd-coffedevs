import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { IconoAlerta } from '../components/Iconos.jsx'
import Semaforo from '../components/Semaforo.jsx'
import {
  cerrarSesionAdmin,
  descargarCsv,
  listarBandeja,
  obtenerMetricas,
} from '../services/api.js'
import {
  ETIQUETAS_ESTADO,
  claveDeFecha,
  etiquetaTipo,
  fechaLocal,
  formatearFecha,
  formatearFechaHora,
} from '../utils/formato.js'

// Panel del equipo (US-017 y US-019): resumen, bandeja por urgencia,
// calendario de vencimientos y respuestas enviadas.

const VISTAS = [
  { clave: 'bandeja', etiqueta: 'Bandeja por vencimiento' },
  { clave: 'calendario', etiqueta: 'Calendario' },
  { clave: 'enviadas', etiqueta: 'Enviadas' },
]
const FILTROS_VACIOS = { q: '', area: '', tipo: '', semaforo: '', estado: '', riesgo_fraude: '' }
const DIAS_SEMANA = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes']
const SEMANAS_MAXIMAS = 6

function Tarjetas({ metricas }) {
  const { tarjetas, presupuesto_ia: gasto } = metricas
  const porcentaje = Math.min(100, (gasto.total_usd / gasto.tope_usd) * 100)
  return (
    <ul className="resumen">
      <li className="tarjeta tarjeta--tecnica resumen__tarjeta">
        <span className="resumen__cifra">{tarjetas.activas}</span>
        <span className="resumen__nombre">Activas</span>
        <span className="resumen__nota texto-apoyo">{tarjetas.con_borrador_listo} con borrador listo</span>
      </li>
      <li className="tarjeta tarjeta--tecnica resumen__tarjeta" data-alerta={tarjetas.por_vencer > 0}>
        <span className="resumen__cifra">{tarjetas.por_vencer}</span>
        <span className="resumen__nombre">En rojo o vencidas</span>
        <span className="resumen__nota texto-apoyo">
          {metricas.por_semaforo.vencidas} ya vencida{metricas.por_semaforo.vencidas === 1 ? '' : 's'}
        </span>
      </li>
      <li className="tarjeta tarjeta--tecnica resumen__tarjeta">
        <span className="resumen__cifra">{tarjetas.pendientes_revision}</span>
        <span className="resumen__nombre">Clasificación por revisar</span>
        <span className="resumen__nota texto-apoyo">{tarjetas.riesgo_fraude} con riesgo de fraude</span>
      </li>
      <li className="tarjeta tarjeta--tecnica resumen__tarjeta">
        <span className="resumen__cifra">{tarjetas.respondidas}</span>
        <span className="resumen__nombre">Respondidas</span>
        <span className="resumen__nota texto-apoyo">Aprobadas por una persona</span>
      </li>
      <li className="tarjeta tarjeta--grafito resumen__tarjeta resumen__tarjeta--gasto">
        <span className="resumen__cifra">
          {gasto.total_usd.toLocaleString('es-CO', { style: 'currency', currency: 'USD' })}
        </span>
        <span className="resumen__nombre">Gasto de IA</span>
        <span
          className="resumen__barra"
          role="progressbar"
          aria-label="Presupuesto de IA usado"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={Math.round(porcentaje)}
        >
          <span style={{ width: `${porcentaje}%` }} />
        </span>
        <span className="resumen__nota">
          {porcentaje.toLocaleString('es-CO', { maximumFractionDigits: 1 })} % del tope de {gasto.tope_usd} USD
          {gasto.alerta ? ' · cerca del tope' : ''}
        </span>
      </li>
    </ul>
  )
}

function Filtros({ filtros, opciones, onCambio }) {
  const cambiar = (clave) => (evento) => onCambio({ ...filtros, [clave]: evento.target.value })
  const hayFiltros = Object.values(filtros).some(Boolean)
  return (
    <form className="filtros" onSubmit={(e) => e.preventDefault()} role="search">
      <div className="filtros__campo filtros__campo--ancho">
        <label htmlFor="filtro-q" className="campo__etiqueta">Buscar</label>
        <input
          id="filtro-q"
          type="search"
          className="campo__control"
          placeholder="Radicado, asunto o texto"
          value={filtros.q}
          maxLength={120}
          onChange={cambiar('q')}
        />
      </div>
      <div className="filtros__campo">
        <label htmlFor="filtro-semaforo" className="campo__etiqueta">Semáforo</label>
        <select id="filtro-semaforo" className="campo__control" value={filtros.semaforo} onChange={cambiar('semaforo')}>
          <option value="">Todos</option>
          <option value="rojo">Urgente o vencida</option>
          <option value="amarillo">Por vencer</option>
          <option value="verde">A tiempo</option>
        </select>
      </div>
      <div className="filtros__campo">
        <label htmlFor="filtro-area" className="campo__etiqueta">Área</label>
        <select id="filtro-area" className="campo__control" value={filtros.area} onChange={cambiar('area')}>
          <option value="">Todas</option>
          {opciones.areas.map((area) => <option key={area}>{area}</option>)}
        </select>
      </div>
      <div className="filtros__campo">
        <label htmlFor="filtro-tipo" className="campo__etiqueta">Tipo</label>
        <select id="filtro-tipo" className="campo__control" value={filtros.tipo} onChange={cambiar('tipo')}>
          <option value="">Todos</option>
          {opciones.tipos.map((tipo) => <option key={tipo} value={tipo}>{etiquetaTipo(tipo)}</option>)}
        </select>
      </div>
      <div className="filtros__campo">
        <label htmlFor="filtro-estado" className="campo__etiqueta">Estado</label>
        <select id="filtro-estado" className="campo__control" value={filtros.estado} onChange={cambiar('estado')}>
          <option value="">Todas las activas</option>
          {opciones.estados
            .filter((estado) => estado !== 'respondida')
            .map((estado) => <option key={estado} value={estado}>{ETIQUETAS_ESTADO[estado]}</option>)}
        </select>
      </div>
      <div className="filtros__campo">
        <label htmlFor="filtro-fraude" className="campo__etiqueta">Riesgo de fraude</label>
        <select id="filtro-fraude" className="campo__control" value={filtros.riesgo_fraude} onChange={cambiar('riesgo_fraude')}>
          <option value="">Todos</option>
          <option value="true">Con riesgo</option>
          <option value="false">Sin riesgo</option>
        </select>
      </div>
      {hayFiltros && (
        <button type="button" className="boton boton--linea filtros__limpiar" onClick={() => onCambio(FILTROS_VACIOS)}>
          Quitar filtros
        </button>
      )}
    </form>
  )
}

function Alertas({ item }) {
  return (
    <span className="alertas">
      {item.requiere_revision && <span className="pildora" data-tono="aviso">Revisar clasificación</span>}
      {item.riesgo_fraude && <span className="pildora" data-tono="alerta">Riesgo de fraude</span>}
      {item.estado === 'clasificada' && !item.tiene_borrador && (
        <span className="pildora" data-tono="neutro">Sin borrador</span>
      )}
    </span>
  )
}

function TablaBandeja({ items }) {
  return (
    <div className="tabla-envoltura">
      <table className="tabla">
        <caption className="solo-lectores">PQRSD activas, de la más urgente a la menos urgente</caption>
        <thead>
          <tr>
            <th scope="col">Semáforo</th>
            <th scope="col">Radicado y asunto</th>
            <th scope="col">Tipo</th>
            <th scope="col">Área</th>
            <th scope="col">Vence</th>
            <th scope="col">Estado</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.radicado}>
              <td><Semaforo item={item} /></td>
              <td>
                <Link className="tabla__radicado" to={`/admin/pqrsd/${item.radicado}`}>{item.radicado}</Link>
                <span className="tabla__asunto">{item.asunto}</span>
                <Alertas item={item} />
              </td>
              <td>{etiquetaTipo(item.tipo)}</td>
              <td>{item.area || 'Sin área'}</td>
              <td className="tabla__fecha">{formatearFecha(item.fecha_vencimiento)}</td>
              <td>{ETIQUETAS_ESTADO[item.estado]}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function TablaEnviadas({ items }) {
  return (
    <div className="tabla-envoltura">
      <table className="tabla">
        <caption className="solo-lectores">PQRSD respondidas</caption>
        <thead>
          <tr>
            <th scope="col">Radicado y asunto</th>
            <th scope="col">Tipo</th>
            <th scope="col">Área</th>
            <th scope="col">Radicada</th>
            <th scope="col">Respondida</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.radicado}>
              <td>
                <Link className="tabla__radicado" to={`/admin/pqrsd/${item.radicado}`}>{item.radicado}</Link>
                <span className="tabla__asunto">{item.asunto}</span>
              </td>
              <td>{etiquetaTipo(item.tipo)}</td>
              <td>{item.area || 'Sin área'}</td>
              <td className="tabla__fecha">{formatearFecha(item.fecha_radicacion)}</td>
              <td className="tabla__fecha">{formatearFechaHora(item.fecha_respuesta)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function ChipPqrsd({ pqrsd }) {
  return (
    <Link
      className="chip-pqrsd"
      data-color={pqrsd.semaforo || 'ninguno'}
      to={`/admin/pqrsd/${pqrsd.radicado}`}
      title={pqrsd.asunto}
    >
      <span className="chip-pqrsd__radicado">{pqrsd.radicado}</span>
      <span className="chip-pqrsd__area">{pqrsd.area || 'Sin área'}</span>
    </Link>
  )
}

function Calendario({ calendario }) {
  const { vencidas, semanas } = useMemo(() => {
    const hoy = new Date()
    hoy.setHours(0, 0, 0, 0)
    const porFecha = new Map(calendario.map((dia) => [dia.fecha, dia.pqrsd]))
    const lunes = new Date(hoy)
    lunes.setDate(hoy.getDate() - ((hoy.getDay() + 6) % 7))

    const ultima = calendario.length ? fechaLocal(calendario[calendario.length - 1].fecha) : hoy
    const semanasNecesarias = Math.ceil((ultima - lunes) / (7 * 86400000) + 0.01)
    const total = Math.max(2, Math.min(SEMANAS_MAXIMAS, semanasNecesarias))

    const lista = []
    for (let s = 0; s < total; s += 1) {
      const dias = []
      for (let d = 0; d < 5; d += 1) {
        const fecha = new Date(lunes)
        fecha.setDate(lunes.getDate() + s * 7 + d)
        dias.push({
          fecha,
          esHoy: fecha.getTime() === hoy.getTime(),
          pasado: fecha < hoy,
          pqrsd: porFecha.get(claveDeFecha(fecha)) || [],
        })
      }
      lista.push(dias)
    }
    // Lo que venció antes de esta semana no cabe en la cuadrícula: va en un bloque aparte.
    const anteriores = calendario.filter((dia) => fechaLocal(dia.fecha) < lunes)
    return { vencidas: anteriores, semanas: lista }
  }, [calendario])

  if (!calendario.length) {
    return <p className="vacio texto-apoyo">No hay PQRSD activas con fecha de vencimiento.</p>
  }

  return (
    <div className="calendario">
      {vencidas.length > 0 && (
        <section className="calendario__vencidas" aria-label="Vencidas en semanas anteriores">
          <h3 className="calendario__titulo">Vencidas en semanas anteriores</h3>
          {vencidas.map((dia) => (
            <div key={dia.fecha} className="calendario__fila-vencida">
              <span className="etiqueta-tecnica">{formatearFecha(dia.fecha)}</span>
              <span className="calendario__chips">
                {dia.pqrsd.map((pqrsd) => <ChipPqrsd key={pqrsd.radicado} pqrsd={pqrsd} />)}
              </span>
            </div>
          ))}
        </section>
      )}

      <div className="calendario__cabecera" aria-hidden="true">
        {DIAS_SEMANA.map((dia) => <span key={dia}>{dia}</span>)}
      </div>
      {semanas.map((dias) => (
        <ol key={claveDeFecha(dias[0].fecha)} className="calendario__semana">
          {dias.map((dia) => (
            <li
              key={claveDeFecha(dia.fecha)}
              className="calendario__dia"
              data-hoy={dia.esHoy}
              data-pasado={dia.pasado}
              data-vacio={dia.pqrsd.length === 0}
            >
              <span className="calendario__fecha">
                <span className="calendario__nombre-dia">
                  {dia.fecha.toLocaleDateString('es-CO', { weekday: 'long' })}{' '}
                </span>
                {dia.fecha.toLocaleDateString('es-CO', { day: 'numeric', month: 'short' })}
                {dia.esHoy && <span className="pildora" data-tono="neutro">Hoy</span>}
              </span>
              {dia.pqrsd.length > 0 && (
                <>
                  <span className="calendario__total">
                    {dia.pqrsd.length} vence{dia.pqrsd.length === 1 ? '' : 'n'}
                  </span>
                  <span className="calendario__chips">
                    {dia.pqrsd.map((pqrsd) => <ChipPqrsd key={pqrsd.radicado} pqrsd={pqrsd} />)}
                  </span>
                </>
              )}
            </li>
          ))}
        </ol>
      ))}
      <p className="calendario__nota texto-apoyo">
        Se muestran los días hábiles de las próximas semanas. Los festivos aparecen sin vencimientos.
      </p>
    </div>
  )
}

export default function AdminPanel() {
  const navegar = useNavigate()
  const [vista, setVista] = useState('bandeja')
  const [filtros, setFiltros] = useState(FILTROS_VACIOS)
  const [busqueda, setBusqueda] = useState(FILTROS_VACIOS) // filtros ya asentados (con pausa al escribir)
  const [metricas, setMetricas] = useState(null)
  const [bandeja, setBandeja] = useState(null)
  const [enviadas, setEnviadas] = useState(null)
  const [error, setError] = useState(null)
  const [descargando, setDescargando] = useState(false)

  const manejarError = useCallback(
    (e) => {
      if (e.estado === 401) navegar('/admin/login', { replace: true })
      else setError(e.message)
    },
    [navegar],
  )

  // Pausa breve al escribir en el buscador para no consultar en cada tecla.
  useEffect(() => {
    const espera = setTimeout(() => setBusqueda(filtros), filtros.q === busqueda.q ? 0 : 300)
    return () => clearTimeout(espera)
  }, [filtros, busqueda.q])

  useEffect(() => {
    let vigente = true
    obtenerMetricas()
      .then((datos) => vigente && setMetricas(datos))
      .catch((e) => vigente && manejarError(e))
    listarBandeja({ estado: 'respondida' })
      .then((datos) => vigente && setEnviadas(datos.items))
      .catch((e) => vigente && manejarError(e))
    return () => {
      vigente = false
    }
  }, [manejarError])

  useEffect(() => {
    let vigente = true
    setError(null)
    listarBandeja(busqueda)
      .then((datos) => vigente && setBandeja(datos))
      .catch((e) => vigente && manejarError(e))
    return () => {
      vigente = false
    }
  }, [busqueda, manejarError])

  async function descargar() {
    setDescargando(true)
    setError(null)
    try {
      await descargarCsv()
    } catch (e) {
      manejarError(e)
    } finally {
      setDescargando(false)
    }
  }

  function salir() {
    cerrarSesionAdmin()
    navegar('/admin/login', { replace: true })
  }

  const hayFiltros = Object.values(busqueda).some(Boolean)

  return (
    <div className="contenedor pagina admin">
      <header className="admin__cabecera">
        <div>
          <p className="etiqueta-tecnica texto-apoyo">Panel de atención</p>
          <h1 className="encabezado">PQRSD por atender</h1>
        </div>
        <div className="admin__acciones">
          <button type="button" className="boton boton--linea" onClick={descargar} disabled={descargando}>
            {descargando ? 'Preparando archivo…' : 'Descargar base (CSV)'}
          </button>
          <button type="button" className="boton boton--grafito" onClick={salir}>Cerrar sesión</button>
        </div>
      </header>

      {error && (
        <p role="alert" className="aviso-error">
          <IconoAlerta />
          <span>{error}</span>
        </p>
      )}

      {metricas ? (
        <Tarjetas metricas={metricas} />
      ) : (
        !error && <p className="vacio texto-apoyo" role="status">Cargando el resumen…</p>
      )}

      <div className="pestanas" role="tablist" aria-label="Vistas del panel">
        {VISTAS.map((opcion) => (
          <button
            key={opcion.clave}
            type="button"
            role="tab"
            id={`pestana-${opcion.clave}`}
            aria-selected={vista === opcion.clave}
            aria-controls={`vista-${opcion.clave}`}
            className="pestanas__boton"
            onClick={() => setVista(opcion.clave)}
          >
            {opcion.etiqueta}
            {opcion.clave === 'enviadas' && enviadas && <span className="pestanas__conteo">{enviadas.length}</span>}
            {opcion.clave === 'bandeja' && bandeja && <span className="pestanas__conteo">{bandeja.total}</span>}
          </button>
        ))}
      </div>

      <section id={`vista-${vista}`} role="tabpanel" aria-labelledby={`pestana-${vista}`} className="admin__vista">
        {vista === 'bandeja' && (
          <>
            {bandeja && <Filtros filtros={filtros} opciones={bandeja.opciones} onCambio={setFiltros} />}
            {!bandeja && !error && <p className="vacio texto-apoyo" role="status">Cargando la bandeja…</p>}
            {bandeja && bandeja.items.length > 0 && <TablaBandeja items={bandeja.items} />}
            {bandeja && bandeja.items.length === 0 && (
              <p className="vacio texto-apoyo">
                {hayFiltros
                  ? 'Ninguna PQRSD coincide con esos filtros.'
                  : 'No hay PQRSD activas. Las nuevas aparecerán aquí al radicarse.'}
              </p>
            )}
          </>
        )}
        {vista === 'calendario' &&
          (metricas ? (
            <Calendario calendario={metricas.calendario} />
          ) : (
            !error && <p className="vacio texto-apoyo" role="status">Cargando el calendario…</p>
          ))}
        {vista === 'enviadas' && (
          <>
            {!enviadas && !error && <p className="vacio texto-apoyo" role="status">Cargando las enviadas…</p>}
            {enviadas && enviadas.length > 0 && <TablaEnviadas items={enviadas} />}
            {enviadas && enviadas.length === 0 && (
              <p className="vacio texto-apoyo">Todavía no se ha aprobado ninguna respuesta.</p>
            )}
          </>
        )}
      </section>
    </div>
  )
}

import { useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import DiagramaFlujo from '../components/DiagramaFlujo.jsx'
import { IconoCheck, IconoFlecha } from '../components/Iconos.jsx'
import { useEnVista } from '../hooks/useEnVista.js'

// Portada del portal ciudadano: explica el recorrido y lleva a las tres
// acciones que existen (asistente, radicación y consulta de estado).

const CAPACIDADES = [
  'Respuestas con sus fuentes',
  'Radicado inmediato',
  'Una persona aprueba cada respuesta',
]

const ESTACIONES = [
  {
    titulo: 'Pregunta',
    texto:
      'El asistente busca en la información oficial del banco. Si la respuesta está ahí, la recibe con sus fuentes y no tiene que radicar nada.',
  },
  {
    titulo: 'Radicación',
    texto:
      'Si necesita una respuesta formal, radica desde el mismo chat, con lo conversado ya escrito, o desde el formulario.',
  },
  {
    titulo: 'Radicado',
    texto:
      'Recibe de inmediato un número con la forma PQRSD-2026-XXXXXX. Guárdelo: con él consulta el estado de su solicitud.',
  },
  {
    titulo: 'Revisión',
    texto:
      'Una persona del banco revisa y aprueba la respuesta antes de enviársela. Nada sale sin esa aprobación.',
  },
]

// Plazos según data/conocimiento/normativa_ley_1755.md (resumen de la Ley 1755 de 2015).
const TIPOS = [
  {
    clave: 'peticion',
    nombre: 'Petición',
    definicion: 'Solicita información, documentos o que el banco haga algo.',
    ejemplo: 'Necesito el paz y salvo de mi tarjeta de crédito cancelada.',
    plazo: '15 días hábiles. Si pide documentos o información, 10.',
  },
  {
    clave: 'queja',
    nombre: 'Queja',
    definicion: 'Manifiesta su inconformidad con la atención o con la conducta de alguien del banco.',
    ejemplo: 'En la oficina no quisieron recibir mi solicitud.',
    plazo: '15 días hábiles.',
  },
  {
    clave: 'reclamo',
    nombre: 'Reclamo',
    definicion: 'Pide corregir un cobro o un servicio que no se prestó como debía.',
    ejemplo: 'Me cobraron cuota de manejo en un mes en que estaba exonerado.',
    plazo: '15 días hábiles.',
  },
  {
    clave: 'sugerencia',
    nombre: 'Sugerencia',
    definicion: 'Propone una mejora en un producto o en la atención.',
    ejemplo: 'Que el extracto llegue también por correo electrónico.',
    plazo: '15 días hábiles, por criterio del banco.',
  },
  {
    clave: 'denuncia',
    nombre: 'Denuncia',
    definicion: 'Avisa de una posible irregularidad o de un fraude.',
    ejemplo: 'Me llamaron a nombre del banco para pedirme la clave de la tarjeta.',
    plazo: '15 días hábiles.',
  },
]

function Recorrido() {
  const [ref, visible] = useEnVista(0.3)
  return (
    <section className="recorrido sobre-oscuro" aria-labelledby="titulo-recorrido">
      <div className="contenedor">
        <h2 id="titulo-recorrido" className="display-seccion recorrido__titulo">
          Qué pasa con su solicitud
        </h2>
        {/* La línea se dibuja y las estaciones se encienden en orden al entrar en pantalla. */}
        <ol ref={ref} className="ruta" data-visible={visible}>
          {ESTACIONES.map((estacion, i) => (
            <li key={estacion.titulo} className="ruta__estacion" style={{ '--orden': i }}>
              <span className="ruta__marca" aria-hidden="true" />
              <span className="etiqueta-tecnica ruta__numero">0{i + 1}</span>
              <h3 className="ruta__titulo">{estacion.titulo}</h3>
              <p className="ruta__texto">{estacion.texto}</p>
            </li>
          ))}
        </ol>
      </div>
    </section>
  )
}

function GuiaDeTipos() {
  const [activo, setActivo] = useState(0)
  const pestanas = useRef([])
  const tipo = TIPOS[activo]

  function alTeclear(evento) {
    const paso = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }[evento.key]
    let siguiente = null
    if (paso) siguiente = (activo + paso + TIPOS.length) % TIPOS.length
    if (evento.key === 'Home') siguiente = 0
    if (evento.key === 'End') siguiente = TIPOS.length - 1
    if (siguiente === null) return
    evento.preventDefault()
    setActivo(siguiente)
    pestanas.current[siguiente]?.focus()
  }

  return (
    <section className="tipos contenedor" aria-labelledby="titulo-tipos">
      <div className="tipos__intro">
        <h2 id="titulo-tipos" className="display-seccion">¿Petición, queja o reclamo?</h2>
        <div className="tipos__textos">
          <p className="texto-enfasis">
            No tiene que elegir. Describa su caso con sus palabras y el banco lo clasifica.
          </p>
          <p className="texto-apoyo">
            Esta guía solo sirve para orientarse: muestra qué es cada tipo de solicitud y en cuánto
            tiempo debe responderla el banco.
          </p>
        </div>
      </div>

      <div className="tipos__fila" role="tablist" aria-label="Tipos de solicitud" onKeyDown={alTeclear}>
        {TIPOS.map((t, i) => (
          <button
            key={t.clave}
            ref={(el) => (pestanas.current[i] = el)}
            type="button"
            role="tab"
            id={`pestana-${t.clave}`}
            aria-selected={i === activo}
            aria-controls="panel-tipo"
            tabIndex={i === activo ? 0 : -1}
            className="tipos__pestana"
            onClick={() => setActivo(i)}
          >
            {/* Las iniciales de las cinco pestañas deletrean PQRSD. */}
            <span className="tipos__mosaico" aria-hidden="true">{t.nombre[0]}</span>
            {t.nombre}
          </button>
        ))}
      </div>

      <div
        id="panel-tipo"
        role="tabpanel"
        aria-labelledby={`pestana-${tipo.clave}`}
        tabIndex={0}
        className="tarjeta tarjeta--nube tipos__panel"
      >
        {/* La clave reinicia la entrada del contenido al cambiar de pestaña. */}
        <div key={tipo.clave} className="tipos__contenido">
          <p className="encabezado tipos__definicion">{tipo.definicion}</p>
          <dl className="tipos__datos">
            <div>
              <dt className="etiqueta-tecnica">Ejemplo</dt>
              <dd>«{tipo.ejemplo}»</dd>
            </div>
            <div>
              <dt className="etiqueta-tecnica">Plazo de respuesta</dt>
              <dd>{tipo.plazo}</dd>
            </div>
          </dl>
        </div>
      </div>
      <p className="tipos__fuente texto-apoyo">
        Plazos según el resumen de la Ley 1755 de 2015 que usa el banco en esta demostración. Se
        cuentan desde el día hábil siguiente a la radicación.
      </p>
    </section>
  )
}

function Accesos() {
  const navegar = useNavigate()
  const [radicado, setRadicado] = useState('')

  function consultar(evento) {
    evento.preventDefault()
    const valor = radicado.trim()
    navegar(valor ? `/estado?radicado=${encodeURIComponent(valor)}` : '/estado')
  }

  return (
    <section className="accesos contenedor" aria-label="Accesos directos">
      <div className="tarjeta tarjeta--nube accesos__duda">
        <h2 className="encabezado">¿Tiene una duda sobre un cobro, una tarjeta o un reporte?</h2>
        <p className="texto-enfasis">
          Empiece por el asistente. Responde solo con la información oficial del banco y, si no la
          encuentra, se lo dice y le ayuda a radicar.
        </p>
        <Link to="/chat" className="boton boton--menta">
          Preguntar al asistente <IconoFlecha />
        </Link>
      </div>

      <form className="tarjeta tarjeta--grafito sobre-oscuro accesos__estado" onSubmit={consultar}>
        <h2 className="encabezado">¿Ya tiene un radicado?</h2>
        <label htmlFor="radicado-inicio" className="accesos__etiqueta">Número de radicado</label>
        <input
          id="radicado-inicio"
          className="accesos__entrada"
          value={radicado}
          maxLength={40}
          onChange={(e) => setRadicado(e.target.value.toUpperCase())}
          placeholder="PQRSD-2026-XXXXXX"
          autoComplete="off"
          spellCheck={false}
        />
        <button type="submit" className="boton boton--translucido">Consultar estado</button>
      </form>
    </section>
  )
}

export default function Inicio() {
  return (
    <>
      <section className="portada contenedor">
        <div className="portada__texto">
          <h1 className="display-portada portada__titular">
            {/* Cada renglón sube desde su máscara: el titular se lee en dos tiempos. */}
            <span className="portada__renglon"><span>Pregunte primero.</span></span>
            <span className="portada__renglon"><span>Radique si hace falta.</span></span>
          </h1>
          <p className="portada__bajada texto-apoyo">
            El asistente responde con la información oficial del banco y muestra de dónde sale cada
            respuesta. Si su caso necesita una PQRSD, queda radicada con un número para hacerle
            seguimiento.
          </p>
          <ul className="portada__capacidades">
            {CAPACIDADES.map((capacidad) => (
              <li key={capacidad}>
                <span className="mosaico-tinta" aria-hidden="true">
                  <IconoCheck width={8} height={8} strokeWidth={2.5} />
                </span>
                {capacidad}
              </li>
            ))}
          </ul>
          <div className="portada__acciones">
            <Link to="/chat" className="boton boton--menta">
              Preguntar al asistente <IconoFlecha />
            </Link>
            <Link to="/radicar" className="boton boton--linea">Radicar una PQRSD</Link>
          </div>
        </div>
        <DiagramaFlujo />
      </section>

      <Recorrido />
      <GuiaDeTipos />
      <Accesos />
    </>
  )
}

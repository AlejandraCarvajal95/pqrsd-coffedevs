import { useEffect, useState } from 'react'
import { Link, NavLink, useLocation } from 'react-router-dom'
import { obtenerSalud } from '../services/api.js'
import { Logo } from './Iconos.jsx'

// Marco común de todas las páginas: franja de aviso, cabecera y pie.

const ETIQUETAS_SALUD = {
  consultando: 'Comprobando el sistema…',
  operativo: 'Sistema en línea',
  sin_base: 'Sistema en línea, base de datos sin conexión',
  caido: 'Sistema sin conexión',
}

function EstadoSistema() {
  const [estado, setEstado] = useState('consultando')

  useEffect(() => {
    let vigente = true
    obtenerSalud()
      .then((salud) => vigente && setEstado(salud.db ? 'operativo' : 'sin_base'))
      .catch(() => vigente && setEstado('caido'))
    return () => {
      vigente = false
    }
  }, [])

  return (
    <span
      className="estado-sistema"
      data-estado={estado === 'sin_base' ? 'caido' : estado}
      role="status"
    >
      <span className="estado-sistema__punto" aria-hidden="true" />
      {ETIQUETAS_SALUD[estado]}
    </span>
  )
}

export default function Marco({ children }) {
  const { pathname } = useLocation()

  useEffect(() => {
    window.scrollTo(0, 0)
  }, [pathname])

  return (
    <>
      <a className="saltar" href="#contenido">Saltar al contenido</a>
      <p className="franja-aviso">
        Demostración académica: Banco Andino Ficticio es una entidad inventada. Use solo datos ficticios.
      </p>
      <header className="cabecera">
        <div className="contenedor cabecera__fila">
          <Link to="/" className="marca">
            <Logo />
            <span className="marca__nombre">
              Banco Andino Ficticio
              <span className="marca__sello">PQRSD</span>
            </span>
          </Link>
          <nav className="navegacion" aria-label="Principal">
            <NavLink to="/chat" className="navegacion__enlace">Asistente virtual</NavLink>
            <NavLink to="/estado" className="navegacion__enlace">Consultar estado</NavLink>
          </nav>
          <Link to="/radicar" className="boton boton--grafito cabecera__accion">Radicar PQRSD</Link>
        </div>
      </header>
      {/* La clave por ruta repite la animación de entrada del contenido al navegar. */}
      <main id="contenido" className="principal" key={pathname}>
        {children}
      </main>
      <footer className="pie">
        <div className="contenedor pie__fila">
          <p className="pie__texto">
            Banco Andino Ficticio no existe. Este portal es un proyecto del equipo Coffee Devs para un
            hackathon y todas sus cifras, contratos y casos son inventados.
          </p>
          <div className="pie__lado">
            <EstadoSistema />
            <a className="boton boton--lima" href="/api/docs">Documentación de la API</a>
          </div>
        </div>
      </footer>
    </>
  )
}

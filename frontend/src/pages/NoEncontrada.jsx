import { Link } from 'react-router-dom'
import { IconoFlecha } from '../components/Iconos.jsx'

export default function NoEncontrada() {
  return (
    <div className="contenedor contenedor--angosto pagina">
      <p className="etiqueta-tecnica texto-apoyo">Error 404</p>
      <h1 className="display-seccion pagina__titulo">Esta página no existe</h1>
      <p className="pagina__bajada texto-apoyo">
        La dirección que abrió no corresponde a ninguna página del portal. Desde el inicio puede
        preguntar al asistente, radicar una PQRSD o consultar su estado.
      </p>
      <Link to="/" className="boton boton--menta pagina__accion">
        Volver al inicio <IconoFlecha />
      </Link>
    </div>
  )
}

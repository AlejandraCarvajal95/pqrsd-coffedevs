import { Link } from 'react-router-dom'
import FormularioPqrsd from '../components/FormularioPqrsd.jsx'

// Página de radicación con formulario (US-007).
export default function Radicar() {
  return (
    <div className="contenedor pagina radicar">
      <div className="radicar__intro">
        <h1 className="display-seccion pagina__titulo">Radicar una PQRSD</h1>
        <p className="pagina__bajada texto-apoyo">
          Presente su petición, queja, reclamo, sugerencia o denuncia. No escriba su cédula,
          números de tarjeta ni claves: este portal es una demostración.
        </p>
        <h2 className="radicar__subtitulo">Después de enviar</h2>
        <ol className="radicar__pasos">
          <li>
            <span className="etiqueta-tecnica">01</span>
            Recibe de inmediato un número de radicado.
          </li>
          <li>
            <span className="etiqueta-tecnica">02</span>
            El banco clasifica su solicitud y la asigna al área que corresponde.
          </li>
          <li>
            <span className="etiqueta-tecnica">03</span>
            Una persona revisa y aprueba la respuesta antes de enviársela.
          </li>
        </ol>
        <p className="texto-apoyo radicar__alterna">
          ¿Solo tiene una duda? <Link className="enlace" to="/chat">Pregunte primero al asistente</Link>:
          puede que la resuelva sin radicar.
        </p>
      </div>
      <div className="tarjeta tarjeta--tecnica radicar__formulario">
        <FormularioPqrsd canal="formulario" />
      </div>
    </div>
  )
}

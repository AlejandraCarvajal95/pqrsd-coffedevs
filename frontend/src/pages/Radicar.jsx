import { Link } from 'react-router-dom'
import FormularioPqrsd from '../components/FormularioPqrsd.jsx'
import { IconoFlecha } from '../components/Iconos.jsx'

// Página de radicación. Ofrece dos caminos para llegar a la misma PQRSD: con el
// asistente (US-008, el ciudadano cuenta su caso y el agente arma los campos) o
// por su cuenta con el formulario (US-007).
export default function Radicar() {
  return (
    <div className="contenedor pagina">
      <h1 className="display-seccion pagina__titulo">Radicar una PQRSD</h1>
      <p className="pagina__bajada texto-apoyo">
        Presente su petición, queja, reclamo, sugerencia o denuncia. Elija cómo prefiere hacerlo.
        No escriba su cédula, números de tarjeta ni claves: este portal es una demostración.
      </p>

      <section className="caminos" aria-label="Cómo radicar">
        <article className="tarjeta tarjeta--nube camino">
          <p className="etiqueta-tecnica camino__sello">Si no sabe cómo redactarla</p>
          <h2 className="encabezado camino__titulo">Con el asistente</h2>
          <p>
            Cuente qué pasó con sus palabras. El asistente le va preguntando lo que falta y arma
            su PQRSD; usted revisa el resumen antes de radicar.
          </p>
          <Link to="/radicar/chat" className="boton boton--menta">
            Radicar con el asistente <IconoFlecha />
          </Link>
        </article>

        <article className="tarjeta tarjeta--tecnica camino">
          <p className="etiqueta-tecnica camino__sello">Si ya sabe qué escribir</p>
          <h2 className="encabezado camino__titulo">Por mi cuenta</h2>
          <p>
            Llene usted mismo los campos de la solicitud: nombre, contacto, asunto y descripción.
          </p>
          <a href="#formulario" className="boton boton--linea">Llenar el formulario</a>
        </article>
      </section>

      <p className="texto-apoyo radicar__alterna">
        ¿Solo tiene una duda? <Link className="enlace" to="/chat">Pregunte primero al asistente</Link>:
        puede que la resuelva sin radicar.
      </p>

      <div className="radicar" id="formulario">
        <div className="radicar__intro">
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
        </div>
        <div className="tarjeta tarjeta--tecnica radicar__formulario">
          <h2 className="encabezado radicar__titulo">Por mi cuenta: llene el formulario</h2>
          <FormularioPqrsd canal="formulario" />
        </div>
      </div>
    </div>
  )
}

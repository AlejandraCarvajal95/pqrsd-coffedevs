import { useRef, useState } from 'react'
import { guardarAprendizaje } from '../services/api.js'
import { IconoAlerta } from './Iconos.jsx'

// Guardar un aprendizaje en la base de conocimiento (US-023): la regla o
// corrección que la persona aplicó en este caso queda como un documento que
// la IA podrá citar en casos futuros. Disponible antes y después de aprobar.

const VACIO = { titulo: '', contenido: '' }

export default function Aprendizaje({ radicado, areas, areaInicial, onGuardado, onSesionVencida }) {
  const dialogo = useRef(null)
  const [datos, setDatos] = useState(VACIO)
  const [area, setArea] = useState(areaInicial || '')
  const [error, setError] = useState(null)
  const [guardando, setGuardando] = useState(false)

  function abrir() {
    setError(null)
    setArea(areaInicial || '')
    dialogo.current?.showModal()
  }

  async function guardar(evento) {
    evento.preventDefault()
    if (datos.titulo.trim().length < 3 || datos.contenido.trim().length < 10) {
      setError('Escriba un título y explique el criterio (al menos una frase).')
      return
    }
    setError(null)
    setGuardando(true)
    try {
      const respuesta = await guardarAprendizaje(radicado, {
        titulo: datos.titulo,
        contenido: datos.contenido,
        area: area || null,
      })
      dialogo.current?.close()
      setDatos(VACIO)
      onGuardado?.(
        `Aprendizaje guardado: la base de conocimiento se actualizó en vivo (${respuesta.archivo}, ` +
          `${respuesta.total_fragmentos} fragmentos en total).`,
      )
    } catch (e) {
      if (e.estado === 401) onSesionVencida?.(e)
      else setError(e.message)
    } finally {
      setGuardando(false)
    }
  }

  return (
    <section className="tarjeta tarjeta--tecnica caso__bloque aprendizaje" aria-labelledby="titulo-aprendizaje">
      <h2 id="titulo-aprendizaje" className="caso__subtitulo">Aprendizaje del equipo</h2>
      <p className="aprendizaje__bajada texto-apoyo">
        Si en este caso aplicó un criterio o una corrección que sirve para otros, guárdelo: la IA
        podrá citarlo en los próximos borradores.
      </p>
      <button type="button" className="boton boton--linea" onClick={abrir}>
        Guardar aprendizaje en la base de conocimiento
      </button>

      <dialog ref={dialogo} className="dialogo dialogo--ancho" aria-labelledby="titulo-dialogo-aprendizaje">
        <form onSubmit={guardar} noValidate>
          <h2 id="titulo-dialogo-aprendizaje" className="dialogo__titulo">Guardar un aprendizaje</h2>
          <p className="texto-apoyo">
            Escriba la regla como una instrucción general. No incluya nombres ni datos del
            ciudadano: este texto lo podrán leer y citar otros casos.
          </p>

          <div className="campo">
            <label htmlFor="aprendizaje-titulo" className="campo__etiqueta">Título</label>
            <input
              id="aprendizaje-titulo"
              className="campo__control"
              value={datos.titulo}
              maxLength={120}
              placeholder="Por ejemplo: Reversión de cobros dobles de cuota de manejo"
              onChange={(e) => setDatos({ ...datos, titulo: e.target.value })}
            />
          </div>
          <div className="campo">
            <label htmlFor="aprendizaje-area" className="campo__etiqueta">Área</label>
            <select
              id="aprendizaje-area"
              className="campo__control"
              value={area}
              onChange={(e) => setArea(e.target.value)}
            >
              <option value="">General (todas las áreas)</option>
              {areas.map((valor) => <option key={valor}>{valor}</option>)}
            </select>
          </div>
          <div className="campo">
            <label htmlFor="aprendizaje-contenido" className="campo__etiqueta">Regla o criterio aprendido</label>
            <textarea
              id="aprendizaje-contenido"
              className="campo__control"
              rows={6}
              maxLength={3000}
              value={datos.contenido}
              placeholder="Qué se debe hacer o decir en casos como este, y por qué."
              onChange={(e) => setDatos({ ...datos, contenido: e.target.value })}
            />
          </div>

          {error && (
            <p role="alert" className="aviso-error">
              <IconoAlerta />
              <span>{error}</span>
            </p>
          )}

          <div className="dialogo__acciones">
            <button type="button" className="boton boton--linea" onClick={() => dialogo.current?.close()}>
              Cancelar
            </button>
            <button type="submit" className="boton boton--menta" disabled={guardando}>
              {guardando ? 'Guardando…' : 'Guardar aprendizaje'}
            </button>
          </div>
        </form>
      </dialog>
    </section>
  )
}

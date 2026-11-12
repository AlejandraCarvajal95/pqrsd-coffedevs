import { useState } from 'react'
import { Link } from 'react-router-dom'
import { consultarEstado } from '../services/api.js'
import { estilosFormulario } from '../components/FormularioPqrsd.jsx'

// Página para que el ciudadano consulte el estado de su PQRSD (US-010).
// Solo muestra estado y fechas; nunca borradores ni datos internos.

const COLORES_ESTADO = {
  recibida: { fondo: '#e8f0fb', texto: '#1a4fa0' },
  en_tramite: { fondo: '#fff4e0', texto: '#8a5a00' },
  respondida: { fondo: '#e7f4ea', texto: '#1d5b2c' },
}

function formatearFecha(valor) {
  // Las fechas "AAAA-MM-DD" se arman a mano: new Date() las correría un día por la zona horaria.
  const [anio, mes, dia] = valor.slice(0, 10).split('-').map(Number)
  return new Date(anio, mes - 1, dia).toLocaleDateString('es-CO', {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  })
}

export default function Estado() {
  const [radicado, setRadicado] = useState('')
  const [resultado, setResultado] = useState(null)
  const [error, setError] = useState(null)
  const [consultando, setConsultando] = useState(false)

  async function consultar(evento) {
    evento.preventDefault()
    setError(null)
    setResultado(null)
    if (!radicado.trim()) {
      setError('Escriba el número de radicado que recibió al radicar.')
      return
    }
    setConsultando(true)
    try {
      setResultado(await consultarEstado(radicado))
    } catch (e) {
      setError(e.message)
    } finally {
      setConsultando(false)
    }
  }

  const colores = resultado && (COLORES_ESTADO[resultado.estado] || COLORES_ESTADO.recibida)

  return (
    <main style={{ fontFamily: 'system-ui, sans-serif', maxWidth: 640, margin: '2rem auto', padding: '0 1rem', color: '#1a1a1a' }}>
      <p><Link to="/">Inicio</Link> · <Link to="/chat">Asistente virtual</Link> · <Link to="/radicar">Radicar</Link></p>
      <h1 style={{ marginBottom: '0.25rem' }}>Consultar el estado de mi PQRSD</h1>
      <p style={{ color: '#555' }}>
        Escriba el número de radicado que recibió al radicar, por ejemplo PQRSD-2026-ABC234.
      </p>

      <form onSubmit={consultar} noValidate>
        <label htmlFor="radicado" style={estilosFormulario.etiqueta}>Número de radicado</label>
        <input
          id="radicado"
          style={estilosFormulario.campo}
          value={radicado}
          maxLength={40}
          onChange={(e) => setRadicado(e.target.value)}
          placeholder="PQRSD-2026-XXXXXX"
          autoComplete="off"
        />
        <button type="submit" style={estilosFormulario.boton} disabled={consultando}>
          {consultando ? 'Consultando…' : 'Consultar'}
        </button>
      </form>

      {error && (
        <p role="alert" style={estilosFormulario.error}>{error}</p>
      )}

      {resultado && (
        <section
          role="status"
          style={{ background: colores.fondo, color: colores.texto, borderRadius: 8, padding: '1rem', marginTop: '1rem' }}
        >
          <p style={{ margin: 0 }}>Radicado <strong>{resultado.radicado}</strong></p>
          <p style={{ fontSize: '1.4rem', margin: '0.4rem 0' }}>
            Estado: <strong>{resultado.etiqueta}</strong>
          </p>
          <p style={{ margin: '0.2rem 0' }}>
            Radicada el {formatearFecha(resultado.fecha_radicacion)}
          </p>
          <p style={{ margin: '0.2rem 0' }}>
            Fecha de vencimiento:{' '}
            {resultado.fecha_vencimiento
              ? formatearFecha(resultado.fecha_vencimiento)
              : 'pendiente de cálculo'}
          </p>
        </section>
      )}
    </main>
  )
}

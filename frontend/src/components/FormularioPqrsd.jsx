import { useState } from 'react'
import { radicarPqrsd } from '../services/api.js'

// Formulario de radicación (US-007). Lo usan la página /radicar y el chat de
// desvío (canal "chat"), que lo abre con asunto y descripción ya sugeridos.

const MAX_DESCRIPCION = 4000

const CAMPOS = [
  { nombre: 'nombre_ciudadano', etiqueta: 'Nombre', tipo: 'input', max: 200, ayuda: 'Use un nombre ficticio.' },
  { nombre: 'contacto', etiqueta: 'Correo o teléfono de contacto', tipo: 'input', max: 200, ayuda: 'Ficticio, por ejemplo nombre@ejemplo.test o 300 000 0000.' },
  { nombre: 'asunto', etiqueta: 'Asunto', tipo: 'input', max: 300 },
  { nombre: 'descripcion', etiqueta: 'Descripción de su solicitud', tipo: 'textarea', max: MAX_DESCRIPCION },
]

export const estilosFormulario = {
  campo: { width: '100%', boxSizing: 'border-box', padding: '0.6rem', fontSize: '1rem', borderRadius: 6, border: '1px solid #999', fontFamily: 'inherit' },
  campoInvalido: { borderColor: '#b3261e', borderWidth: 2 },
  etiqueta: { display: 'block', fontWeight: 600, marginTop: '0.9rem' },
  ayuda: { fontSize: '0.85rem', color: '#555', margin: '0.2rem 0 0.3rem' },
  boton: { padding: '0.6rem 1.1rem', borderRadius: 6, border: '1px solid #1a4fa0', background: '#1a4fa0', color: '#fff', cursor: 'pointer', fontSize: '1rem', marginTop: '1rem' },
  error: { background: '#fdecea', color: '#8a1c1c', border: '1px solid #f5c2c0', borderRadius: 6, padding: '0.6rem 0.9rem', marginTop: '1rem' },
  exito: { background: '#e7f4ea', color: '#1d5b2c', border: '1px solid #b9dfc2', borderRadius: 8, padding: '1rem', marginTop: '1rem' },
}

export function Confirmacion({ resultado }) {
  return (
    <section role="status" style={estilosFormulario.exito}>
      <h2 style={{ marginTop: 0, fontSize: '1.2rem' }}>Su PQRSD fue radicada</h2>
      <p style={{ fontSize: '1.3rem', margin: '0.4rem 0' }}>
        Número de radicado: <strong>{resultado.radicado}</strong>
      </p>
      <p style={{ margin: 0 }}>{resultado.mensaje}</p>
    </section>
  )
}

export default function FormularioPqrsd({ valoresIniciales = {}, canal = 'formulario', alRadicar }) {
  const [valores, setValores] = useState({
    nombre_ciudadano: '',
    contacto: '',
    asunto: '',
    descripcion: '',
    ...valoresIniciales,
  })
  const [invalidos, setInvalidos] = useState([])
  const [error, setError] = useState(null)
  const [enviando, setEnviando] = useState(false)
  const [resultado, setResultado] = useState(null)

  function cambiar(nombre, valor) {
    setValores((previos) => ({ ...previos, [nombre]: valor }))
    setInvalidos((previos) => previos.filter((campo) => campo !== nombre))
  }

  async function enviar(evento) {
    evento.preventDefault()
    setError(null)
    // Validación local: evita enviar si falta algo obligatorio.
    const vacios = CAMPOS.filter((c) => !valores[c.nombre].trim()).map((c) => c.nombre)
    if (vacios.length) {
      setInvalidos(vacios)
      const nombres = CAMPOS.filter((c) => vacios.includes(c.nombre)).map((c) => c.etiqueta.toLowerCase())
      setError(`Complete los campos obligatorios: ${nombres.join(', ')}.`)
      return
    }
    setEnviando(true)
    try {
      const datos = await radicarPqrsd({ ...valores, canal })
      setResultado(datos)
      alRadicar?.(datos)
    } catch (e) {
      setError(e.message)
      setInvalidos(e.campos || [])
    } finally {
      setEnviando(false)
    }
  }

  if (resultado) return <Confirmacion resultado={resultado} />

  return (
    <form onSubmit={enviar} noValidate>
      {CAMPOS.map((campo) => {
        const invalido = invalidos.includes(campo.nombre)
        const props = {
          id: campo.nombre,
          value: valores[campo.nombre],
          maxLength: campo.max,
          required: true,
          'aria-invalid': invalido,
          'aria-describedby': campo.ayuda ? `${campo.nombre}-ayuda` : undefined,
          onChange: (e) => cambiar(campo.nombre, e.target.value),
          style: { ...estilosFormulario.campo, ...(invalido ? estilosFormulario.campoInvalido : {}) },
        }
        return (
          <div key={campo.nombre}>
            <label htmlFor={campo.nombre} style={estilosFormulario.etiqueta}>
              {campo.etiqueta} <span aria-hidden="true">*</span>
            </label>
            {campo.ayuda && (
              <p id={`${campo.nombre}-ayuda`} style={estilosFormulario.ayuda}>{campo.ayuda}</p>
            )}
            {campo.tipo === 'textarea' ? (
              <>
                <textarea {...props} style={{ ...props.style, minHeight: 160 }} />
                <p style={estilosFormulario.ayuda}>{valores[campo.nombre].length}/{campo.max}</p>
              </>
            ) : (
              <input {...props} />
            )}
          </div>
        )
      })}
      {error && <p role="alert" style={estilosFormulario.error}>{error}</p>}
      <button type="submit" style={estilosFormulario.boton} disabled={enviando}>
        {enviando ? 'Radicando…' : 'Radicar'}
      </button>
    </form>
  )
}

import { useState } from 'react'
import { Link } from 'react-router-dom'
import { radicarPqrsd } from '../services/api.js'
import { IconoAlerta, IconoCheck, IconoCopiar, IconoFlecha } from './Iconos.jsx'

// Formulario de radicación (US-007). Lo usan la página /radicar y el chat de
// desvío (canal "chat"), que lo abre con asunto y descripción ya sugeridos.

const MAX_DESCRIPCION = 4000

const CAMPOS = [
  { nombre: 'nombre_ciudadano', etiqueta: 'Nombre', tipo: 'input', max: 200, ayuda: 'Use un nombre ficticio.', autoComplete: 'off' },
  { nombre: 'contacto', etiqueta: 'Correo o teléfono de contacto', tipo: 'input', max: 200, ayuda: 'Ficticio, por ejemplo nombre@ejemplo.test o 300 000 0000.', autoComplete: 'off' },
  { nombre: 'asunto', etiqueta: 'Asunto', tipo: 'input', max: 300 },
  { nombre: 'descripcion', etiqueta: 'Descripción de su solicitud', tipo: 'textarea', max: MAX_DESCRIPCION },
]

function formatearFechaHora(valor) {
  return new Date(valor).toLocaleString('es-CO', { dateStyle: 'long', timeStyle: 'short' })
}

export function Confirmacion({ resultado }) {
  const [copiado, setCopiado] = useState(false)

  async function copiar() {
    try {
      await navigator.clipboard.writeText(resultado.radicado)
      setCopiado(true)
      setTimeout(() => setCopiado(false), 2500)
    } catch {
      // Sin permiso de portapapeles: el número sigue visible y se puede seleccionar.
    }
  }

  return (
    <section role="status" className="tarjeta tarjeta--grafito sobre-oscuro confirmacion">
      <h2 className="encabezado">Su PQRSD fue radicada</h2>
      <p className="confirmacion__rotulo etiqueta-tecnica">Número de radicado</p>
      <p className="confirmacion__numero">
        <span className="solo-lectores">{resultado.radicado}</span>
        {/* Las letras caen una a una: marca el momento en que el número queda asignado. */}
        <span aria-hidden="true">
          {resultado.radicado.split('').map((letra, i) => (
            <span key={i} className="confirmacion__letra" style={{ animationDelay: `${i * 35}ms` }}>
              {letra}
            </span>
          ))}
        </span>
      </p>
      <p className="confirmacion__mensaje">{resultado.mensaje}</p>
      {resultado.fecha_radicacion && (
        <p className="confirmacion__fecha etiqueta-tecnica">
          Radicada el {formatearFechaHora(resultado.fecha_radicacion)}
        </p>
      )}
      <div className="confirmacion__acciones">
        <button type="button" className="boton boton--menta" onClick={copiar}>
          {copiado ? <IconoCheck /> : <IconoCopiar />}
          {copiado ? 'Radicado copiado' : 'Copiar radicado'}
        </button>
        <Link
          className="boton boton--translucido"
          to={`/estado?radicado=${encodeURIComponent(resultado.radicado)}`}
        >
          Consultar su estado
        </Link>
      </div>
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
      document.getElementById(`${canal}-${vacios[0]}`)?.focus()
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
    <form onSubmit={enviar} noValidate className="formulario">
      <p className="formulario__nota">Todos los campos son obligatorios.</p>
      {CAMPOS.map((campo) => {
        // El id lleva el canal: el formulario puede aparecer en /radicar y dentro del chat.
        const id = `${canal}-${campo.nombre}`
        const invalido = invalidos.includes(campo.nombre)
        const props = {
          id,
          className: 'campo__control',
          value: valores[campo.nombre],
          maxLength: campo.max,
          required: true,
          autoComplete: campo.autoComplete,
          'aria-invalid': invalido,
          'aria-describedby': campo.ayuda ? `${id}-ayuda` : undefined,
          onChange: (e) => cambiar(campo.nombre, e.target.value),
        }
        return (
          <div key={campo.nombre} className="campo">
            <label htmlFor={id} className="campo__etiqueta">{campo.etiqueta}</label>
            {campo.ayuda && <p id={`${id}-ayuda`} className="campo__ayuda">{campo.ayuda}</p>}
            {campo.tipo === 'textarea' ? (
              <>
                <textarea {...props} />
                <p className="campo__pie etiqueta-tecnica">
                  <span>{invalido ? 'Revise este campo' : ''}</span>
                  <span>{valores[campo.nombre].length}/{campo.max}</span>
                </p>
              </>
            ) : (
              <>
                <input {...props} />
                {invalido && <p className="campo__pie etiqueta-tecnica campo__pie--error">Revise este campo</p>}
              </>
            )}
          </div>
        )
      })}
      {error && (
        <p role="alert" className="aviso-error">
          <IconoAlerta />
          <span>{error}</span>
        </p>
      )}
      <button type="submit" className="boton boton--menta formulario__enviar" disabled={enviando}>
        {enviando ? 'Radicando…' : 'Radicar PQRSD'}
        {!enviando && <IconoFlecha />}
      </button>
    </form>
  )
}

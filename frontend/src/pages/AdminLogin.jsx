import { useEffect, useState } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'
import { IconoAlerta, IconoFlecha } from '../components/Iconos.jsx'
import { iniciarSesionAdmin, obtenerModoAdmin, tokenAdmin } from '../services/api.js'

// Acceso al panel del equipo del banco (US-022).

export default function AdminLogin() {
  const navegar = useNavigate()
  const destino = useLocation().state?.desde || '/admin'
  const [usuario, setUsuario] = useState('')
  const [clave, setClave] = useState('')
  const [modo, setModo] = useState(null)
  const [error, setError] = useState(null)
  const [enviando, setEnviando] = useState(false)

  useEffect(() => {
    let vigente = true
    obtenerModoAdmin()
      .then((datos) => vigente && setModo(datos))
      .catch(() => {})
    return () => {
      vigente = false
    }
  }, [])

  if (tokenAdmin()) return <Navigate to={destino} replace />

  async function entrar(evento) {
    evento.preventDefault()
    if (!usuario.trim() || !clave) {
      setError('Escriba el usuario y la clave.')
      return
    }
    setError(null)
    setEnviando(true)
    try {
      await iniciarSesionAdmin(usuario, clave)
      navegar(destino, { replace: true })
    } catch (e) {
      setError(e.message)
    } finally {
      setEnviando(false)
    }
  }

  return (
    <div className="contenedor contenedor--angosto pagina admin-login">
      <p className="etiqueta-tecnica texto-apoyo">Uso interno del banco</p>
      <h1 className="display-seccion pagina__titulo">Panel de atención de PQRSD</h1>
      <p className="pagina__bajada texto-apoyo">
        Aquí el equipo revisa las solicitudes, corrige el borrador que propone la IA y aprueba la
        respuesta. Nada llega al ciudadano sin esa aprobación.
      </p>

      {modo && !modo.disponible && (
        <p role="alert" className="aviso-error">
          <IconoAlerta />
          <span>
            El panel no está configurado en este servidor. Defina ADMIN_CLAVE en el archivo .env y
            reinicie el backend.
          </span>
        </p>
      )}

      <form onSubmit={entrar} noValidate className="tarjeta tarjeta--tecnica admin-login__formulario">
        <div className="campo">
          <label htmlFor="usuario" className="campo__etiqueta">Usuario</label>
          <input
            id="usuario"
            className="campo__control"
            value={usuario}
            maxLength={100}
            onChange={(e) => setUsuario(e.target.value)}
            autoComplete="username"
            autoCapitalize="none"
            spellCheck={false}
          />
        </div>
        <div className="campo">
          <label htmlFor="clave" className="campo__etiqueta">Clave</label>
          <input
            id="clave"
            type="password"
            className="campo__control"
            value={clave}
            maxLength={200}
            onChange={(e) => setClave(e.target.value)}
            autoComplete="current-password"
          />
        </div>

        {error && (
          <p role="alert" className="aviso-error">
            <IconoAlerta />
            <span>{error}</span>
          </p>
        )}

        <button type="submit" className="boton boton--menta admin-login__entrar" disabled={enviando}>
          {enviando ? 'Entrando…' : 'Entrar al panel'}
          {!enviando && <IconoFlecha />}
        </button>
      </form>

      {modo?.credenciales_demo && (
        <p className="admin-login__demo texto-apoyo">
          Entorno de desarrollo. Credenciales de demostración: usuario{' '}
          <code>{modo.usuario_demo}</code>, clave <code>{modo.clave_demo}</code>. En el servidor del
          evento se reemplazan con ADMIN_CLAVE.
        </p>
      )}
    </div>
  )
}

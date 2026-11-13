import { useEffect, useRef, useState } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'
import { IconoAlerta, IconoFlecha } from '../components/Iconos.jsx'
import { iniciarSesionAdmin, obtenerModoAdmin, tokenAdmin } from '../services/api.js'

// Acceso al panel del equipo del banco (US-022).

// Lo que hace el equipo dentro del panel, en el orden en que ocurre.
const TAREAS = [
  'Revisar cada solicitud con su clasificación y su fecha de vencimiento.',
  'Corregir el borrador de respuesta que propone la IA.',
  'Aprobar la respuesta: sin ese paso nada llega al ciudadano.',
]

export default function AdminLogin() {
  const navegar = useNavigate()
  const destino = useLocation().state?.desde || '/admin'
  const [usuario, setUsuario] = useState('')
  const [clave, setClave] = useState('')
  const [claveVisible, setClaveVisible] = useState(false)
  const [modo, setModo] = useState(null)
  const [error, setError] = useState(null)
  const [invalidos, setInvalidos] = useState([])
  const [enviando, setEnviando] = useState(false)
  const campoUsuario = useRef(null)
  const campoClave = useRef(null)

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
    const vacios = []
    if (!usuario.trim()) vacios.push('usuario')
    if (!clave) vacios.push('clave')
    if (vacios.length) {
      setInvalidos(vacios)
      setError('Escriba el usuario y la clave.')
      const primero = vacios[0] === 'usuario' ? campoUsuario : campoClave
      primero.current?.focus()
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

  function usarDemo() {
    setUsuario(modo.usuario_demo)
    setClave(modo.clave_demo)
    setInvalidos([])
    setError(null)
  }

  return (
    <div className="contenedor pagina admin-login">
      <div className="tarjeta admin-login__marco">
        <section className="admin-login__panel sobre-oscuro">
          <p className="etiqueta-tecnica admin-login__rotulo">Uso interno del banco</p>
          <h1 className="admin-login__titulo">Panel de atención de PQRSD</h1>
          <p className="admin-login__bajada">La IA propone y una persona del equipo decide.</p>
          <ol className="admin-login__tareas">
            {TAREAS.map((tarea, i) => (
              <li key={tarea} style={{ animationDelay: `${160 + i * 90}ms` }}>
                <span className="etiqueta-tecnica" aria-hidden="true">0{i + 1}</span>
                {tarea}
              </li>
            ))}
          </ol>
        </section>

        <section className="admin-login__acceso">
          <h2 className="encabezado">Ingresar</h2>
          <p className="texto-apoyo admin-login__nota">Con el usuario y la clave del equipo.</p>

          {modo && !modo.disponible && (
            <p role="alert" className="aviso-error">
              <IconoAlerta />
              <span>
                El panel no está configurado en este servidor. Defina ADMIN_CLAVE en el archivo .env
                y reinicie el backend.
              </span>
            </p>
          )}

          <form onSubmit={entrar} noValidate>
            <div className="campo">
              <label htmlFor="usuario" className="campo__etiqueta">Usuario</label>
              <input
                id="usuario"
                ref={campoUsuario}
                className="campo__control"
                value={usuario}
                maxLength={100}
                onChange={(e) => {
                  setUsuario(e.target.value)
                  setInvalidos((previos) => previos.filter((c) => c !== 'usuario'))
                }}
                aria-invalid={invalidos.includes('usuario')}
                autoComplete="username"
                autoCapitalize="none"
                spellCheck={false}
              />
            </div>
            <div className="campo">
              <label htmlFor="clave" className="campo__etiqueta">Clave</label>
              <div className="admin-login__clave">
                <input
                  id="clave"
                  ref={campoClave}
                  type={claveVisible ? 'text' : 'password'}
                  className="campo__control"
                  value={clave}
                  maxLength={200}
                  onChange={(e) => {
                    setClave(e.target.value)
                    setInvalidos((previos) => previos.filter((c) => c !== 'clave'))
                  }}
                  aria-invalid={invalidos.includes('clave')}
                  autoComplete="current-password"
                  autoCapitalize="none"
                  spellCheck={false}
                />
                <button
                  type="button"
                  className="admin-login__ver"
                  aria-pressed={claveVisible}
                  aria-label="Mostrar la clave"
                  onClick={() => setClaveVisible((visible) => !visible)}
                >
                  {claveVisible ? 'Ocultar' : 'Mostrar'}
                </button>
              </div>
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
            <div className="admin-login__demo">
              <p className="etiqueta-tecnica">Entorno de desarrollo</p>
              <dl>
                <div>
                  <dt>Usuario</dt>
                  <dd>{modo.usuario_demo}</dd>
                </div>
                <div>
                  <dt>Clave</dt>
                  <dd>{modo.clave_demo}</dd>
                </div>
              </dl>
              <button type="button" className="boton boton--linea" onClick={usarDemo}>
                Usar estas credenciales
              </button>
              <p className="admin-login__demo-nota">
                En el servidor del evento se reemplazan con ADMIN_CLAVE.
              </p>
            </div>
          )}
        </section>
      </div>
    </div>
  )
}

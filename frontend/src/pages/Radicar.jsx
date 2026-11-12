import { Link } from 'react-router-dom'
import FormularioPqrsd from '../components/FormularioPqrsd.jsx'

// Página de radicación con formulario (US-007).
export default function Radicar() {
  return (
    <main style={{ fontFamily: 'system-ui, sans-serif', maxWidth: 640, margin: '2rem auto', padding: '0 1rem', color: '#1a1a1a' }}>
      <p><Link to="/">Inicio</Link> · <Link to="/chat">Asistente virtual</Link> · <Link to="/radicar/chat">Radicar contándole mi caso al asistente</Link></p>
      <h1 style={{ marginBottom: '0.25rem' }}>Radicar una PQRSD</h1>
      <p style={{ color: '#555' }}>
        Presente su petición, queja, reclamo, sugerencia o denuncia. Al enviarla recibirá un
        número de radicado. Use solo datos ficticios: no escriba su cédula, números de tarjeta ni
        claves.
      </p>
      <FormularioPqrsd canal="formulario" />
    </main>
  )
}

import { useEffect, useState } from 'react'
import { Route, Routes } from 'react-router-dom'
import { obtenerSalud } from './services/api.js'

// Pantalla inicial: solo comprueba que el backend y la base respondan.
// Las páginas del producto (radicar, bandeja, métricas) son de otras historias.
function EstadoSistema() {
  const [salud, setSalud] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    obtenerSalud()
      .then(setSalud)
      .catch((e) => setError(e.message))
  }, [])

  return (
    <main style={{ fontFamily: 'system-ui, sans-serif', maxWidth: 640, margin: '3rem auto', padding: '0 1rem' }}>
      <h1>PQRSD Coffee Devs</h1>
      <h2>Estado del sistema</h2>
      {error && <p>Backend: no disponible ({error})</p>}
      {!error && !salud && <p>Consultando /api/health…</p>}
      {salud && (
        <ul>
          <li>Backend: {salud.estado}</li>
          <li>Base de datos: {salud.db ? 'conectada' : 'sin conexión'}</li>
        </ul>
      )}
    </main>
  )
}

export default function App() {
  return (
    <Routes>
      <Route path="*" element={<EstadoSistema />} />
    </Routes>
  )
}

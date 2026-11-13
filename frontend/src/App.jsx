import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import Marco from './components/Marco.jsx'
import AdminDetalle from './pages/AdminDetalle.jsx'
import AdminLogin from './pages/AdminLogin.jsx'
import AdminPanel from './pages/AdminPanel.jsx'
import Chat from './pages/Chat.jsx'
import Estado from './pages/Estado.jsx'
import Inicio from './pages/Inicio.jsx'
import NoEncontrada from './pages/NoEncontrada.jsx'
import Radicar from './pages/Radicar.jsx'
import RadicarChat from './pages/RadicarChat.jsx'
import { tokenAdmin } from './services/api.js'

// Las páginas del panel piden sesión (US-022). El backend valida el token en cada
// consulta; esta guardia solo evita mostrar el panel a quien no ha entrado.
function SoloAdmin({ children }) {
  const { pathname } = useLocation()
  if (!tokenAdmin()) return <Navigate to="/admin/login" replace state={{ desde: pathname }} />
  return children
}

export default function App() {
  return (
    <Marco>
      <Routes>
        <Route path="/" element={<Inicio />} />
        <Route path="/chat" element={<Chat />} />
        <Route path="/radicar" element={<Radicar />} />
        <Route path="/radicar/chat" element={<RadicarChat />} />
        <Route path="/estado" element={<Estado />} />
        <Route path="/admin/login" element={<AdminLogin />} />
        <Route path="/admin" element={<SoloAdmin><AdminPanel /></SoloAdmin>} />
        <Route path="/admin/pqrsd/:radicado" element={<SoloAdmin><AdminDetalle /></SoloAdmin>} />
        <Route path="*" element={<NoEncontrada />} />
      </Routes>
    </Marco>
  )
}

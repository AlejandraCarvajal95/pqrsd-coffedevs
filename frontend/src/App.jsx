import { Route, Routes } from 'react-router-dom'
import Marco from './components/Marco.jsx'
import Chat from './pages/Chat.jsx'
import Estado from './pages/Estado.jsx'
import Inicio from './pages/Inicio.jsx'
import NoEncontrada from './pages/NoEncontrada.jsx'
import Radicar from './pages/Radicar.jsx'
import RadicarChat from './pages/RadicarChat.jsx'

export default function App() {
  return (
    <Marco>
      <Routes>
        <Route path="/" element={<Inicio />} />
        <Route path="/chat" element={<Chat />} />
        <Route path="/radicar" element={<Radicar />} />
        <Route path="/radicar/chat" element={<RadicarChat />} />
        <Route path="/estado" element={<Estado />} />
        <Route path="*" element={<NoEncontrada />} />
      </Routes>
    </Marco>
  )
}

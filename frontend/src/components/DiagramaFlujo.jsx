import { IconoCheck } from './Iconos.jsx'
import { useRadicadoAnimado } from '../hooks/useRadicadoAnimado.js'

// Ilustración de portada: el recorrido de una solicitud como hojas técnicas
// superpuestas. Las hojas se posan en orden y la línea de ruta se dibuja
// después, para que se lea la secuencia consulta, solicitud, radicado, revisión.
export default function DiagramaFlujo() {
  // Sufijo de ejemplo con el alfabeto real del radicado (sin 0/O ni 1/I/L).
  const sufijo = useRadicadoAnimado('K7M2QD', true)

  return (
    <div
      className="diagrama"
      role="img"
      aria-label="Recorrido de una solicitud: consulta al asistente con su fuente, solicitud, número de radicado y revisión de una persona."
    >
      <svg className="diagrama__ruta" viewBox="0 0 110 100" aria-hidden="true">
        <defs>
          <linearGradient id="barrido-senal" x1="0" x2="1" y1="0" y2="0">
            <stop offset="0.52" stopColor="#10c9b4" />
            <stop offset="1" stopColor="#a8e01c" />
          </linearGradient>
        </defs>
        <path
          pathLength="1"
          d="M30 16 C 58 8, 84 14, 80 32 S 60 44, 55 56 S 44 78, 34 88"
        />
      </svg>

      <div className="hoja hoja--consulta" aria-hidden="true">
        <span className="hoja__rotulo">consulta</span>
        <p className="hoja__burbuja">¿Por qué me cobraron cuota de manejo?</p>
        <p className="hoja__fuente">[F1] faq_clientes › Pregunta 1</p>
      </div>

      <div className="hoja hoja--solicitud" aria-hidden="true">
        <span className="hoja__rotulo">solicitud</span>
        <dl className="hoja__datos">
          <div><dt>Asunto</dt><dd>Cobro de cuota de manejo</dd></div>
          <div><dt>Canal</dt><dd>chat</dd></div>
        </dl>
      </div>

      <div className="ficha" aria-hidden="true">
        <span className="hoja__rotulo">radicado de ejemplo</span>
        <p className="ficha__numero">PQRSD-2026-{sufijo}</p>
        <p className="ficha__estado"><span className="ficha__marca" />Recibida</p>
      </div>

      <div className="hoja hoja--revision" aria-hidden="true">
        <span className="hoja__rotulo">revisión</span>
        <p className="hoja__linea">Borrador con citas</p>
        <p className="hoja__aprobado">
          <span className="mosaico-menta"><IconoCheck width={10} height={10} /></span>
          Aprobado por una persona
        </p>
      </div>
    </div>
  )
}

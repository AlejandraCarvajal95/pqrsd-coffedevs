"""Carta de respuesta en PDF con la marca del banco.

Arma el PDF de una PQRSD ya respondida: membrete con el logo y el nombre de
Banco Andino Ficticio, radicado, fecha de respuesta y el texto final aprobado (sin
etiquetas [F#]). Lo usan la consulta del ciudadano (api/estado.py) y el panel
(api/bandeja.py). Solo se genera a partir del texto que aprobó una persona.

El logo se dibuja con vectores (mismo dibujo de frontend/public/logo.svg), así
no hace falta empaquetar imágenes. Se usan las fuentes base del PDF, que solo
cubren latin-1: los signos tipográficos fuera de ese rango se reemplazan.
"""

from datetime import datetime

from fastapi import Response
from fpdf import FPDF
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import PQRSD, AccionRevision, Revision
from app.models.pqrsd import ZONA_COLOMBIA

NOMBRE_BANCO = "Banco Andino Ficticio"
LEMA = "Atención de peticiones, quejas, reclamos, sugerencias y denuncias"
AVISO_PIE = "Entidad ficticia creada para una demostración académica. Documento sin validez real."

MESES = (
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
)

# Colores de la identidad visual (identidad.css).
TINTA = (28, 25, 23)
PAPEL = (255, 253, 250)
MENTA = (143, 245, 220)
PIZARRA = (120, 113, 108)
ACERO = (214, 211, 209)

REEMPLAZOS_LATIN1 = str.maketrans({
    "‘": "'", "’": "'", "“": '"', "”": '"',
    "–": "-", "—": "-", "…": "...", "•": "-",
    " ": " ", " ": " ", "​": "",
})


def _latin1(texto: str) -> str:
    return texto.translate(REEMPLAZOS_LATIN1).encode("latin-1", "replace").decode("latin-1")


def fecha_larga(momento: datetime) -> str:
    """'13 de noviembre de 2026', en hora de Colombia."""
    local = momento.astimezone(ZONA_COLOMBIA) if momento.tzinfo else momento
    return f"{local.day} de {MESES[local.month - 1]} de {local.year}"


class _Carta(FPDF):
    def __init__(self, radicado: str, fecha: str) -> None:
        super().__init__(format="Letter", unit="mm")
        self.radicado = radicado
        self.fecha = fecha
        self.set_margins(25, 22, 25)
        self.set_auto_page_break(auto=True, margin=24)
        self.set_title(_latin1(f"Respuesta a la PQRSD {radicado}"))
        self.set_author(NOMBRE_BANCO)
        self.set_creator(NOMBRE_BANCO)

    def _logo(self, x: float, y: float, lado: float) -> None:
        escala = lado / 28  # el dibujo original mide 28 x 28
        self.set_line_width(1.5 * escala)
        self.set_draw_color(*TINTA)
        self.set_fill_color(*PAPEL)
        with self.rotation(8, x + 11.5 * escala, y + 11.5 * escala):
            self.rect(x + 3 * escala, y + 3 * escala, 17 * escala, 17 * escala,
                      style="DF", round_corners=True, corner_radius=4 * escala)
        self.set_fill_color(*TINTA)
        self.rect(x + 9 * escala, y + 9 * escala, 16 * escala, 16 * escala,
                  style="F", round_corners=True, corner_radius=4 * escala)
        self.set_fill_color(*MENTA)
        self.rect(x + 13 * escala, y + 17 * escala, 4 * escala, 4 * escala,
                  style="F", round_corners=True, corner_radius=1 * escala)

    def header(self) -> None:
        arriba = 16
        self._logo(self.l_margin, arriba, 13)
        self.set_xy(self.l_margin + 16, arriba + 1.5)
        self.set_text_color(*TINTA)
        self.set_font("Helvetica", "B", 15)
        self.cell(0, 6, NOMBRE_BANCO)
        self.set_xy(self.l_margin + 16, arriba + 7.5)
        self.set_text_color(*PIZARRA)
        self.set_font("Helvetica", "", 8.5)
        self.cell(0, 4, _latin1(LEMA))

        self.set_xy(self.l_margin, arriba + 1.5)
        self.set_font("Courier", "", 9)
        self.cell(0, 5, self.radicado, align="R")
        self.set_xy(self.l_margin, arriba + 7.5)
        self.set_font("Helvetica", "", 8.5)
        self.cell(0, 4, _latin1(f"Respondida el {self.fecha}"), align="R")

        self.set_draw_color(*ACERO)
        self.set_line_width(0.3)
        self.line(self.l_margin, arriba + 17, self.w - self.r_margin, arriba + 17)
        self.set_y(arriba + 25)

    def footer(self) -> None:
        self.set_y(-16)
        self.set_draw_color(*ACERO)
        self.set_line_width(0.3)
        self.line(self.l_margin, self.get_y() - 2, self.w - self.r_margin, self.get_y() - 2)
        self.set_text_color(*PIZARRA)
        self.set_font("Helvetica", "", 7.5)
        self.cell(0, 4, _latin1(f"{NOMBRE_BANCO} · {AVISO_PIE}"))
        self.cell(0, 4, f"{self.page_no()} / {{nb}}", align="R")


def generar_pdf_respuesta(
    *,
    radicado: str,
    fecha_respuesta: datetime,
    texto: str,
) -> bytes:
    """Devuelve el PDF de la carta de respuesta aprobada.

    La carta que redacta la IA ya trae fecha, referencia y saludo: aquí solo se
    agrega el membrete, con el radicado y la fecha de respuesta.
    """
    pdf = _Carta(radicado, fecha_larga(fecha_respuesta))
    pdf.add_page()
    ancho = pdf.w - pdf.l_margin - pdf.r_margin

    pdf.set_text_color(*TINTA)
    pdf.set_font("Helvetica", "", 11)
    for parrafo in texto.strip().split("\n"):
        if parrafo.strip():
            pdf.multi_cell(
                ancho, 6, _latin1(parrafo.rstrip()), align="L", new_x="LMARGIN", new_y="NEXT"
            )
        else:
            pdf.ln(3.5)

    return bytes(pdf.output())


def respuesta_aprobada(sesion: Session, pqrsd: PQRSD) -> Revision | None:
    """La revisión que aprobó la PQRSD (la más reciente), o None si no está respondida."""
    return sesion.scalars(
        select(Revision)
        .where(Revision.pqrsd_id == pqrsd.id, Revision.accion == AccionRevision.aprobado)
        .order_by(Revision.creado_en.desc(), Revision.id.desc())
    ).first()


def respuesta_pdf(pqrsd: PQRSD, aprobada: Revision, descargar: bool) -> Response:
    """PDF listo para enviar: en línea para verlo en el navegador o como descarga."""
    contenido = generar_pdf_respuesta(
        radicado=pqrsd.radicado,
        fecha_respuesta=aprobada.creado_en,
        texto=aprobada.texto_final or "",
    )
    modo = "attachment" if descargar else "inline"
    return Response(
        content=contenido,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'{modo}; filename="respuesta-{pqrsd.radicado}.pdf"',
            "Cache-Control": "no-store",
        },
    )

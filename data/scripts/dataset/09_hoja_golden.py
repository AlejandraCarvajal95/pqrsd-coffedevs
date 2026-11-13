"""Paso 9: hoja de Excel para que el equipo etiquete a mano el tipo del golden set.

    python data/scripts/dataset/09_hoja_golden.py

Lee data/datasets/intermedio/golden_propuesto.jsonl y escribe
data/datasets/final/golden_set_etiquetado.xlsx (sin fórmulas: solo datos y listas).
"""

import json
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.worksheet.datavalidation import DataValidation

RAIZ = Path(__file__).resolve().parents[2] / "datasets"
ENTRADA = RAIZ / "intermedio" / "golden_propuesto.jsonl"
SALIDA = RAIZ / "final" / "golden_set_etiquetado.xlsx"

TIPOS = ["peticion", "queja", "reclamo", "sugerencia", "denuncia", "no_aplica"]
AREAS = {"tarjetas": "Tarjetas de Crédito", "cartera": "Cartera", "seguros": "Seguros de Vida",
         "juridica": "Jurídica", "fuera_de_competencia": "Fuera de competencia (no es del banco)"}
FUENTES = {"cfpb": "Queja bancaria real (CFPB, traducida)",
           "datos_gov_mindeporte": "PQRS real (MinDeporte)",
           "datos_gov_contraloria_valle": "Denuncia real (Contraloría del Valle)",
           "amazon_es": "Reseña real de cliente (Amazon)"}

FUENTE = "Arial"
AZUL = "1F3864"
AMARILLO = PatternFill("solid", fgColor="FFF2CC")
ENCABEZADO = PatternFill("solid", fgColor=AZUL)
GRIS = PatternFill("solid", fgColor="F2F2F2")
BORDE = Border(*(Side(style="thin", color="BFBFBF"),) * 4)


def f(tamano=10, negrita=False, color="000000", cursiva=False):
    return Font(name=FUENTE, size=tamano, bold=negrita, color=color, italic=cursiva)


def hoja_instrucciones(wb):
    ws = wb.active
    ws.title = "Instrucciones"
    ws.sheet_view.showGridLines = False
    ws.column_dimensions["A"].width = 3
    ws.column_dimensions["B"].width = 20
    ws.column_dimensions["C"].width = 95
    fila = 2

    def escribir(texto, fuente=None, alto=None, col="B", fusionar=True):
        nonlocal fila
        celda = ws[f"{col}{fila}"]
        celda.value = texto
        celda.font = fuente or f()
        celda.alignment = Alignment(wrap_text=True, vertical="top")
        if fusionar:
            ws.merge_cells(f"B{fila}:C{fila}")
        if alto:
            ws.row_dimensions[fila].height = alto
        fila += 1

    escribir("Golden set: etiquetado manual del tipo de PQRSD", f(16, True, AZUL), 28)
    escribir("Banco Andino Ficticio · Coffee Devs · Nepxa AI Ops Challenge 2026", f(10, cursiva=True,
             color="595959"))
    fila += 1
    escribir("Para qué sirve", f(12, True, AZUL))
    escribir("Estas 59 PQRSD son reales y ninguna se usó para entrenar los modelos. Con el tipo que "
             "ustedes confirmen se mide qué tan bien clasifica el sistema: es la cifra de exactitud "
             "que se muestra en la demo. Por eso la debe poner una persona, no la IA.", alto=45)
    fila += 1
    escribir("Cómo llenarla (unos 15 minutos)", f(12, True, AZUL))
    pasos = [
        "1. Vaya a la hoja «Etiquetado». Lea el texto de cada fila (columna C).",
        "2. En la columna E («Tipo correcto»), elija el tipo de la lista desplegable. La columna D "
        "muestra lo que propuso la IA: úsela solo como pista, y si no está de acuerdo, elija otro.",
        "3. Solo edite las celdas amarillas: E (tipo correcto), F (comentario, opcional) y G (sus iniciales).",
        "4. Si duda entre dos tipos, elija el que exige la acción principal del banco y anote la duda "
        "en el comentario.",
        "5. Si el texto no es una PQRSD (solo una opinión, un título o un texto sin sentido), elija «no_aplica».",
    ]
    for p in pasos:
        escribir(p, alto=30)
    fila += 1
    escribir("Definiciones de cada tipo", f(12, True, AZUL))
    definiciones = [
        ("peticion", "Pide información, un documento, una copia, un certificado o un trámite, sin "
                     "expresar inconformidad. Ej.: «Solicito el paz y salvo de mi crédito».",
         "10 días hábiles si pide documentos o información; 15 en general"),
        ("queja", "Inconformidad con la conducta o la atención de una persona o dependencia: mal "
                  "trato, demora en atender, mala información, acoso en la cobranza.",
         "15 días hábiles"),
        ("reclamo", "Inconformidad con un producto, cobro o decisión, pidiendo que se corrija: cobro "
                    "indebido, compra no reconocida, reporte errado en centrales de riesgo.",
         "15 días hábiles"),
        ("sugerencia", "Propone una mejora o una idea, sin pedir solución a un caso propio.",
         "15 días hábiles (criterio del Banco)"),
        ("denuncia", "Informa una posible irregularidad, fraude, corrupción, suplantación o delito, "
                     "propio o de terceros.", "15 días hábiles"),
        ("no_aplica", "No es una PQRSD: opinión sin propuesta, felicitación, texto vacío o sin sentido.",
         "—"),
    ]
    for nombre, (col_b, col_c) in (("Tipo", ("Definición", "Plazo legal")),):
        pass
    ws[f"B{fila}"], ws[f"C{fila}"] = "Tipo", "Definición  ·  plazo de respuesta"
    for c in ("B", "C"):
        ws[f"{c}{fila}"].font = f(10, True, "FFFFFF")
        ws[f"{c}{fila}"].fill = ENCABEZADO
        ws[f"{c}{fila}"].border = BORDE
    fila += 1
    for tipo, definicion, plazo in definiciones:
        ws[f"B{fila}"] = tipo
        ws[f"B{fila}"].font = f(10, True)
        ws[f"C{fila}"] = f"{definicion}\nPlazo: {plazo}"
        ws[f"C{fila}"].font = f()
        for c in ("B", "C"):
            ws[f"{c}{fila}"].alignment = Alignment(wrap_text=True, vertical="top")
            ws[f"{c}{fila}"].border = BORDE
        ws.row_dimensions[fila].height = 45
        fila += 1
    fila += 1
    escribir("Por qué importa el tipo", f(12, True, AZUL))
    escribir("El tipo define el plazo legal (Ley 1755 de 2015). Si una petición de documentos "
             "(10 días) se toma por reclamo (15 días), la PQRSD puede vencer sin que el sistema "
             "avise a tiempo.", alto=45)
    fila += 1
    escribir("Ejemplo de una fila bien llenada", f(12, True, AZUL))
    ejemplo = [("Texto", "«Necesito un certificado con el saldo de mi crédito para presentarlo en otra "
                         "entidad.»"),
               ("Tipo propuesto (IA)", "peticion"), ("Tipo correcto", "peticion"),
               ("Comentario", "(vacío: no hubo dudas)"), ("Revisado por", "MVC")]
    for etiqueta, valor in ejemplo:
        ws[f"B{fila}"], ws[f"C{fila}"] = etiqueta, valor
        ws[f"B{fila}"].font = f(10, True)
        ws[f"C{fila}"].font = f(cursiva=True)
        ws[f"C{fila}"].fill = AMARILLO if etiqueta in ("Tipo correcto", "Comentario", "Revisado por") else GRIS
        ws[f"C{fila}"].alignment = Alignment(wrap_text=True)
        fila += 1
    fila += 1
    escribir("Leyenda: las celdas amarillas son las únicas que se editan. Los textos están "
             "anonimizados: los nombres, documentos y teléfonos son ficticios.", f(9, cursiva=True,
             color="595959"), alto=30)


def hoja_etiquetado(wb, filas):
    ws = wb.create_sheet("Etiquetado")
    encabezados = [("N°", 5), ("Texto de la PQRSD", 80), ("Origen", 22), ("Tipo propuesto (IA)", 14),
                   ("Tipo correcto ✎", 15), ("Comentario ✎", 28), ("Revisado por ✎", 12),
                   ("Área de referencia", 20), ("Tema de referencia", 22), ("id", 16)]
    columnas = "ABCDEFGHIJ"
    for col, (titulo, ancho) in zip(columnas, encabezados):
        celda = ws[f"{col}1"]
        celda.value = titulo
        celda.font = f(10, True, "FFFFFF")
        celda.fill = ENCABEZADO
        celda.alignment = Alignment(wrap_text=True, vertical="center", horizontal="center")
        celda.border = BORDE
        ws.column_dimensions[col].width = ancho
    ws.row_dimensions[1].height = 32
    ws.freeze_panes = "C2"

    lista = DataValidation(type="list", formula1='"' + ",".join(TIPOS) + '"', allow_blank=True,
                           showErrorMessage=True, errorTitle="Tipo no válido",
                           error="Elija un tipo de la lista.")
    ws.add_data_validation(lista)

    for i, fila in enumerate(filas, start=2):
        valores = [i - 1, fila["texto"], FUENTES.get(fila["fuente"], fila["fuente"]),
                   fila.get("tipo_propuesto") or "—", None, None, None,
                   AREAS.get(fila["area_ref"], fila["area_ref"]),
                   (fila.get("tema_ref") or "—").replace("_", " "), fila["id"]]
        for col, valor in zip(columnas, valores):
            celda = ws[f"{col}{i}"]
            celda.value = valor
            celda.font = f(9, color="7F7F7F") if col == "J" else f()
            celda.border = BORDE
            celda.alignment = Alignment(wrap_text=True, vertical="top",
                                        horizontal="center" if col in "ADEG" else "left")
            if col in "EFG":
                celda.fill = AMARILLO
        lista.add(f"E{i}")
        ws.row_dimensions[i].height = max(30, min(240, 13 * (len(fila["texto"]) // 95 + 1)))
    ws.auto_filter.ref = f"A1:J{len(filas) + 1}"


if __name__ == "__main__":
    filas = [json.loads(l) for l in ENTRADA.read_text(encoding="utf-8").splitlines()]
    filas = [x for x in filas if x.get("texto")]
    # Orden mezclado (fijo) para que no queden todas las de un mismo origen juntas.
    filas.sort(key=lambda x: hash(x["id"][::-1]) % 1000)
    wb = Workbook()
    hoja_instrucciones(wb)
    hoja_etiquetado(wb, filas)
    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    wb.save(SALIDA)
    print(f"{SALIDA}: {len(filas)} filas")

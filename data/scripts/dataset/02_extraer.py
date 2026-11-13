"""Paso 2: selecciona y unifica las filas útiles de cada fuente en intermedio/candidatos.parquet.

Esquema unificado (una fila por texto):
  id, fuente, fuente_id, idioma, texto_original, es_banco,
  tipo_fuente (etiqueta original de la fuente), tipo_mapeo (tipo provisional),
  area, tema, fraude, sentimiento_fuente, grupo

No hay datos sintéticos: todo texto viene de una fuente pública.
"""

import html
import json
import re
import sys

import duckdb
import pandas as pd

sys.path.insert(0, "/data/scripts/dataset")
from config import (  # noqa: E402
    BANKING77, CRUDO, DATOS_GOV, INTERMEDIO, PRODUCTOS_COBRANZA, PRODUCTOS_PRESTAMO,
    PRODUCTOS_REPORTE, PRODUCTOS_TARJETA, SEMILLA, TEMAS, mapear_cfpb,
)

POR_AREA_CFPB = 1000  # meta por área del banco (Tarjetas, Cartera, Jurídica; Seguros lo que haya)
MAX_CARACTERES_EN = 900  # unas 150 palabras: largo de una PQRS típica


def recortar(texto: str, maximo: int) -> str:
    """Recorta por oraciones sin pasar del máximo (si la primera ya es larga, por palabras)."""
    texto = " ".join(texto.split())
    if len(texto) <= maximo:
        return texto
    oraciones = re.split(r"(?<=[.!?])\s+", texto)
    salida = ""
    for o in oraciones:
        if len(salida) + len(o) + 1 > maximo:
            break
        salida = f"{salida} {o}".strip()
    return salida or texto[:maximo].rsplit(" ", 1)[0]


def clave_dup(texto: str) -> str:
    return re.sub(r"[^a-z0-9áéíóúñ]", "", texto.lower())[:120]


# --------------------------------------------------------------------------
def cfpb() -> pd.DataFrame:
    con = duckdb.connect()
    productos = PRODUCTOS_TARJETA + PRODUCTOS_COBRANZA + PRODUCTOS_REPORTE + PRODUCTOS_PRESTAMO
    lista = ",".join("'" + p.replace("'", "''") + "'" for p in productos)
    con.execute(f"""
        CREATE VIEW q AS
        SELECT CAST(complaint_id AS VARCHAR) AS fuente_id, product, issue, sub_issue,
               consumer_complaint_narrative AS texto, CAST(date_received AS VARCHAR) AS fecha
        FROM read_parquet('{CRUDO}/cfpb/*.parquet')
        WHERE consumer_complaint_narrative IS NOT NULL
          AND length(consumer_complaint_narrative) BETWEEN 250 AND 4000
          AND product IN ({lista})
          -- Los reportes de crédito recientes son en su mayoría cartas plantilla de
          -- empresas de "reparación de crédito": se usan solo los anteriores a 2023.
          AND NOT (product IN ({",".join("'" + p.replace("'", "''") + "'" for p in PRODUCTOS_REPORTE)})
                   AND CAST(date_received AS VARCHAR) >= '2023-01-01')
    """)
    combos = con.execute(
        "SELECT product, issue, sub_issue, count(*) n FROM q GROUP BY ALL"
    ).df()
    combos["map"] = [mapear_cfpb(p, i, s) for p, i, s in zip(combos["product"], combos["issue"], combos["sub_issue"])]
    combos = combos[combos["map"].notna()]
    combos[["area", "tema", "tipo", "fraude"]] = pd.DataFrame(combos["map"].tolist(), index=combos.index)
    disponibles = combos.groupby(["area", "tema"])["n"].sum()
    print("CFPB disponible por área y tema:\n", disponibles.to_string())

    partes = []
    for area, grupo in combos.groupby("area"):
        temas = sorted(grupo["tema"].unique())
        # Reparte la meta del área por partes iguales entre sus temas; lo que un tema
        # no alcanza a cubrir se pasa a los demás.
        cupo, restantes = {}, POR_AREA_CFPB
        for t in sorted(temas, key=lambda t: disponibles[(area, t)]):
            pendientes = len(temas) - len(cupo)
            cupo[t] = min(int(disponibles[(area, t)]), restantes // pendientes)
            restantes -= cupo[t]
        for tema, n in cupo.items():
            sub = grupo[grupo["tema"] == tema]
            cond = " OR ".join(
                "(product = ? AND issue = ? AND " + ("sub_issue IS NULL" if pd.isna(s) else "sub_issue = ?") + ")"
                for s in sub["sub_issue"]
            )
            params = []
            for p, i, s in zip(sub["product"], sub["issue"], sub["sub_issue"]):
                params += [p, i] + ([] if pd.isna(s) else [s])
            filas = con.execute(
                f"SELECT * FROM q WHERE {cond} ORDER BY hash(fuente_id || '{SEMILLA}') LIMIT {n * 2}", params
            ).df()
            filas = filas[filas["texto"].str.count("XXXX") < 15]
            filas["dup"] = filas["texto"].map(clave_dup)
            filas = filas.drop_duplicates("dup").head(n)
            mapa = {(p, i, None if pd.isna(s) else s): m for p, i, s, m in
                    zip(sub["product"], sub["issue"], sub["sub_issue"], sub["map"])}
            m = [mapa[(p, i, None if pd.isna(s) else s)] for p, i, s in
                 zip(filas["product"], filas["issue"], filas["sub_issue"])]
            filas["area"], filas["tema"] = area, tema
            filas["tipo_mapeo"] = [x[2] for x in m]
            filas["fraude"] = [x[3] for x in m]
            partes.append(filas)
    df = pd.concat(partes, ignore_index=True)
    return pd.DataFrame({
        "fuente": "cfpb", "fuente_id": df["fuente_id"], "idioma": "en",
        "texto_original": [recortar(t, MAX_CARACTERES_EN) for t in df["texto"]],
        "es_banco": True,
        "tipo_fuente": df["product"] + " | " + df["issue"] + " | " + df["sub_issue"].fillna("-"),
        "tipo_mapeo": df["tipo_mapeo"], "area": df["area"], "tema": df["tema"],
        "fraude": df["fraude"], "sentimiento_fuente": None, "grupo": "cfpb",
    })


# --------------------------------------------------------------------------
def banking77() -> pd.DataFrame:
    nombres = json.loads((CRUDO / "banking77" / "etiquetas.json").read_text(encoding="utf-8"))
    df = pd.concat([pd.read_parquet(p) for p in (CRUDO / "banking77").glob("*.parquet")], ignore_index=True)
    df["intencion"] = df["label"].map(lambda i: nombres[i])
    df = df[df["intencion"].isin(BANKING77)].drop_duplicates("text")
    df = df.groupby("intencion", group_keys=False).apply(
        lambda g: g.sample(min(len(g), 40), random_state=SEMILLA)
    )
    return pd.DataFrame({
        "fuente": "banking77", "fuente_id": df.index.astype(str), "idioma": "en",
        "texto_original": df["text"].str.strip(), "es_banco": True,
        "tipo_fuente": df["intencion"], "tipo_mapeo": "peticion", "area": "tarjetas",
        "tema": df["intencion"].map(lambda i: BANKING77[i][0]),
        "fraude": df["intencion"].map(lambda i: BANKING77[i][1]),
        "sentimiento_fuente": None, "grupo": "banking77",
    })


# --------------------------------------------------------------------------
SUGERENCIA = re.compile(
    r"\b(deber[ií]an|ser[ií]a (bueno|mejor|ideal|genial)|sugiero|sugerir[ií]a|recomendar[ií]a que|"
    r"podr[ií]an (mejorar|incluir|agregar|a[ñn]adir|poner)|ojal[áa]|les propongo|estar[ií]a bien que)\b",
    re.I,
)


def amazon() -> pd.DataFrame:
    df = pd.concat([pd.read_parquet(p) for p in (CRUDO / "amazon_es").glob("*.parquet")], ignore_index=True)
    df = df[df["text"].str.len().between(40, 900)].drop_duplicates("text")
    estrellas_a_sent = {0: "negativo", 1: "negativo", 2: "neutral", 3: "positivo", 4: "positivo"}
    df["sent"] = df["label"].map(estrellas_a_sent)
    sent = df.groupby("sent", group_keys=False).apply(lambda g: g.sample(2000, random_state=SEMILLA))
    sent["grupo"], sent["tipo_mapeo"] = "amazon_sentimiento", None
    sug = df[df["text"].str.contains(SUGERENCIA) & ~df.index.isin(sent.index)]
    sug = sug.sample(min(len(sug), 1200), random_state=SEMILLA)
    sug["grupo"], sug["tipo_mapeo"] = "amazon_sugerencia", "sugerencia"
    df = pd.concat([sent, sug])
    return pd.DataFrame({
        "fuente": "amazon_es", "fuente_id": df["id"].astype(str), "idioma": "es",
        "texto_original": df["text"].str.strip(), "es_banco": False,
        "tipo_fuente": "estrellas=" + (df["label"] + 1).astype(str), "tipo_mapeo": df["tipo_mapeo"],
        "area": None, "tema": None, "fraude": None,
        "sentimiento_fuente": df["sent"], "grupo": df["grupo"],
    })


# --------------------------------------------------------------------------
PREFIJOS_VALLE = re.compile(r"^(informe final|respuesta final|respuesta)\s*[.:-]?\s*(relacionad[ao]s? con\s*)?", re.I)
CAP_MINDEPORTE_PETICION = 900


def limpiar(texto: str) -> str:
    texto = re.sub(r"&#(\d+),", lambda m: chr(int(m.group(1))), str(texto))
    return " ".join(html.unescape(texto).split())


def datos_gov() -> pd.DataFrame:
    partes = []
    for nombre, cfg in DATOS_GOV.items():
        df = pd.read_parquet(CRUDO / "datos_gov" / f"{nombre}.parquet")
        df["texto"] = df[cfg["texto"]].map(limpiar)
        if nombre == "contraloria_valle":
            df["texto"] = df["texto"].str.replace(PREFIJOS_VALLE, "", regex=True).str.strip()
            df["tipo_fuente"] = "Denuncia"
        else:
            df["tipo_fuente"] = df[cfg["tipo"]]
        df["tipo_mapeo"] = df["tipo_fuente"].map(cfg["tipos"]) if cfg["tipo"] else "denuncia"
        df = df[df["tipo_mapeo"].notna() & (df["texto"].str.len() >= 40)]
        df["dup"] = df["texto"].map(clave_dup)
        df = df.drop_duplicates("dup")
        if nombre == "mindeporte":
            pet = df[df["tipo_mapeo"] == "peticion"]
            pet = pet.groupby("tipo_fuente", group_keys=False).apply(
                lambda g: g.sample(min(len(g), CAP_MINDEPORTE_PETICION // 4), random_state=SEMILLA)
            )
            df = pd.concat([pet, df[df["tipo_mapeo"] != "peticion"]])
        if nombre == "contraloria_valle":
            df = df.sample(min(len(df), 500), random_state=SEMILLA)
        id_col = next(c for c in df.columns if c in ("no_de_solicitud", "radicado", "consecutivo", ":id")) \
            if any(c in df.columns for c in ("no_de_solicitud", "radicado", "consecutivo")) else None
        partes.append(pd.DataFrame({
            "fuente": f"datos_gov_{nombre}",
            "fuente_id": (df[id_col].astype(str) if id_col else df.index.astype(str)),
            "idioma": "es", "texto_original": df["texto"], "es_banco": False,
            "tipo_fuente": df["tipo_fuente"].astype(str), "tipo_mapeo": df["tipo_mapeo"],
            "area": "fuera_de_competencia", "tema": None, "fraude": False,
            "sentimiento_fuente": None, "grupo": "datos_gov",
        }))
    return pd.concat(partes, ignore_index=True)


if __name__ == "__main__":
    INTERMEDIO.mkdir(parents=True, exist_ok=True)
    fuentes = sys.argv[1:] or ["datos_gov", "amazon", "banking77", "cfpb"]
    for f in fuentes:
        df = globals()[f]()
        df["id"] = df["fuente"] + ":" + df["fuente_id"].astype(str)
        df = df.drop_duplicates("id")
        df.to_parquet(INTERMEDIO / f"candidatos_{f}.parquet", index=False)
        print(f"\n== {f}: {len(df)} filas")
        print(df.groupby(["grupo", "tipo_mapeo"], dropna=False).size().to_string())
        if f in ("cfpb", "banking77"):
            print(df.groupby(["area", "tema"]).size().to_string())

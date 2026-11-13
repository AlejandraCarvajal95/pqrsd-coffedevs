"""Paso 7: candidatos del golden set, todos reales y ninguno usado en el entrenamiento.

- 36 quejas bancarias del CFPB (9 por área del banco). Su área y tema salen del producto y
  el issue que eligió el propio consumidor al radicar: son independientes de Claude y del SVM.
  Se traducen y se propone el tipo en el paso 8.
- 24 PQRS reales en español de entidades públicas y reseñas (peticiones, quejas, reclamos,
  denuncias, sugerencias). Su área de referencia es "fuera de competencia" (no son del banco).
El tipo de todas lo debe confirmar una persona en la hoja de etiquetado.

Salida: intermedio/golden_candidatos.jsonl
"""

import json
import random
import re
import sys

import duckdb
import pandas as pd

sys.path.insert(0, "/data/scripts/dataset")
from config import (  # noqa: E402
    CRUDO, DATOS_GOV, INTERMEDIO, PRODUCTOS_COBRANZA, PRODUCTOS_PRESTAMO, PRODUCTOS_REPORTE,
    PRODUCTOS_TARJETA, mapear_cfpb,
)

SEMILLA_GOLDEN = 77  # distinta a la del dataset
POR_AREA = 9
rnd = random.Random(SEMILLA_GOLDEN)


def cfpb() -> list[dict]:
    usados = set(pd.read_parquet(INTERMEDIO / "candidatos_cfpb.parquet")["fuente_id"].astype(str))
    productos = PRODUCTOS_TARJETA + PRODUCTOS_COBRANZA + PRODUCTOS_REPORTE + PRODUCTOS_PRESTAMO
    lista = ",".join("'" + p.replace("'", "''") + "'" for p in productos)
    df = duckdb.sql(f"""
        SELECT CAST(complaint_id AS VARCHAR) AS fuente_id, product, issue, sub_issue,
               consumer_complaint_narrative AS texto
        FROM read_parquet('{CRUDO}/cfpb/*.parquet')
        WHERE consumer_complaint_narrative IS NOT NULL
          AND length(consumer_complaint_narrative) BETWEEN 250 AND 1500
          AND product IN ({lista}) AND CAST(date_received AS VARCHAR) < '2023-01-01'
        USING SAMPLE 60000 ROWS (reservoir, {SEMILLA_GOLDEN})
    """).df()
    # El seguro de deuda es escaso: se buscan todas sus quejas con texto, sin muestrear.
    seguros = duckdb.sql(f"""
        SELECT CAST(complaint_id AS VARCHAR) AS fuente_id, product, issue, sub_issue,
               consumer_complaint_narrative AS texto
        FROM read_parquet('{CRUDO}/cfpb/*.parquet')
        WHERE consumer_complaint_narrative IS NOT NULL
          AND length(consumer_complaint_narrative) BETWEEN 200 AND 2500
          AND issue = 'Credit card protection / Debt protection'
    """).df()
    df = pd.concat([df, seguros]).drop_duplicates("fuente_id")
    df = df[~df["fuente_id"].isin(usados) & (df["texto"].str.count("XXXX") < 8)]
    df["map"] = [mapear_cfpb(p, i, s) for p, i, s in zip(df["product"], df["issue"], df["sub_issue"])]
    df = df[df["map"].notna()]
    df["area"] = df["map"].str[0]
    df["tema"] = df["map"].str[1]
    salida = []
    for area, grupo in df.groupby("area"):
        # Reparte entre temas por turnos, para que el golden set cubra todos los temas del área.
        por_tema = {t: g.sample(frac=1, random_state=SEMILLA_GOLDEN) for t, g in grupo.groupby("tema")}
        elegidas, ronda = [], 0
        while len(elegidas) < POR_AREA and any(len(g) > ronda for g in por_tema.values()):
            for g in por_tema.values():
                if len(g) > ronda and len(elegidas) < POR_AREA:
                    elegidas.append(g.iloc[ronda])
            ronda += 1
        for f in elegidas:
            salida.append({"id": f"golden:cfpb:{f['fuente_id']}", "fuente": "cfpb", "idioma": "en",
                           "texto": " ".join(f["texto"].split())[:1200], "area_ref": area,
                           "tema_ref": f["tema"], "tipo_fuente": f"{f['issue']} | {f['sub_issue']}"})
    return salida


def espanol() -> list[dict]:
    usados = set(pd.read_parquet(INTERMEDIO / "candidatos_datos_gov.parquet")["texto_original"].str[:120])
    usados_amazon = set(pd.read_parquet(INTERMEDIO / "candidatos_amazon.parquet")["fuente_id"].astype(str))
    salida = []

    def tomar(df, columna_texto, n, fuente, tipo_fuente):
        df = df.assign(t=df[columna_texto].astype(str).map(lambda x: " ".join(x.split())))
        df = df[(df["t"].str.len() >= 60) & ~df["t"].str[:120].isin(usados)].drop_duplicates("t")
        for _, f in df.sample(min(n, len(df)), random_state=SEMILLA_GOLDEN).iterrows():
            salida.append({"id": f"golden:{fuente}:{abs(hash(f['t'])) % 10**10}", "fuente": fuente,
                           "idioma": "es", "texto": f["t"][:1200], "area_ref": "fuera_de_competencia",
                           "tema_ref": None, "tipo_fuente": tipo_fuente(f)})

    md = pd.read_parquet(CRUDO / "datos_gov" / "mindeporte.parquet")
    tipo_md = lambda f: f["tipo"]  # noqa: E731
    tomar(md[md["tipo"].str.contains("Queja|Reclamo")], "asunto", 4, "datos_gov_mindeporte", tipo_md)
    tomar(md[md["tipo"] == "Derecho de Petición - Petición"], "asunto", 4, "datos_gov_mindeporte", tipo_md)
    tomar(md[md["tipo"].str.contains("Información, copias")], "asunto", 2, "datos_gov_mindeporte", tipo_md)
    tomar(md[md["tipo"].str.contains("Consulta")], "asunto", 2, "datos_gov_mindeporte", tipo_md)
    tomar(md[md["tipo"] == "Denuncias - Denuncias"], "asunto", 2, "datos_gov_mindeporte", tipo_md)

    valle = pd.read_parquet(CRUDO / "datos_gov" / "contraloria_valle.parquet")
    valle["asunto"] = valle["asunto"].astype(str).str.replace(
        r"^(informe final|respuesta final|respuesta)\s*[.:-]?\s*(relacionad[ao]s? con\s*)?", "",
        flags=re.I, regex=True)
    tomar(valle, "asunto", 5, "datos_gov_contraloria_valle", lambda f: "Denuncia")

    amazon = pd.concat([pd.read_parquet(p) for p in (CRUDO / "amazon_es").glob("*.parquet")])
    amazon = amazon[~amazon["id"].astype(str).isin(usados_amazon) & amazon["text"].str.len().between(80, 700)]
    sug = amazon[amazon["text"].str.contains(r"\b(deber[ií]an|ser[ií]a bueno|sugiero|ojal[áa])\b", case=False)]
    tomar(sug, "text", 5, "amazon_es", lambda f: f"estrellas={f['label'] + 1}")
    return salida


if __name__ == "__main__":
    from importlib import import_module

    an = import_module("03_anonimizar").Anonimizador()
    filas = cfpb() + espanol()
    es = [i for i, f in enumerate(filas) if f["idioma"] == "es"]
    tramos = an.nombres_spacy([filas[i]["texto"] for i in es])
    for i, t in zip(es, tramos):
        filas[i]["texto"], filas[i]["n_datos_reemplazados"] = an.anonimizar(filas[i]["texto"], filas[i]["id"], t)
    for f in filas:
        if f["idioma"] == "en":
            f["texto"], f["n_datos_reemplazados"] = an.anonimizar(f["texto"], f["id"])
    with open(INTERMEDIO / "golden_candidatos.jsonl", "w", encoding="utf-8") as out:
        for f in filas:
            out.write(json.dumps(f, ensure_ascii=False) + "\n")
    print(pd.DataFrame(filas).groupby(["fuente", "area_ref"]).size().to_string())
    print(f"Total: {len(filas)}")

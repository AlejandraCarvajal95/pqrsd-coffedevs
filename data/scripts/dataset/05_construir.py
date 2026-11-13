"""Paso 5: arma la tabla maestra y un archivo balanceado por capa del embudo.

Salida en data/datasets/final/:
  maestro.parquet / maestro.csv     todas las filas con todas las etiquetas conocidas
  capas/<capa>.parquet / .csv       subconjunto balanceado de cada SVM, con columna split
  muestra_revision_humana.csv       100 filas cuyo tipo cambió al reetiquetar, para que el equipo las revise
  resumen.json                      conteos por capa y clase

Se puede correr antes y después de traducir: las filas en inglés sin traducir quedan en el
maestro con estado_traduccion = "pendiente" y no entran a las capas hasta tener texto en español.
"""

import json
import sys
import zlib

import pandas as pd

sys.path.insert(0, "/data/scripts/dataset")
from config import FINAL, INTERMEDIO, SEMILLA, SENTIMIENTOS, TIPOS  # noqa: E402

CUPO = {"tipo": 1000, "area": 1000, "tema": 300, "sentimiento": 3000, "fraude": 1500}


def orden_estable(ids: pd.Series) -> pd.Series:
    return ids.map(lambda i: zlib.crc32(f"{SEMILLA}:{i}".encode()))


def asignar_split(df: pd.DataFrame, etiqueta: str) -> pd.DataFrame:
    """70/15/15 estratificado por etiqueta, determinista por id."""
    df = df.assign(_h=orden_estable(df["id"])).sort_values([etiqueta, "_h"])
    rango = df.groupby(etiqueta).cumcount() / df.groupby(etiqueta)[etiqueta].transform("size")
    df["split"] = pd.cut(rango, [-0.01, 0.70, 0.85, 1.0], labels=["train", "val", "test"]).astype(str)
    return df.drop(columns="_h")


def balancear(df: pd.DataFrame, etiqueta: str, cupo: int, intercalar: bool = False) -> pd.DataFrame:
    """Hasta `cupo` filas por clase, sin duplicar filas (las clases que no llegan al cupo se
    compensan con class_weight al entrenar).

    - intercalar=False: primero las filas de banco, luego el resto.
    - intercalar=True: toma de cada fuente por turnos, para que ninguna clase quede asociada
      a una sola fuente (si no, el SVM aprende el estilo de la fuente y no la clase).
    """
    df = df.assign(_h=orden_estable(df["id"]), _b=~df["es_banco"].astype(bool))
    if intercalar:
        df = df.sort_values("_h")
        df["_r"] = df.groupby([etiqueta, "fuente"]).cumcount()
        df = df.sort_values(["_r", "_b", "_h"]).drop(columns="_r")
    else:
        df = df.sort_values(["_b", "_h"])
    df = df.groupby(etiqueta, group_keys=False).head(cupo)
    return asignar_split(df.drop(columns=["_h", "_b"]), etiqueta)


def maestro() -> pd.DataFrame:
    df = pd.concat([pd.read_parquet(p) for p in INTERMEDIO.glob("anonimizado_*.parquet")], ignore_index=True)
    df = df.rename(columns={"idioma": "idioma_original"})

    # Reetiquetado (español).
    ret = pd.read_json(INTERMEDIO / "reetiquetado.jsonl", lines=True) if (INTERMEDIO / "reetiquetado.jsonl").exists() \
        else pd.DataFrame(columns=["id", "tipo", "sentimiento", "datos_personales"])
    ret = ret.drop_duplicates("id", keep="last").set_index("id")
    # Traducción + reetiquetado (inglés), cuando exista.
    tra = pd.read_json(INTERMEDIO / "traducido.jsonl", lines=True) if (INTERMEDIO / "traducido.jsonl").exists() \
        else pd.DataFrame(columns=["id", "texto_es", "tipo", "sentimiento", "datos_personales"])
    tra = tra.drop_duplicates("id", keep="last").set_index("id")

    es = df["idioma_original"] == "es"
    df["texto"] = df["texto_anon"].where(es, df["id"].map(tra["texto_es"]))
    # Traducciones con restos de EE. UU. (dólares, estados, secciones de la ley FCRA): fuera.
    residuo = (~es) & df["texto"].fillna("").str.contains(
        r"(?i)\b(?:d[óo]lares|USD|Florida|California|Texas|New York|Georgia|FCRA|FDCPA|SSN)\b"
        r"|(?:secci[óo]n|art[íi]culo) 6\d\d", regex=True)
    df.loc[residuo, "texto"] = None
    df["texto_en"] = df["texto_anon"].where(~es)
    df["estado_traduccion"] = "no_aplica"
    df.loc[~es, "estado_traduccion"] = df.loc[~es, "texto"].notna().map({True: "traducido", False: "pendiente"})

    etiquetas = pd.concat([ret, tra.drop(columns="texto_es")])
    df["tipo"] = df["id"].map(etiquetas["tipo"])
    df["tipo_origen"] = df["tipo"].notna().map({True: "reetiquetado_claude", False: None})
    df.loc[df["tipo"].isna(), "tipo_origen"] = "mapeo_provisional"
    df.loc[df["tipo_origen"] == "mapeo_provisional", "tipo"] = df["tipo_mapeo"]
    df.loc[df["tipo"].isna(), "tipo_origen"] = None

    df["sentimiento"] = df["id"].map(etiquetas["sentimiento"])
    df["sentimiento_origen"] = df["sentimiento"].notna().map({True: "reetiquetado_claude", False: None})
    estrellas = df["sentimiento"].isna() & df["sentimiento_fuente"].notna()
    df.loc[estrellas, "sentimiento"] = df.loc[estrellas, "sentimiento_fuente"]
    df.loc[estrellas, "sentimiento_origen"] = "estrellas_amazon"

    # Fuera: posibles datos personales que se escaparon y textos que no son PQRSD
    # (estos últimos sí sirven para sentimiento).
    sospechosos = df["id"].map(etiquetas["datos_personales"]).fillna(False).astype(bool)
    df = df[~sospechosos]
    fallidos = df["id"].isin(etiquetas.index) & df["tipo"].isna()
    df = df[~fallidos]

    columnas = ["id", "fuente", "fuente_id", "idioma_original", "texto", "texto_en", "estado_traduccion",
                "es_banco", "tipo", "tipo_origen", "tipo_fuente", "tipo_mapeo", "area", "tema",
                "sentimiento", "sentimiento_origen", "fraude", "n_datos_reemplazados", "grupo"]
    print(f"Maestro: {len(df)} filas ({int(sospechosos.sum())} descartadas por posibles datos personales, "
          f"{int(fallidos.sum())} sin etiqueta)")
    return df[columnas].reset_index(drop=True)


def capas(m: pd.DataFrame) -> dict[str, pd.DataFrame]:
    con_texto = m[m["texto"].notna()]
    base = ["id", "texto", "fuente", "es_banco"]
    salida = {}

    t = con_texto[con_texto["tipo"].isin(TIPOS) & (con_texto["grupo"] != "amazon_sentimiento")]
    salida["tipo"] = balancear(t[base + ["tipo"]], "tipo", CUPO["tipo"], intercalar=True)

    banco = con_texto[con_texto["es_banco"] & con_texto["area"].notna()]
    fuera = con_texto[(con_texto["area"] == "fuera_de_competencia") & con_texto["tipo"].isin(TIPOS)]
    a = pd.concat([banco, fuera])
    salida["area"] = balancear(a[base + ["area"]], "area", CUPO["area"])

    for area in banco["area"].unique():
        sub = banco[(banco["area"] == area) & banco["tema"].notna()]
        if sub["tema"].nunique() > 1:
            salida[f"tema_{area}"] = balancear(sub[base + ["tema"]], "tema", CUPO["tema"])

    s = con_texto[con_texto["sentimiento"].isin(SENTIMIENTOS)]
    salida["sentimiento"] = balancear(s[base + ["sentimiento"]], "sentimiento", CUPO["sentimiento"], intercalar=True)

    f = banco[banco["fraude"].notna()].assign(fraude=lambda d: d["fraude"].astype(bool).map({True: "si", False: "no"}))
    if f["fraude"].nunique() == 2:
        cupo = min(CUPO["fraude"], int((f["fraude"] == "si").sum()))
        salida["fraude"] = balancear(f[base + ["fraude"]], "fraude", cupo)
    return salida


if __name__ == "__main__":
    (FINAL / "capas").mkdir(parents=True, exist_ok=True)
    m = maestro()
    m.to_parquet(FINAL / "maestro.parquet", index=False)
    m.to_csv(FINAL / "maestro.csv", index=False, encoding="utf-8-sig")

    resumen = {"maestro": {
        "filas": len(m),
        "por_fuente": m["fuente"].value_counts().to_dict(),
        "traduccion": m["estado_traduccion"].value_counts().to_dict(),
    }, "capas": {}}
    for nombre, df in capas(m).items():
        etiqueta = df.columns[4]
        df.to_parquet(FINAL / "capas" / f"{nombre}.parquet", index=False)
        df.to_csv(FINAL / "capas" / f"{nombre}.csv", index=False, encoding="utf-8-sig")
        resumen["capas"][nombre] = {
            "filas": len(df),
            "por_clase": df[etiqueta].value_counts().to_dict(),
            "de_banco": int(df["es_banco"].sum()),
            "por_split": df["split"].value_counts().to_dict(),
        }
        print(f"\n[{nombre}] {len(df)} filas, {int(df['es_banco'].sum())} de banco")
        print(df.groupby([etiqueta, "fuente"]).size().unstack(fill_value=0).to_string())

    # Muestra para revisión humana: tipo original de la fuente vs tipo reetiquetado.
    cambios = m[(m["tipo_origen"] == "reetiquetado_claude") & m["tipo_mapeo"].notna() & (m["tipo"] != m["tipo_mapeo"])]
    cambios.sample(min(100, len(cambios)), random_state=SEMILLA)[
        ["id", "texto", "tipo_fuente", "tipo_mapeo", "tipo"]
    ].assign(tipo_correcto_segun_revisor="").to_csv(
        FINAL / "muestra_revision_humana.csv", index=False, encoding="utf-8-sig"
    )
    resumen["reetiquetado"] = {
        "filas_con_tipo_cambiado": len(cambios),
        "matriz_original_vs_nuevo": pd.crosstab(cambios["tipo_mapeo"], cambios["tipo"]).to_dict(),
    }
    (FINAL / "resumen.json").write_text(json.dumps(resumen, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

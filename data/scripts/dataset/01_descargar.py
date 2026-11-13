"""Paso 1: descarga las fuentes públicas a data/datasets/crudo/ (no se versiona).

Fuentes:
- CFPB Consumer Complaint Database (copia completa en Hugging Face, Bob-68/cfpb-consumer-complaints).
  Dominio público (gobierno de EE. UU.). 67 archivos parquet, unos 1 GB.
- BANKING77 (PolyAI/banking77), CC BY 4.0.
- Amazon Reviews Multi, solo español (SetFit/amazon_reviews_multi_es). Licencia de Amazon
  para uso académico no comercial.
- datos.gov.co: PQRSD reales de entidades públicas colombianas (ver config.DATOS_GOV).
"""

import json
import sys
from datetime import date

import pandas as pd
import requests

sys.path.insert(0, "/data/scripts/dataset")
from config import CRUDO, DATOS_GOV  # noqa: E402

HF = "https://huggingface.co/api/datasets"
SODA = "https://www.datos.gov.co/resource"
SESION = requests.Session()


def bajar(url: str, destino):
    if destino.exists() and destino.stat().st_size > 0:
        return
    with SESION.get(url, stream=True, timeout=600) as r:
        r.raise_for_status()
        with open(destino, "wb") as f:
            for trozo in r.iter_content(1 << 20):
                f.write(trozo)


def parquet_hf(dataset: str, split: str, carpeta):
    carpeta.mkdir(parents=True, exist_ok=True)
    urls = SESION.get(f"{HF}/{dataset}/parquet/default/{split}", timeout=60).json()
    for i, url in enumerate(urls):
        bajar(url, carpeta / f"{split}-{i}.parquet")
    return len(urls)


def cfpb():
    carpeta = CRUDO / "cfpb"
    carpeta.mkdir(parents=True, exist_ok=True)
    urls = SESION.get(f"{HF}/Bob-68/cfpb-consumer-complaints/parquet/default/train", timeout=60).json()
    for i, url in enumerate(urls):
        bajar(url, carpeta / f"{i}.parquet")
    print(f"CFPB: {len(urls)} archivos")


def banking77():
    carpeta = CRUDO / "banking77"
    for split in ("train", "test"):
        parquet_hf("PolyAI/banking77", split, carpeta)
    info = SESION.get("https://datasets-server.huggingface.co/info?dataset=PolyAI/banking77", timeout=60).json()
    nombres = info["dataset_info"]["default"]["features"]["label"]["names"]
    (carpeta / "etiquetas.json").write_text(json.dumps(nombres), encoding="utf-8")
    print(f"BANKING77: {len(nombres)} intenciones")


def amazon_es():
    n = parquet_hf("SetFit/amazon_reviews_multi_es", "train", CRUDO / "amazon_es")
    print(f"Amazon ES: {n} archivos")


def soda(id_conjunto: str, where: str | None = None) -> pd.DataFrame:
    filas, offset = [], 0
    while True:
        params = {"$limit": 50000, "$offset": offset, "$order": ":id"}
        if where:
            params["$where"] = where
        lote = SESION.get(f"{SODA}/{id_conjunto}.json", params=params, timeout=300).json()
        filas += lote
        if len(lote) < 50000:
            return pd.DataFrame(filas)
        offset += 50000


def datos_gov():
    carpeta = CRUDO / "datos_gov"
    carpeta.mkdir(parents=True, exist_ok=True)
    for nombre, cfg in DATOS_GOV.items():
        destino = carpeta / f"{nombre}.parquet"
        if destino.exists():
            continue
        where = None
        if cfg["tipo"] and nombre == "mindeporte":
            tipos = ",".join("'" + t.replace("'", "''") + "'" for t in cfg["tipos"])
            where = f"{cfg['tipo']} in ({tipos})"
        df = soda(cfg["id"], where)
        df.to_parquet(destino, index=False)
        print(f"datos.gov.co {nombre}: {len(df)} filas")


if __name__ == "__main__":
    pasos = sys.argv[1:] or ["banking77", "amazon_es", "datos_gov"]
    for paso in pasos:
        globals()[paso]()
    (CRUDO / "descarga.json").write_text(
        json.dumps({"fecha": date.today().isoformat(), "pasos": pasos}), encoding="utf-8"
    )

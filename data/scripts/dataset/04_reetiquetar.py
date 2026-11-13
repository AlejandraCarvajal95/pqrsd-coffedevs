"""Paso 4: reetiqueta con Claude (modelo liviano) los textos en español ya anonimizados.

Corre dentro del contenedor del backend para usar costos.llamar_claude: cada llamada
queda registrada en /api/costos y respeta el tope de presupuesto del equipo.

    docker compose run --rm -v ./data/datasets:/data/datasets backend \
        python /data/scripts/dataset/04_reetiquetar.py

Entrada:  intermedio/para_reetiquetar.jsonl  (id, grupo, tipo_mapeo, texto)
Salida:   intermedio/reetiquetado.jsonl      (id, tipo, sentimiento, datos_personales)
Es reanudable: si se corta, vuelve a correr y salta los ids ya etiquetados.
"""

import json
import logging
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, "/app")
from app.pipeline import costos  # noqa: E402
from app.pipeline.costos import ErrorIA, LimiteExcedido, Tarea  # noqa: E402

logging.basicConfig(level=logging.WARNING)
DIR = Path("/data/datasets/intermedio")
ENTRADA, SALIDA = DIR / "para_reetiquetar.jsonl", DIR / "reetiquetado.jsonl"
PROMPT = (Path(__file__).parent / "prompts" / "reetiquetado.md").read_text(encoding="utf-8")
POR_LLAMADA, HILOS, MAX_CHARS_TEXTO = 3, 6, 700

TIPOS = {"peticion", "queja", "reclamo", "sugerencia", "denuncia", "no_aplica"}
SENTIMIENTOS = {"negativo", "neutral", "positivo"}
SISTEMA = [{"type": "text", "text": PROMPT, "cache_control": {"type": "ephemeral"}}]
candado = threading.Lock()
gasto = Decimal(0)


def interpretar(texto: str, n: int):
    m = re.search(r"\[.*\]", texto, re.S)
    if not m:
        return None
    try:
        datos = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
    if not isinstance(datos, list) or len(datos) != n:
        return None
    salida = []
    for d in datos:
        if d.get("tipo") not in TIPOS or d.get("sentimiento") not in SENTIMIENTOS:
            return None
        salida.append((d["tipo"], d["sentimiento"], bool(d.get("datos_personales"))))
    return salida


def etiquetar(lote: list[dict]):
    global gasto
    contenido = "\n\n".join(
        f'<texto n="{k}">\n{f["texto"][:MAX_CHARS_TEXTO]}\n</texto>' for k, f in enumerate(lote, 1)
    )
    for _ in range(2):
        try:
            for espera in (10, 30, 60, 120, 0):  # cortes de red o 429: esperar y reintentar
                try:
                    r = costos.llamar_claude(Tarea.clasificador, [{"role": "user", "content": contenido}], sistema=SISTEMA)
                    break
                except ErrorIA:
                    if not espera:
                        raise
                    time.sleep(espera)
        except LimiteExcedido as e:
            if e.codigo == "entrada_larga" and len(lote) > 1:
                break
            raise
        with candado:
            gasto += r.costo_usd
        res = None if (r.rechazada or r.truncada) else interpretar(r.texto, len(lote))
        if res:
            return [{"id": f["id"], "tipo": t, "sentimiento": s, "datos_personales": p}
                    for f, (t, s, p) in zip(lote, res)]
    if len(lote) > 1:  # se divide el lote y se reintenta por mitades
        mitad = len(lote) // 2
        return etiquetar(lote[:mitad]) + etiquetar(lote[mitad:])
    return [{"id": lote[0]["id"], "tipo": None, "sentimiento": None, "datos_personales": None}]


def main():
    filas = [json.loads(l) for l in ENTRADA.read_text(encoding="utf-8").splitlines()]
    hechos = set()
    if SALIDA.exists():
        hechos = {json.loads(l)["id"] for l in SALIDA.read_text(encoding="utf-8").splitlines()}
    pendientes = [f for f in filas if f["id"] not in hechos]
    lotes = [pendientes[i:i + POR_LLAMADA] for i in range(0, len(pendientes), POR_LLAMADA)]
    print(f"{len(filas)} textos, {len(hechos)} ya etiquetados, {len(lotes)} llamadas pendientes", flush=True)

    with open(SALIDA, "a", encoding="utf-8") as out, ThreadPoolExecutor(HILOS) as ex:
        for k, res in enumerate(ex.map(etiquetar, lotes), 1):
            with candado:
                for r in res:
                    out.write(json.dumps(r, ensure_ascii=False) + "\n")
                out.flush()
            if k % 50 == 0:
                print(f"  {k}/{len(lotes)} llamadas, gasto de esta corrida: {gasto:.4f} USD", flush=True)
    print(f"Listo. Gasto de esta corrida: {gasto:.4f} USD", flush=True)


if __name__ == "__main__":
    try:
        main()
    except (ErrorIA, LimiteExcedido) as e:
        print(f"Detenido: {e}. Se puede reanudar corriendo de nuevo.", flush=True)
        sys.exit(1)

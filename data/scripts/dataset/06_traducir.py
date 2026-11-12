"""Paso 4b: traduce, localiza y reetiqueta el CFPB y BANKING77 con la Batch API (50 % más barata).

Corre dentro del contenedor del backend (usa su cliente de Anthropic, su modelo liviano y
su registro de costos):

    docker compose run --rm --user root -v ./data/datasets:/data/datasets backend \
        python /data/scripts/dataset/06_traducir.py <comando>

Comandos:
  piloto N    envía un lote pequeño con N textos para medir el costo real por texto
  enviar      envía un lote con todos los textos pendientes
  estado      muestra el estado de los lotes
  recoger     lee los lotes terminados, agrega a intermedio/traducido.jsonl y registra
              el gasto en consumos_ia (tarea "traduccion_dataset")
  reprocesar  vuelve a leer todos los lotes ya pagados (sin costo nuevo) con la limpieza actual

Cada texto se acepta por separado. Lo que el modelo deja sin adaptar (censuras XXXX,
nombres de empresas de EE. UU.) se limpia aquí, sin volver a pagar una llamada.
"""

import json
import re
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, "/app")
from anthropic.types.message_create_params import MessageCreateParamsNonStreaming  # noqa: E402
from anthropic.types.messages.batch_create_params import Request  # noqa: E402

from app.models import ConsumoIA  # noqa: E402
from app.pipeline import costos  # noqa: E402
from app.pipeline.costos import Tarea  # noqa: E402

DIR = Path("/data/datasets/intermedio")
SALIDA = DIR / "traducido.jsonl"
ESTADO = DIR / "lotes_traduccion.json"
PROMPT = (Path(__file__).parent / "prompts" / "traduccion.md").read_text(encoding="utf-8")
POR_PETICION = {"cfpb": 4, "banking77": 10}
MAX_TOKENS = 4000  # incluye el razonamiento del modelo
DESCUENTO_BATCH = Decimal("0.5")
TIPOS = {"peticion", "queja", "reclamo", "sugerencia", "denuncia"}
SENTIMIENTOS = {"negativo", "neutral", "positivo"}

CENSURAS = [
    (re.compile(r"'?\bXX/XX/(\d{4})\b'?"), r"una fecha de \1"),
    (re.compile(r"'?\bXX/XX/(XXXX|XX)\b'?"), "una fecha"),
    (re.compile(r"'?\bXX de XX(XX)?\b'?"), "un día"),
    (re.compile(r"\{\$[\d.,]+\}"), "cierto valor"),
    (re.compile(r"(\s*\bX{2,}\b)+"), ""),
]
EMPRESAS = [
    (re.compile(r"\b(Equifax|Experian|Trans ?Union)\b", re.I), "la central de riesgo"),
    (re.compile(r"\b(True ?Accord|Midland( Credit Management)?|Portfolio Recovery( Associates)?|LVNV( Funding)?|"
                r"Convergent|Enhanced Recovery|IC System|Jefferson Capital|Cavalry)\b", re.I), "la casa de cobranza"),
    (re.compile(r"\b(Synchrony( Bank)?( Pay Later)?|Capital ?One|Chase|JP ?Morgan|Citi(bank|group)?|Discover|"
                r"Wells Fargo|Bank of America|American Express|Amex|Barclays|Comenity( Bank)?|Affirm|PayPal|"
                r"Navient|Credit One|Merrick|Credit Karma|U\.?S\.? Bank|Klarna|Afterpay)\b", re.I), "el banco"),
    (re.compile(r"\b(CFPB|Consumer Financial Protection Bureau)\b"), "la Superintendencia Financiera"),
]


def limpiar(texto: str) -> str | None:
    for patron, reemplazo in CENSURAS + EMPRESAS:
        texto = patron.sub(reemplazo, texto)
    texto = re.sub(r"\s{2,}", " ", texto)
    texto = re.sub(r"\s+([,.;:])", r"\1", texto).strip()
    texto = re.sub(r"\b(el|la|del|al) (el|la) (banco|central|casa)", r"\1 \3", texto)
    if re.search(r"X{2,}|\{\$", texto) or len(texto) < 15:
        return None
    return texto


def pendientes() -> list[dict]:
    """Textos de para_traducir.jsonl (lo genera 03_anonimizar.py) que no estén ya traducidos
    ni en un lote enviado sin recoger."""
    hechos = set()
    if SALIDA.exists():
        hechos = {json.loads(l)["id"] for l in SALIDA.read_text(encoding="utf-8").splitlines()}
    if ESTADO.exists():
        for lote in json.loads(ESTADO.read_text()):
            if not lote["recogido"]:
                hechos |= {i for ids in lote["mapa"].values() for i in ids}
    filas = [json.loads(l) for l in (DIR / "para_traducir.jsonl").read_text(encoding="utf-8").splitlines()]
    return [f for f in filas if f["id"] not in hechos]


def peticiones(filas: list[dict]) -> tuple[list[Request], dict]:
    sistema = [{"type": "text", "text": PROMPT, "cache_control": {"type": "ephemeral"}}]
    modelo = costos.modelo_para(Tarea.clasificador)
    reqs, mapa = [], {}
    for fuente, n in POR_PETICION.items():
        grupo = [f for f in filas if f["fuente"] == fuente]
        for i in range(0, len(grupo), n):
            lote = grupo[i:i + n]
            cid = f"{fuente}-{i}"
            mapa[cid] = [f["id"] for f in lote]
            contenido = "\n\n".join(f'<texto n="{k}">\n{f["texto_anon"]}\n</texto>' for k, f in enumerate(lote, 1))
            reqs.append(Request(custom_id=cid, params=MessageCreateParamsNonStreaming(
                model=modelo, max_tokens=MAX_TOKENS, system=sistema,
                output_config={"effort": "low"},
                messages=[{"role": "user", "content": contenido}],
            )))
    return reqs, mapa


def enviar(filas: list[dict], etiqueta: str):
    costos.verificar_presupuesto()
    reqs, mapa = peticiones(filas)
    lote = costos.obtener_cliente().messages.batches.create(requests=reqs)
    estado = json.loads(ESTADO.read_text()) if ESTADO.exists() else []
    estado.append({"id": lote.id, "etiqueta": etiqueta, "textos": len(filas), "mapa": mapa, "recogido": False})
    ESTADO.write_text(json.dumps(estado))
    print(f"Lote {lote.id} enviado: {len(reqs)} peticiones, {len(filas)} textos")


def interpretar(texto: str, n: int) -> list[dict | None]:
    """Una entrada por texto del grupo: el dict válido o None. Un texto malo no tumba a los demás."""
    m = re.search(r"\[.*\]", texto, re.S)
    try:
        datos = json.loads(m.group(0)) if m else None
    except json.JSONDecodeError:
        datos = None
    if not isinstance(datos, list) or len(datos) != n:
        return [None] * n
    salida = []
    for d in datos:
        if not isinstance(d, dict):
            salida.append(None)
            continue
        limpio = limpiar(str(d.get("texto") or ""))
        ok = limpio and d.get("tipo") in TIPOS and d.get("sentimiento") in SENTIMIENTOS
        salida.append({"texto": limpio, "tipo": d["tipo"], "sentimiento": d["sentimiento"]} if ok else None)
    return salida


def leer_lote(cliente, lote: dict, out, hechos: set) -> tuple[dict, int, int]:
    uso = {"entrada": 0, "salida": 0, "cache_w": 0, "cache_r": 0}
    ok = descartados = 0
    for r in cliente.messages.batches.results(lote["id"]):
        ids = lote["mapa"][r.custom_id]
        if r.result.type != "succeeded":
            descartados += len(ids)
            continue
        msg = r.result.message
        u = msg.usage
        uso["entrada"] += u.input_tokens
        uso["salida"] += u.output_tokens
        uso["cache_w"] += u.cache_creation_input_tokens or 0
        uso["cache_r"] += u.cache_read_input_tokens or 0
        texto = next((b.text for b in msg.content if b.type == "text"), "")
        datos = [None] * len(ids) if msg.stop_reason in ("max_tokens", "refusal") else interpretar(texto, len(ids))
        for i, d in zip(ids, datos):
            if d is None:
                descartados += 1
            elif i not in hechos:
                out.write(json.dumps({"id": i, "texto_es": d["texto"], "tipo": d["tipo"],
                                      "sentimiento": d["sentimiento"]}, ensure_ascii=False) + "\n")
                hechos.add(i)
                ok += 1
    return uso, ok, descartados


def registrar(uso: dict) -> Decimal:
    costo = (costos.calcular_costo(Tarea.clasificador, uso["entrada"], uso["salida"], uso["cache_w"], uso["cache_r"])
             * DESCUENTO_BATCH).quantize(Decimal("0.000001"))
    costos._registrar_consumo(ConsumoIA(
        tarea="traduccion_dataset", modelo=costos.modelo_para(Tarea.clasificador),
        tokens_entrada=uso["entrada"], tokens_salida=uso["salida"],
        tokens_cache_escritura=uso["cache_w"], tokens_cache_lectura=uso["cache_r"], costo_usd=costo,
    ))
    return costo


def recoger(reprocesar: bool = False):
    """Lee los lotes terminados. Con reprocesar=True vuelve a leer también los ya pagados
    (los resultados duran 29 días en la API) sin registrar de nuevo su costo."""
    cliente = costos.obtener_cliente()
    estado = json.loads(ESTADO.read_text())
    if reprocesar:
        SALIDA.write_text("", encoding="utf-8")
    hechos = set()
    if SALIDA.exists():
        hechos = {json.loads(l)["id"] for l in SALIDA.read_text(encoding="utf-8").splitlines()}
    with open(SALIDA, "a", encoding="utf-8") as out:
        for lote in estado:
            if lote["etiqueta"] == "piloto" or (lote["recogido"] and not reprocesar):
                continue
            info = cliente.messages.batches.retrieve(lote["id"])
            if info.processing_status != "ended":
                print(f"Lote {lote['id']} aún en proceso: {info.request_counts}")
                continue
            uso, ok, descartados = leer_lote(cliente, lote, out, hechos)
            if not lote["recogido"]:
                lote["costo_usd"] = str(registrar(uso))
                lote["recogido"] = True
            print(f"Lote {lote['id']}: {ok} traducidos nuevos, {descartados} descartados, "
                  f"costo {lote['costo_usd']} USD")
    ESTADO.write_text(json.dumps(estado))
    print(f"Total traducidos: {len(hechos)}")


if __name__ == "__main__":
    comando = sys.argv[1]
    if comando == "piloto":
        n = int(sys.argv[2])
        filas = pendientes()
        cfpb = [f for f in filas if f["fuente"] == "cfpb"][: n * 3 // 4]
        b77 = [f for f in filas if f["fuente"] == "banking77"][: n - len(cfpb)]
        enviar(cfpb + b77, "piloto")
    elif comando == "enviar":
        enviar(pendientes(), "completo")
    elif comando == "estado":
        for x in json.loads(ESTADO.read_text()):
            info = costos.obtener_cliente().messages.batches.retrieve(x["id"])
            print(x["id"], x["etiqueta"], info.processing_status, info.request_counts, x.get("costo_usd"))
    elif comando == "recoger":
        recoger()
    elif comando == "reprocesar":
        recoger(reprocesar=True)

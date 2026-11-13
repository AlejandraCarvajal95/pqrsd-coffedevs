"""Paso 8: traduce los candidatos del golden set en inglés y propone el tipo de todos.

La propuesta es solo un punto de partida para quien etiqueta: el tipo definitivo lo pone
una persona en la hoja de etiquetado (paso 9).

    docker compose run --rm --user root -v ./data/datasets:/data/datasets backend \
        python /data/scripts/dataset/08_golden_proponer.py
"""

import importlib.util
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, "/app")
from app.pipeline import costos  # noqa: E402
from app.pipeline.costos import ErrorIA, Tarea  # noqa: E402

DIR = Path("/data/datasets/intermedio")
PROMPTS = Path(__file__).parent / "prompts"
TIPOS = {"peticion", "queja", "reclamo", "sugerencia", "denuncia", "no_aplica"}

spec = importlib.util.spec_from_file_location("traducir", Path(__file__).parent / "06_traducir.py")
traducir = importlib.util.module_from_spec(spec)
spec.loader.exec_module(traducir)


def llamar(tarea: Tarea, prompt: str, contenido: str) -> list[dict] | None:
    sistema = [{"type": "text", "text": prompt, "cache_control": {"type": "ephemeral"}}]
    for espera in (5, 30, 90):
        try:
            r = costos.llamar_claude(tarea, [{"role": "user", "content": contenido}], sistema=sistema)
        except ErrorIA:  # corte de red o límite de peticiones: esperar y reintentar
            time.sleep(espera)
            continue
        m = re.search(r"\[.*\]", r.texto, re.S)
        if m and not r.truncada:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                pass
    return None


def main():
    """Reanudable: cada fila se guarda al terminarla y las ya hechas se saltan."""
    filas = [json.loads(l) for l in (DIR / "golden_candidatos.jsonl").read_text(encoding="utf-8").splitlines()]
    salida = DIR / "golden_propuesto.jsonl"
    hechos = set()
    if salida.exists():
        hechos = {json.loads(l)["id"] for l in salida.read_text(encoding="utf-8").splitlines()}
    prompt_tra = (PROMPTS / "traduccion.md").read_text(encoding="utf-8")
    prompt_ret = (PROMPTS / "reetiquetado.md").read_text(encoding="utf-8")
    with open(salida, "a", encoding="utf-8") as out:
        for f in filas:
            if f["id"] in hechos:
                continue
            if f["idioma"] == "en":
                datos = llamar(Tarea.edicion, prompt_tra, f'<texto n="1">\n{f["texto"]}\n</texto>')
                d = datos[0] if datos else {}
                f["texto_en"] = f["texto"]
                f["texto"] = traducir.limpiar(str(d.get("texto") or "")) or ""
            else:
                contenido = f'<texto n="1">\n{f["texto"][:900]}\n</texto>'
                datos = llamar(Tarea.clasificador, prompt_ret, contenido)
                d = datos[0] if datos else {}
            f["tipo_propuesto"] = d.get("tipo") if d.get("tipo") in TIPOS else None
            out.write(json.dumps(f, ensure_ascii=False) + "\n")
            out.flush()
            print(f["id"], f["tipo_propuesto"], (f["texto"] or "SIN TRADUCCIÓN")[:70], flush=True)


if __name__ == "__main__":
    main()

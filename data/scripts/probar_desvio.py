"""Prueba manual del chat de desvío (US-009) contra la API real.

Recorre data/ejemplos/consultas_desvio.json, envía cada pregunta a
POST /api/chat/consulta (una sesión nueva por pregunta) y muestra la
cobertura obtenida frente a la esperada.

ATENCIÓN: gasta presupuesto de IA real (hasta 12 llamadas al modelo liviano;
las preguntas sin contexto no llaman a Claude). No forma parte de pytest ni
de la CI. Requisitos:
  - el stack arriba (docker compose up -d) con una ANTHROPIC_API_KEY real;
  - la base de conocimiento cargada:
      docker compose run --rm backend python /data/scripts/cargar_conocimiento.py

Uso (desde la raíz del repositorio, en el equipo donde corre Docker):
    python3 data/scripts/probar_desvio.py [--url http://localhost]
"""

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

EJEMPLOS = Path(__file__).resolve().parents[1] / "ejemplos" / "consultas_desvio.json"


def _pedir(url: str, cuerpo: dict | None = None) -> tuple[int, dict]:
    datos = None if cuerpo is None else json.dumps(cuerpo).encode()
    peticion = urllib.request.Request(
        url, data=datos, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(peticion, timeout=120) as respuesta:
            return respuesta.status, json.load(respuesta)
    except urllib.error.HTTPError as error:
        try:
            return error.code, json.load(error)
        except json.JSONDecodeError:
            return error.code, {"detail": f"HTTP {error.code}"}


def main() -> int:
    parser = argparse.ArgumentParser(description="Prueba manual del chat de desvío.")
    parser.add_argument("--url", default="http://localhost")
    base = parser.parse_args().url.rstrip("/")

    estado, salud = _pedir(f"{base}/api/health")
    if estado != 200 or not salud.get("db"):
        print(f"El backend no responde bien en {base}/api/health: {salud}")
        return 1
    _, costo_antes = _pedir(f"{base}/api/costos")

    consultas = json.loads(EJEMPLOS.read_text(encoding="utf-8"))["consultas"]
    aciertos = 0
    print(f"{'#':>2}  {'grupo':<12} {'esperada':<8} {'obtenida':<8} ok  fuentes / pregunta")
    for numero, caso in enumerate(consultas, start=1):
        estado, datos = _pedir(
            f"{base}/api/chat/consulta", {"sesion_id": None, "mensaje": caso["pregunta"]}
        )
        if estado != 200:
            obtenida, detalle = f"HTTP{estado}", datos.get("detail", "")
        else:
            obtenida = datos["cobertura"]
            detalle = ", ".join(f["documento"] for f in datos["fuentes"]) or "-"
        acierto = obtenida == caso["cobertura_esperada"]
        aciertos += acierto
        print(
            f"{numero:>2}  {caso['grupo']:<12} {caso['cobertura_esperada']:<8} "
            f"{obtenida:<8} {'sí' if acierto else 'NO'}  {detalle} / {caso['pregunta']}"
        )

    _, costo_despues = _pedir(f"{base}/api/costos")
    _, metricas = _pedir(f"{base}/api/chat/metricas")
    gasto = costo_despues.get("total_usd", 0) - costo_antes.get("total_usd", 0)
    print(f"\nCoincidencias: {aciertos}/{len(consultas)}")
    print(f"Gasto estimado de esta corrida: {gasto:.6f} USD")
    print(f"Métricas del chat: {json.dumps(metricas, ensure_ascii=False)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

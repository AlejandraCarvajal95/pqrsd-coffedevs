"""Lectura tolerante de las salidas JSON del modelo (desvío y clasificador)."""

import json
import re


def extraer_objeto_json(texto: str) -> dict | None:
    """Devuelve el primer objeto JSON del texto, o None si no hay uno válido.

    Tolera cercos de código (```json) y texto antes o después del objeto.
    """
    limpio = re.sub(r"```(?:json)?", "", texto or "").strip()
    inicio, fin = limpio.find("{"), limpio.rfind("}")
    if inicio == -1 or fin <= inicio:
        return None
    try:
        datos = json.loads(limpio[inicio : fin + 1])
    except json.JSONDecodeError:
        return None
    return datos if isinstance(datos, dict) else None

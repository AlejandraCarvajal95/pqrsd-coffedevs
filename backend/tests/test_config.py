"""US-003: el backend no arranca sin las variables obligatorias."""

import os
import subprocess
import sys
from pathlib import Path

DIRECTORIO_BACKEND = Path(__file__).resolve().parents[1]


def _importar_config(**variables: str) -> subprocess.CompletedProcess:
    entorno = {k: v for k, v in os.environ.items() if k not in ("ANTHROPIC_API_KEY", "DB_URL")}
    entorno.update(variables)
    return subprocess.run(
        [sys.executable, "-c", "import app.config"],
        cwd=DIRECTORIO_BACKEND,
        env=entorno,
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_falla_si_falta_la_api_key():
    resultado = _importar_config(DB_URL="postgresql+psycopg://u:p@db:5432/x")
    assert resultado.returncode == 1
    assert "Faltan variables de entorno obligatorias: ANTHROPIC_API_KEY" in resultado.stderr


def test_variable_vacia_cuenta_como_faltante():
    resultado = _importar_config(ANTHROPIC_API_KEY="", DB_URL="")
    assert resultado.returncode == 1
    assert "ANTHROPIC_API_KEY, DB_URL" in resultado.stderr


def test_no_imprime_secretos():
    secreto = "valor-secreto-que-no-debe-aparecer"
    resultado = _importar_config(ANTHROPIC_API_KEY=secreto, EMBEDDING_DIM="no-es-numero")
    assert resultado.returncode == 1
    assert secreto not in resultado.stderr + resultado.stdout


def test_arranca_con_las_obligatorias():
    resultado = _importar_config(
        ANTHROPIC_API_KEY="clave-falsa", DB_URL="postgresql+psycopg://u:p@db:5432/x"
    )
    assert resultado.returncode == 0, resultado.stderr

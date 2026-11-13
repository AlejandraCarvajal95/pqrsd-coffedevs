"""Carga data/conocimiento/*.md en pgvector (US-005).

Uso recomendado (dentro del contenedor del backend, que ya tiene las
dependencias, la conexión a la base y el volumen del modelo de embeddings):

    docker compose run --rm backend python /data/scripts/cargar_conocimiento.py

Opciones:
    --directorio RUTA     carpeta con los .md (por defecto data/conocimiento)
    --forzar              recalcula todos los embeddings (p. ej. si cambió EMBEDDING_MODELO)
    --eliminar-huerfanos  borra fragmentos de documentos que ya no existen

Se puede ejecutar varias veces: no duplica fragmentos y solo recalcula los que cambiaron.
Las credenciales se leen de las variables de entorno (DB_URL), nunca de este archivo.
"""

import argparse
import logging
import sys
from pathlib import Path

RAIZ_DATA = Path(__file__).resolve().parents[1]


def _agregar_backend_al_path() -> None:
    """Permite `import app` tanto en el repo (backend/) como en el contenedor (/app)."""
    for candidato in (RAIZ_DATA.parent / "backend", Path.cwd()):
        if (candidato / "app" / "main.py").is_file():
            sys.path.insert(0, str(candidato))
            return
    sys.exit("No se encontró el paquete app del backend. Ejecuta el script desde backend/ o /app.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Carga la base de conocimiento en pgvector.")
    parser.add_argument("--directorio", type=Path, default=RAIZ_DATA / "conocimiento")
    parser.add_argument("--forzar", action="store_true")
    parser.add_argument("--eliminar-huerfanos", action="store_true")
    argumentos = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    _agregar_backend_al_path()

    from app.db import SesionLocal, inicializar_base_de_datos
    from app.pipeline.conocimiento import cargar_directorio

    inicializar_base_de_datos()  # crea las tablas si el backend aún no arrancó
    with SesionLocal() as sesion:
        resumen = cargar_directorio(
            sesion,
            argumentos.directorio,
            forzar=argumentos.forzar,
            eliminar_huerfanos=argumentos.eliminar_huerfanos,
        )
        sesion.commit()
    print(f"Carga terminada. {resumen}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

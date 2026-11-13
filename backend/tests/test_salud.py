"""US-001: el endpoint de salud responde bajo /api e informa la base."""

from fastapi.testclient import TestClient

from app.main import app


def test_health_con_base_disponible(base_inicializada):
    with TestClient(app) as cliente:
        respuesta = cliente.get("/api/health")
    assert respuesta.status_code == 200
    assert respuesta.json() == {"estado": "ok", "db": True}


def test_rutas_sin_prefijo_api_no_existen(base_inicializada):
    with TestClient(app) as cliente:
        assert cliente.get("/health").status_code == 404

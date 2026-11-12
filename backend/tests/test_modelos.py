"""US-002: modelo de datos (solo datos ficticios)."""

import re

import pytest
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import DBAPIError

from app.db import engine
from app.models import (
    PQRSD,
    AccionRevision,
    Borrador,
    CanalPQRSD,
    EstadoPQRSD,
    Revision,
    generar_radicado,
)

PATRON_RADICADO = re.compile(r"^PQRSD-\d{4}-[ABCDEFGHJKMNPQRSTUVWXYZ23456789]{6}$")


def _pqrsd_ficticia(**extra) -> PQRSD:
    datos = dict(
        nombre_ciudadano="Ciudadana Ficticia",
        contacto="ficticia@ejemplo.test",
        asunto="Asunto de prueba",
        descripcion="Descripción ficticia",
        canal=CanalPQRSD.formulario,
    )
    datos.update(extra)
    return PQRSD(**datos)


def test_radicado_formato_y_no_consecutivo():
    radicados = {generar_radicado() for _ in range(500)}
    assert all(PATRON_RADICADO.match(r) for r in radicados)
    assert len(radicados) == 500  # sin repetidos en la muestra


def test_existen_las_cuatro_tablas_y_la_extension(base_inicializada):
    tablas = set(inspect(engine).get_table_names())
    assert {"pqrsd", "borradores", "revisiones", "fragmentos_conocimiento"} <= tablas
    with engine.connect() as conexion:
        consulta = text("SELECT count(*) FROM pg_extension WHERE extname = 'vector'")
        assert conexion.scalar(consulta) == 1


def test_inicializar_dos_veces_no_falla(base_inicializada):
    from app.db import inicializar_base_de_datos

    inicializar_base_de_datos(intentos=1)


def test_pqrsd_queda_con_valores_por_defecto(sesion):
    pqrsd = _pqrsd_ficticia(area="Atención al ciudadano", confianza=0.9)
    sesion.add(pqrsd)
    sesion.flush()
    sesion.refresh(pqrsd)
    assert PATRON_RADICADO.match(pqrsd.radicado)
    assert pqrsd.estado == EstadoPQRSD.recibida
    assert pqrsd.fecha_radicacion is not None and pqrsd.fecha_radicacion.tzinfo is not None


def test_confianza_fuera_de_rango_es_rechazada(sesion):
    sesion.add(_pqrsd_ficticia(confianza=1.5))
    with pytest.raises(DBAPIError):
        sesion.flush()


def test_editar_borrador_conserva_original_y_registra_revision(sesion):
    pqrsd = _pqrsd_ficticia()
    sesion.add(pqrsd)
    sesion.flush()
    borrador = Borrador(
        pqrsd_id=pqrsd.id, texto_original="Propuesta IA", texto_actual="Propuesta IA",
        modelo="modelo-de-prueba",
    )
    sesion.add(borrador)
    sesion.flush()

    borrador.editar("Texto final revisado", revisor="Revisor Ficticio")
    sesion.flush()
    sesion.expire_all()

    guardado = sesion.get(Borrador, borrador.id)
    assert guardado.texto_original == "Propuesta IA"
    assert guardado.texto_actual == "Texto final revisado"
    revisiones = sesion.scalars(select(Revision).where(Revision.borrador_id == borrador.id)).all()
    assert [(r.accion, r.texto_final) for r in revisiones] == [
        (AccionRevision.editado, "Texto final revisado")
    ]


def test_texto_original_no_se_puede_modificar_por_sql(sesion):
    pqrsd = _pqrsd_ficticia()
    sesion.add(pqrsd)
    sesion.flush()
    borrador = Borrador(
        pqrsd_id=pqrsd.id, texto_original="Original", texto_actual="Original", modelo="m"
    )
    sesion.add(borrador)
    sesion.flush()
    with pytest.raises(DBAPIError, match="texto_original"):
        sesion.execute(
            text("UPDATE borradores SET texto_original = 'x' WHERE id = :id"), {"id": borrador.id}
        )

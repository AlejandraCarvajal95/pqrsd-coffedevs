"""Panel administrativo: acceso (US-022), bandeja (US-017, US-019, US-020) y métricas.

Solo datos ficticios y ninguna llamada real a Claude.
"""

import contextlib
import csv
import io
import time
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import select, text

from app.api import admin, bandeja
from app.config import configuracion
from app.db import obtener_sesion
from app.main import app
from app.models import (
    PQRSD,
    AccionRevision,
    Borrador,
    CanalPQRSD,
    ConsumoIA,
    EstadoPQRSD,
    FragmentoConocimiento,
    Revision,
    TipoPQRSD,
)
from app.pipeline import dias_habiles, generador, orquestador

CLAVE = "clave-de-prueba-del-panel"
CARTA_LIMPIA = "Señora Ciudadana: la cuota se cobra una vez al mes [F1]. Atentamente, Ana Ficticia."
CARTA_CON_PENDIENTES = (
    f"{generador.INICIO_AVISO}\n- {generador.AVISO_SIN_CITAS}\n{generador.FIN_AVISO}\n\n"
    "Señora Ciudadana: [COMPLETAR: resultado de la verificación].\n\n"
    "[Nombre del funcionario]\n[Cargo] — Área responsable"
)


@pytest.fixture
def panel(sesion, monkeypatch):
    """Cliente HTTP sobre la sesión de la prueba, con la clave del panel definida."""
    monkeypatch.setattr(configuracion, "admin_usuario", "admin")
    monkeypatch.setattr(configuracion, "admin_clave", SecretStr(CLAVE))
    admin.limitador_acceso.reiniciar()
    app.dependency_overrides[obtener_sesion] = lambda: sesion
    http = TestClient(app)
    token = http.post("/api/admin/login", json={"usuario": "admin", "clave": CLAVE}).json()[
        "token"
    ]
    yield http, {"Authorization": f"Bearer {token}"}, sesion
    app.dependency_overrides.clear()
    admin.limitador_acceso.reiniciar()


def _pqrsd(sesion, dias_para_vencer: int | None = 12, **extra) -> PQRSD:
    """PQRSD ficticia que vence en `dias_para_vencer` días hábiles (negativo: ya venció)."""
    hoy = dias_habiles.fecha_colombia()
    if dias_para_vencer is None:
        vencimiento = None
    elif dias_para_vencer < 0:
        vencimiento = hoy + timedelta(days=dias_para_vencer)
    else:
        vencimiento = dias_habiles.sumar_dias_habiles(hoy, dias_para_vencer)
    datos = dict(
        nombre_ciudadano="Ciudadana Ficticia",
        contacto="ficticia@ejemplo.test",
        asunto="Cobro doble de la cuota de manejo",
        descripcion="Me cobraron la cuota de manejo de la tarjeta dos veces en el mismo mes.",
        canal=CanalPQRSD.formulario,
        tipo=TipoPQRSD.reclamo,
        area="Tarjetas de Crédito",
        confianza=0.9,
        tema="cobros_comisiones_intereses",
        sentimiento="negativo",
        riesgo_fraude=False,
        estado=EstadoPQRSD.clasificada,
        fecha_vencimiento=vencimiento,
    )
    datos.update(extra)
    pqrsd = PQRSD(**datos)
    sesion.add(pqrsd)
    sesion.flush()
    return pqrsd


def _borrador(sesion, pqrsd, texto=CARTA_LIMPIA, citas=None) -> Borrador:
    borrador = Borrador(
        pqrsd_id=pqrsd.id, texto_original=texto, texto_actual=texto, citas=citas or [],
        modelo="modelo-borrador-de-prueba", tokens_entrada=1500, tokens_salida=600,
    )  # fmt: skip
    sesion.add(borrador)
    pqrsd.estado = EstadoPQRSD.borrador_listo
    sesion.flush()
    return borrador


# --- US-022: acceso ----------------------------------------------------------


@pytest.mark.parametrize(
    "ruta",
    ["/api/bandeja", "/api/bandeja/exportar/csv", "/api/bandeja/PQRSD-2026-AAAAAA",
     "/api/metricas", "/api/admin/sesion"],
)  # fmt: skip
def test_sin_sesion_el_panel_responde_401(panel, ruta):
    http, _, _ = panel
    assert http.get(ruta).status_code == 401
    assert http.get(ruta, headers={"Authorization": "Bearer no-es-un-token"}).status_code == 401


def test_los_endpoints_del_ciudadano_siguen_abiertos(panel):
    http, _, sesion = panel
    pqrsd = _pqrsd(sesion)
    assert http.get("/api/health").status_code == 200
    assert http.get(f"/api/pqrsd/{pqrsd.radicado}").status_code == 200
    assert http.get("/api/admin/modo").status_code == 200


def test_login_valida_usuario_y_clave(panel):
    http, cabeceras, _ = panel
    assert http.get("/api/admin/sesion", headers=cabeceras).json() == {"usuario": "admin"}
    for usuario, clave in (("admin", "otra-clave"), ("otro", CLAVE), ("", "")):
        respuesta = http.post("/api/admin/login", json={"usuario": usuario, "clave": clave})
        assert respuesta.status_code == 401
        assert CLAVE not in respuesta.text


def test_token_vencido_o_alterado_no_sirve(panel):
    http, cabeceras, _ = panel
    vencido, _ = admin.crear_token("admin", CLAVE, ahora=time.time() - 13 * 3600)
    cabecera = {"Authorization": f"Bearer {vencido}"}
    assert http.get("/api/bandeja", headers=cabecera).status_code == 401
    token = cabeceras["Authorization"].removeprefix("Bearer ")
    carga, firma = token.split(".")
    otra_firma = firma[:-1] + ("0" if firma[-1] != "0" else "1")
    alterado = {"Authorization": f"Bearer {carga}.{otra_firma}"}
    assert http.get("/api/bandeja", headers=alterado).status_code == 401
    # Un token firmado con otra clave tampoco sirve.
    ajeno, _ = admin.crear_token("admin", "otra-clave")
    cabecera = {"Authorization": f"Bearer {ajeno}"}
    assert http.get("/api/bandeja", headers=cabecera).status_code == 401


def test_limite_de_intentos_de_acceso(panel):
    http, _, _ = panel
    admin.limitador_acceso.reiniciar()
    estados = [
        http.post("/api/admin/login", json={"usuario": "admin", "clave": "x"}).status_code
        for _ in range(11)
    ]
    assert estados[:10] == [401] * 10 and estados[10] == 429


def test_sin_clave_propia_solo_desarrollo_usa_la_de_demo(panel, monkeypatch):
    http, cabeceras, _ = panel
    monkeypatch.setattr(configuracion, "admin_clave", None)

    monkeypatch.setattr(configuracion, "app_env", "desarrollo")
    modo = http.get("/api/admin/modo").json()
    assert modo["disponible"] and modo["credenciales_demo"]
    datos = {"usuario": modo["usuario_demo"], "clave": modo["clave_demo"]}
    assert http.post("/api/admin/login", json=datos).status_code == 200

    # Fuera de desarrollo, sin ADMIN_CLAVE el panel queda cerrado y no revela nada.
    monkeypatch.setattr(configuracion, "app_env", "evento")
    modo = http.get("/api/admin/modo").json()
    assert modo == {
        "disponible": False, "credenciales_demo": False, "usuario_demo": None, "clave_demo": None,
    }  # fmt: skip
    assert http.post("/api/admin/login", json=datos).status_code == 503
    assert http.get("/api/bandeja", headers=cabeceras).status_code == 503


def test_con_clave_propia_no_se_anuncian_credenciales(panel):
    http, _, _ = panel
    modo = http.get("/api/admin/modo").json()
    assert modo["disponible"] and not modo["credenciales_demo"] and modo["clave_demo"] is None


# --- US-017 y US-019: bandeja por urgencia, semáforo y filtros ---------------


@pytest.fixture
def varias(panel):
    http, cabeceras, sesion = panel
    casos = {
        "verde": _pqrsd(sesion, 12, asunto="Solicitud de paz y salvo", area="Cartera",
                        tipo=TipoPQRSD.peticion),
        "amarillo": _pqrsd(sesion, 5, asunto="Cobro doble de cuota"),
        "rojo": _pqrsd(sesion, 1, asunto="Compra no reconocida", riesgo_fraude=True,
                       area="Jurídica", tipo=TipoPQRSD.denuncia),
        "vencida": _pqrsd(sesion, -10, asunto="Reporte en centrales de riesgo", area="Cartera"),
        "revision": _pqrsd(sesion, 9, asunto="Texto ambiguo", tipo=None, area=None,
                           estado=EstadoPQRSD.pendiente_revision_clasificacion),
        "respondida": _pqrsd(sesion, 2, asunto="Ya atendida", estado=EstadoPQRSD.respondida),
    }  # fmt: skip
    return http, cabeceras, sesion, casos


def _radicados(respuesta) -> list[str]:
    return [item["radicado"] for item in respuesta.json()["items"]]


def test_la_bandeja_ordena_por_urgencia_y_calcula_el_semaforo(varias):
    http, cabeceras, _, casos = varias
    respuesta = http.get("/api/bandeja", headers=cabeceras)
    assert respuesta.status_code == 200
    orden = ["vencida", "rojo", "amarillo", "revision", "verde"]  # sin la respondida
    assert _radicados(respuesta) == [casos[clave].radicado for clave in orden]

    por_radicado = {item["radicado"]: item for item in respuesta.json()["items"]}
    esperado = {
        "vencida": ("rojo", True), "rojo": ("rojo", False), "amarillo": ("amarillo", False),
        "revision": ("verde", False), "verde": ("verde", False),
    }  # fmt: skip
    for clave, (color, vencida) in esperado.items():
        item = por_radicado[casos[clave].radicado]
        assert (item["semaforo"], item["vencida"]) == (color, vencida), clave
    assert por_radicado[casos["rojo"].radicado]["dias_habiles_restantes"] == 1
    assert por_radicado[casos["amarillo"].radicado]["dias_habiles_restantes"] == 5
    assert por_radicado[casos["vencida"].radicado]["dias_habiles_restantes"] < 0
    assert por_radicado[casos["revision"].radicado]["requiere_revision"] is True
    assert respuesta.json()["opciones"]["areas"] == [
        "Tarjetas de Crédito", "Cartera", "Seguros de Vida", "Jurídica",
    ]  # fmt: skip


def test_filtros_de_la_bandeja(varias):
    http, cabeceras, _, casos = varias

    def filtrar(**parametros) -> set[str]:
        respuesta = http.get("/api/bandeja", headers=cabeceras, params=parametros)
        assert respuesta.status_code == 200
        return set(_radicados(respuesta))

    def radicados(*claves) -> set[str]:
        return {casos[clave].radicado for clave in claves}

    assert filtrar(area="Cartera") == radicados("verde", "vencida")
    assert filtrar(tipo="denuncia") == radicados("rojo")
    assert filtrar(semaforo="rojo") == radicados("rojo", "vencida")
    assert filtrar(semaforo="amarillo") == radicados("amarillo")
    assert filtrar(riesgo_fraude="true") == radicados("rojo")
    assert filtrar(estado="pendiente_revision_clasificacion") == radicados("revision")
    assert filtrar(estado="respondida") == radicados("respondida")  # las enviadas
    assert filtrar(incluir_respondidas="true") == radicados(*casos)
    assert filtrar(q=casos["verde"].radicado.lower()) == radicados("verde")
    assert filtrar(q="centrales de riesgo") == radicados("vencida")
    assert filtrar(q="no existe este texto") == set()
    invalido = http.get("/api/bandeja", headers=cabeceras, params={"semaforo": "azul"})
    assert invalido.status_code == 422


# --- US-020: detalle, edición y aprobación -----------------------------------


def test_detalle_con_clasificacion_borrador_y_fuentes(panel, conocimiento_banco):
    http, cabeceras, sesion = panel
    fragmento = sesion.scalars(select(FragmentoConocimiento)).first()
    pqrsd = _pqrsd(sesion, 5)
    cita = {"etiqueta": "F1", "fragmento_id": str(fragmento.id), "documento": fragmento.documento,
            "seccion": fragmento.seccion, "similitud": 0.61}  # fmt: skip
    _borrador(sesion, pqrsd, texto=CARTA_CON_PENDIENTES, citas=[cita])

    datos = http.get(f"/api/bandeja/{pqrsd.radicado.lower()}", headers=cabeceras).json()

    assert datos["radicado"] == pqrsd.radicado and datos["contacto"] == "ficticia@ejemplo.test"
    assert datos["descripcion"] == pqrsd.descripcion
    assert (datos["semaforo"], datos["dias_habiles_restantes"]) == ("amarillo", 5)
    assert datos["clasificacion"]["tipo"] == "reclamo"
    assert datos["clasificacion"]["area"] == "Tarjetas de Crédito"
    assert datos["clasificacion"]["sentimiento"] == "negativo"
    borrador = datos["borrador"]
    assert borrador["texto_original"] == borrador["texto_actual"] == CARTA_CON_PENDIENTES
    assert borrador["editado"] is False
    assert borrador["avisos"] == [generador.AVISO_SIN_CITAS]
    assert len(borrador["bloqueos_aprobacion"]) == 3  # aviso, campo por completar y firma
    assert borrador["citas"] == [{**cita, "contenido": fragmento.contenido}]
    assert datos["respuesta"] is None

    assert http.get("/api/bandeja/PQRSD-2026-ZZZZZZ", headers=cabeceras).status_code == 404


def test_editar_el_borrador_conserva_el_texto_original(panel):
    http, cabeceras, sesion = panel
    pqrsd = _pqrsd(sesion)
    borrador = _borrador(sesion, pqrsd)

    respuesta = http.put(
        f"/api/bandeja/{pqrsd.radicado}/borrador", headers=cabeceras,
        json={"texto": "Texto corregido por la persona [F1]."},
    )  # fmt: skip

    assert respuesta.status_code == 200
    assert respuesta.json()["borrador"]["editado"] is True
    fila = sesion.execute(
        text("SELECT texto_original, texto_actual FROM borradores WHERE id = :id"),
        {"id": borrador.id},
    ).one()
    assert fila.texto_original == CARTA_LIMPIA
    assert fila.texto_actual == "Texto corregido por la persona [F1]."
    revision = sesion.scalars(select(Revision).where(Revision.borrador_id == borrador.id)).one()
    assert (revision.accion, revision.revisor) == (AccionRevision.editado, "admin")
    assert pqrsd.estado == EstadoPQRSD.borrador_listo  # editar no aprueba

    ruta = f"/api/bandeja/{pqrsd.radicado}/borrador"
    assert http.put(ruta, headers=cabeceras, json={"texto": "   "}).status_code == 422
    sin_borrador = _pqrsd(sesion)
    ruta = f"/api/bandeja/{sin_borrador.radicado}/borrador"
    assert http.put(ruta, headers=cabeceras, json={"texto": "Hola"}).status_code == 404


def test_no_se_aprueba_un_texto_con_avisos_o_campos_por_completar(panel):
    http, cabeceras, sesion = panel
    pqrsd = _pqrsd(sesion)
    _borrador(sesion, pqrsd, texto=CARTA_CON_PENDIENTES)

    respuesta = http.post(f"/api/bandeja/{pqrsd.radicado}/aprobar", headers=cabeceras)

    assert respuesta.status_code == 422
    for parte in ("aviso automático", "[COMPLETAR", "firma"):
        assert parte in respuesta.json()["detail"]
    assert pqrsd.estado == EstadoPQRSD.borrador_listo
    assert sesion.scalars(select(Revision)).all() == []


def test_aprobar_deja_la_pqrsd_respondida_y_registra_quien_aprobo(panel):
    http, cabeceras, sesion = panel
    pqrsd = _pqrsd(sesion, 2)
    borrador = _borrador(sesion, pqrsd, texto=CARTA_CON_PENDIENTES)
    final = "Señora Ciudadana: reversamos el cobro duplicado [F1]. Atentamente, Ana Ficticia."

    # Aprueba enviando el texto final ya corregido, en un solo paso.
    respuesta = http.post(
        f"/api/bandeja/{pqrsd.radicado}/aprobar", headers=cabeceras, json={"texto": final}
    )

    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert datos["estado"] == "respondida" and datos["semaforo"] is None
    # Al ciudadano le llega el texto sin las etiquetas de cita.
    assert datos["respuesta"]["texto_final"] == (
        "Señora Ciudadana: reversamos el cobro duplicado. Atentamente, Ana Ficticia."
    )
    assert datos["respuesta"]["revisor"] == "admin" and datos["fecha_respuesta"]
    acciones = [r["accion"] for r in datos["revisiones"]]
    assert acciones == ["editado", "aprobado"]
    sesion.refresh(borrador)
    assert borrador.texto_original == CARTA_CON_PENDIENTES and borrador.texto_actual == final

    # El ciudadano ya la ve como respondida, y no se puede volver a tocar.
    assert http.get(f"/api/pqrsd/{pqrsd.radicado}").json()["estado"] == "respondida"
    base = f"/api/bandeja/{pqrsd.radicado}"
    assert http.post(f"{base}/aprobar", headers=cabeceras).status_code == 409
    assert http.put(f"{base}/borrador", headers=cabeceras, json={"texto": "x"}).status_code == 409
    cambio = {"tipo": "queja", "area": "Cartera"}
    assert http.patch(f"{base}/clasificacion", headers=cabeceras, json=cambio).status_code == 409


def test_no_se_aprueba_sin_borrador(panel):
    http, cabeceras, sesion = panel
    pqrsd = _pqrsd(sesion)
    ruta = f"/api/bandeja/{pqrsd.radicado}/aprobar"
    assert http.post(ruta, headers=cabeceras).status_code == 409
    assert pqrsd.estado == EstadoPQRSD.clasificada


# --- Confirmar o corregir la clasificación -----------------------------------


def test_confirmar_la_clasificacion_dispara_el_borrador(panel, monkeypatch):
    http, cabeceras, sesion = panel
    disparos: list = []
    monkeypatch.setattr(orquestador, "redactar_borrador", disparos.append)
    monkeypatch.setattr(configuracion, "plazos_por_tipo", {"peticion": 10})
    pqrsd = _pqrsd(
        sesion, 12, tipo=None, area=None, confianza=None,
        estado=EstadoPQRSD.pendiente_revision_clasificacion,
        clasificacion_detalle={"motivos_revision": ["baja_confianza"], "svm": {}},
    )  # fmt: skip
    sesion.refresh(pqrsd)

    respuesta = http.patch(
        f"/api/bandeja/{pqrsd.radicado}/clasificacion", headers=cabeceras,
        json={"tipo": "peticion", "area": "Cartera"},
    )  # fmt: skip

    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert datos["borrador_en_proceso"] is True and disparos == [pqrsd.id]
    assert (datos["estado"], datos["tipo"]) == ("clasificada", "peticion")
    assert datos["area"] == "Cartera"
    assert datos["requiere_revision"] is False
    # El plazo se recalcula con el tipo confirmado (10 días hábiles para "peticion").
    esperado = dias_habiles.calcular_vencimiento(pqrsd.fecha_radicacion, ["peticion"])
    assert datos["fecha_vencimiento"] == esperado.isoformat()
    detalle = datos["clasificacion"]
    assert detalle["motivos_revision"] == []
    assert detalle["revision_humana"]["revisor"] == "admin"
    assert detalle["revision_humana"]["tipo_anterior"] is None

    ruta = f"/api/bandeja/{pqrsd.radicado}/clasificacion"
    invalida = {"tipo": "peticion", "area": "Área Inventada"}
    assert http.patch(ruta, headers=cabeceras, json=invalida).status_code == 422
    invalida = {"tipo": "otro", "area": "Cartera"}
    assert http.patch(ruta, headers=cabeceras, json=invalida).status_code == 422


def test_corregir_la_clasificacion_con_borrador_no_lo_regenera(panel, monkeypatch):
    http, cabeceras, sesion = panel
    disparos: list = []
    monkeypatch.setattr(orquestador, "redactar_borrador", disparos.append)
    pqrsd = _pqrsd(sesion)
    _borrador(sesion, pqrsd)

    datos = http.patch(
        f"/api/bandeja/{pqrsd.radicado}/clasificacion", headers=cabeceras,
        json={"tipo": "queja", "area": "Jurídica"},
    ).json()  # fmt: skip

    assert disparos == [] and datos["borrador_en_proceso"] is False
    assert (datos["estado"], datos["tipo"]) == ("borrador_listo", "queja")
    assert datos["area"] == "Jurídica"
    assert datos["clasificacion"]["revision_humana"]["tipo_anterior"] == "reclamo"


def test_confirmar_la_clasificacion_genera_el_borrador_con_claude_falso(
    panel, ia_falsa, conocimiento_banco, monkeypatch
):
    http, cabeceras, sesion = panel
    monkeypatch.setattr(orquestador, "fabrica_sesion", lambda: contextlib.nullcontext(sesion))
    cliente = ia_falsa.usar("La cuota de manejo se cobra una sola vez cada mes [F1].")
    pqrsd = _pqrsd(sesion, tipo=None, area=None,
                   estado=EstadoPQRSD.pendiente_revision_clasificacion)  # fmt: skip

    http.patch(
        f"/api/bandeja/{pqrsd.radicado}/clasificacion", headers=cabeceras,
        json={"tipo": "reclamo", "area": "Tarjetas de Crédito"},
    )  # fmt: skip

    datos = http.get(f"/api/bandeja/{pqrsd.radicado}", headers=cabeceras).json()
    assert datos["estado"] == "borrador_listo"
    assert "[F1]" in datos["borrador"]["texto_original"]
    assert datos["borrador"]["citas"][0]["contenido"]
    assert len(cliente.llamadas) == 1
    assert cliente.llamadas[0]["model"] == "modelo-borrador-de-prueba"


def test_generar_el_borrador_a_pedido(panel, monkeypatch):
    http, cabeceras, sesion = panel
    disparos: list = []
    monkeypatch.setattr(orquestador, "redactar_borrador", disparos.append)
    clasificada = _pqrsd(sesion)
    ruta = f"/api/bandeja/{clasificada.radicado}/borrador/generar"
    assert http.post(ruta, headers=cabeceras).status_code == 202
    assert disparos == [clasificada.id]

    con_borrador = _pqrsd(sesion)
    _borrador(sesion, con_borrador)
    en_revision = _pqrsd(sesion, estado=EstadoPQRSD.pendiente_revision_clasificacion)
    for pqrsd in (con_borrador, en_revision):
        ruta = f"/api/bandeja/{pqrsd.radicado}/borrador/generar"
        assert http.post(ruta, headers=cabeceras).status_code == 409
    assert disparos == [clasificada.id]


# --- Exportación CSV ---------------------------------------------------------


def test_exportar_csv(panel):
    http, cabeceras, sesion = panel
    abierta = _pqrsd(sesion, 5, riesgo_fraude=True)
    vencida = _pqrsd(sesion, -10)
    respondida = _pqrsd(sesion, 2)
    _borrador(sesion, respondida)
    final = "=Respuesta final, con coma y \"comillas\". Atentamente, Ana Ficticia."
    http.post(
        f"/api/bandeja/{respondida.radicado}/aprobar", headers=cabeceras, json={"texto": final}
    )

    respuesta = http.get("/api/bandeja/exportar/csv", headers=cabeceras)

    assert respuesta.status_code == 200
    assert respuesta.headers["content-type"].startswith("text/csv")
    assert "attachment" in respuesta.headers["content-disposition"]
    assert respuesta.content.startswith(b"\xef\xbb\xbf")  # BOM para Excel
    filas = list(csv.DictReader(io.StringIO(respuesta.content.decode("utf-8-sig"))))
    assert list(filas[0]) == list(bandeja.COLUMNAS_CSV)
    por_radicado = {fila["radicado"]: fila for fila in filas}
    assert set(por_radicado) == {abierta.radicado, vencida.radicado, respondida.radicado}
    # Los días de atraso son un número negativo, no una fórmula: van sin apóstrofo.
    assert int(por_radicado[vencida.radicado]["dias_habiles_restantes"]) < 0
    fila = por_radicado[abierta.radicado]
    assert (fila["estado"], fila["tipo"], fila["area"]) == (
        "clasificada", "reclamo", "Tarjetas de Crédito",
    )  # fmt: skip
    assert (fila["riesgo_fraude"], fila["semaforo"], fila["dias_habiles_restantes"]) == (
        "sí", "amarillo", "5",
    )  # fmt: skip
    assert fila["fecha_vencimiento"] == abierta.fecha_vencimiento.isoformat()
    assert fila["respuesta_final"] == ""
    fila = por_radicado[respondida.radicado]
    assert fila["estado"] == "respondida" and fila["fecha_respuesta"]
    # La celda que empieza por "=" va con apóstrofo para que Excel no la tome como fórmula.
    assert fila["respuesta_final"] == "'" + final
    # El CSV no lleva datos de contacto del ciudadano.
    assert "ficticia@ejemplo.test" not in respuesta.text
    assert "Ciudadana Ficticia" not in respuesta.text


# --- Métricas ----------------------------------------------------------------


def test_metricas_del_panel(varias):
    http, cabeceras, sesion, casos = varias
    sesion.add(ConsumoIA(tarea="generador", modelo="m", costo_usd=1.25))
    sesion.flush()

    datos = http.get("/api/metricas", headers=cabeceras).json()

    assert datos["tarjetas"] == {
        "activas": 5, "por_vencer": 2, "pendientes_revision": 1, "con_borrador_listo": 0,
        "respondidas": 1, "riesgo_fraude": 1,
    }  # fmt: skip
    assert datos["por_semaforo"] == {
        "verde": 2, "amarillo": 1, "rojo": 1, "vencidas": 1, "sin_fecha": 0,
    }  # fmt: skip
    assert datos["por_estado"]["clasificada"] == 4
    assert datos["por_estado"]["respondida"] == 1
    assert datos["por_estado"]["recibida"] == 0
    areas = {fila["nombre"]: fila["total"] for fila in datos["por_area"]}
    assert areas == {"Tarjetas de Crédito": 2, "Cartera": 2, "Jurídica": 1, "sin clasificar": 1}
    tipos = {fila["nombre"]: fila["total"] for fila in datos["por_tipo"]}
    assert tipos == {"reclamo": 3, "peticion": 1, "denuncia": 1, "sin clasificar": 1}

    # Calendario: solo las activas, agrupadas por fecha y en orden.
    fechas = [dia["fecha"] for dia in datos["calendario"]]
    assert fechas == sorted(fechas) and sum(dia["total"] for dia in datos["calendario"]) == 5
    primero = datos["calendario"][0]
    assert primero["fecha"] == casos["vencida"].fecha_vencimiento.isoformat()
    assert primero["pqrsd"][0]["radicado"] == casos["vencida"].radicado
    assert primero["pqrsd"][0]["vencida"] is True
    assert casos["respondida"].radicado not in str(datos["calendario"])

    presupuesto = datos["presupuesto_ia"]
    assert presupuesto["total_usd"] == pytest.approx(1.25)
    assert presupuesto["tope_usd"] == configuracion.gasto_tope_usd
    assert presupuesto["por_tarea"][0]["tarea"] == "generador"


# --- US-016: el vencimiento se calcula al radicar ----------------------------


def test_al_radicar_queda_la_fecha_de_vencimiento(panel, monkeypatch):
    http, _, sesion = panel
    monkeypatch.setattr(orquestador, "procesar_pqrsd", lambda pqrsd_id: None)
    respuesta = http.post(
        "/api/pqrsd",
        json={
            "nombre_ciudadano": "Ciudadana Ficticia",
            "contacto": "ficticia@ejemplo.test",
            "asunto": "Cobro de cuota de manejo",
            "descripcion": "Me cobraron la cuota de manejo dos veces en el mismo mes.",
        },
    )
    assert respuesta.status_code == 201
    datos = respuesta.json()
    pqrsd = sesion.scalars(select(PQRSD).where(PQRSD.radicado == datos["radicado"])).one()
    esperado = dias_habiles.sumar_dias_habiles(
        dias_habiles.fecha_colombia(pqrsd.fecha_radicacion), configuracion.plazo_dias_habiles
    )
    assert pqrsd.fecha_vencimiento == esperado
    assert datos["fecha_vencimiento"] == esperado.isoformat()
    assert dias_habiles.es_habil(esperado)
    # El ciudadano la ve en la consulta de estado.
    estado = http.get(f"/api/pqrsd/{datos['radicado']}").json()
    assert estado["fecha_vencimiento"] == esperado.isoformat()


def test_respuesta_aprobada_se_descarga_en_pdf_en_el_panel_y_para_el_ciudadano(panel):
    http, cabeceras, sesion = panel
    pqrsd = _pqrsd(sesion, 2)
    _borrador(sesion, pqrsd, texto=CARTA_CON_PENDIENTES)
    ruta_panel = f"/api/bandeja/{pqrsd.radicado}/respuesta.pdf"
    ruta_ciudadano = f"/api/pqrsd/{pqrsd.radicado}/respuesta.pdf"

    # Antes de aprobar no hay carta: ni en el panel ni para el ciudadano.
    assert http.get(ruta_panel, headers=cabeceras).status_code == 404
    assert http.get(ruta_ciudadano).status_code == 404

    final = "Señora Ciudadana: reversamos el cobro duplicado [F1]. Atentamente, Ana Ficticia."
    http.post(f"/api/bandeja/{pqrsd.radicado}/aprobar", headers=cabeceras, json={"texto": final})

    assert http.get(ruta_panel).status_code == 401  # el del panel exige sesión
    for ruta, cab in ((ruta_panel, cabeceras), (ruta_ciudadano, {})):
        en_linea = http.get(ruta, headers=cab)
        assert en_linea.status_code == 200
        assert en_linea.headers["content-type"] == "application/pdf"
        assert en_linea.content.startswith(b"%PDF")
        assert en_linea.headers["content-disposition"].startswith("inline;")
        descarga = http.get(ruta, headers=cab, params={"descargar": True})
        assert descarga.headers["content-disposition"] == (
            f'attachment; filename="respuesta-{pqrsd.radicado}.pdf"'
        )


def test_el_pdf_lleva_el_banco_y_el_texto_final_sin_etiquetas():
    import zlib
    from datetime import UTC, datetime

    from app.pdf_respuesta import generar_pdf_respuesta

    contenido = generar_pdf_respuesta(
        radicado="PQRSD-2026-ABC234",
        fecha_respuesta=datetime(2026, 11, 13, 15, tzinfo=UTC),
        texto="Señora Ciudadana: reversamos el cobro — en 5 días.\n\nAtentamente, Ana Ficticia.",
    )
    texto = b""
    for bloque in contenido.split(b"stream")[1::2]:
        try:
            texto += zlib.decompress(bloque.strip(b"\r\n"))
        except zlib.error:
            texto += bloque
    assert b"Banco Andino Ficticio" in texto
    assert b"PQRSD-2026-ABC234" in texto
    assert b"13 de noviembre de 2026" in texto
    assert "reversamos el cobro - en 5 días.".encode("latin-1") in texto

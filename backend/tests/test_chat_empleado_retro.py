"""US-021 (chat del empleado) y US-023 (aprendizajes en la base de conocimiento).

Claude y el modelo de embeddings son falsos, y los .md se escriben en una
carpeta temporal: no se gasta presupuesto ni se toca data/conocimiento/.
"""

import re
from pathlib import Path

import anthropic
import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import func, select

from app.api import admin
from app.config import configuracion
from app.db import obtener_sesion
from app.main import app
from app.models import (
    PQRSD,
    Borrador,
    CanalPQRSD,
    ConsumoIA,
    EstadoPQRSD,
    FragmentoConocimiento,
    TipoPQRSD,
)
from app.pipeline import chat_empleado, rag, retroalimentacion
from app.pipeline.conocimiento import cargar_directorio

CLAVE = "clave-de-prueba-del-panel"
CARTA = "Señora Ciudadana: la cuota de manejo se cobra una sola vez cada mes [F1]. Atentamente."
PROPUESTA = (
    "Lamentamos la molestia. La cuota de manejo se cobra una sola vez cada mes [F1] y, "
    "si se cobra dos veces, el banco reversa el duplicado [F2]. Según otra norma [F9]."
)
SALIDA_CON_PROPUESTA = (
    "Hice el tono más empático y expliqué la reversión.\n\n"
    f"<borrador_propuesto>\n{PROPUESTA}\n</borrador_propuesto>"
)


@pytest.fixture
def panel(sesion, ia_falsa, conocimiento_banco, monkeypatch, tmp_path):
    """Cliente HTTP con sesión del panel, Claude falso y carpeta temporal de aprendizajes."""
    monkeypatch.setattr(configuracion, "admin_usuario", "admin")
    monkeypatch.setattr(configuracion, "admin_clave", SecretStr(CLAVE))
    monkeypatch.setattr(configuracion, "retroalimentacion_dir", str(tmp_path / "retro"))
    admin.limitador_acceso.reiniciar()
    app.dependency_overrides[obtener_sesion] = lambda: sesion
    http = TestClient(app)
    token = http.post("/api/admin/login", json={"usuario": "admin", "clave": CLAVE}).json()[
        "token"
    ]
    ia_falsa.http = http
    ia_falsa.cabeceras = {"Authorization": f"Bearer {token}"}
    ia_falsa.carpeta = tmp_path / "retro"
    yield ia_falsa
    app.dependency_overrides.clear()
    admin.limitador_acceso.reiniciar()


def _pqrsd(sesion, **extra) -> PQRSD:
    datos = dict(
        nombre_ciudadano="Ciudadana Ficticia",
        contacto="ficticia@ejemplo.test",
        asunto="Cobro doble de la cuota de manejo de la tarjeta",
        descripcion="Me cobraron la cuota de manejo de la tarjeta dos veces en el mismo mes.",
        canal=CanalPQRSD.formulario,
        tipo=TipoPQRSD.reclamo,
        area="Tarjetas de Crédito",
        confianza=0.9,
        tema="cobros_comisiones_intereses",
        sentimiento="negativo",
        riesgo_fraude=False,
        estado=EstadoPQRSD.clasificada,
    )
    datos.update(extra)
    pqrsd = PQRSD(**datos)
    sesion.add(pqrsd)
    sesion.flush()
    return pqrsd


def _fragmento(sesion, seccion: str) -> FragmentoConocimiento:
    return sesion.scalars(
        select(FragmentoConocimiento).where(FragmentoConocimiento.seccion == seccion)
    ).one()


def _con_borrador(sesion, texto=CARTA, **extra) -> tuple[PQRSD, Borrador]:
    """PQRSD con un borrador que cita [F1] = fragmento "Cuota de manejo"."""
    pqrsd = _pqrsd(sesion, **extra)
    fragmento = _fragmento(sesion, "Cuota de manejo")
    cita = {"etiqueta": "F1", "fragmento_id": str(fragmento.id), "documento": fragmento.documento,
            "seccion": fragmento.seccion, "similitud": 0.7}  # fmt: skip
    borrador = Borrador(pqrsd_id=pqrsd.id, texto_original=texto, texto_actual=texto,
                        citas=[cita], modelo="modelo-borrador-de-prueba")  # fmt: skip
    sesion.add(borrador)
    if pqrsd.estado != EstadoPQRSD.respondida:
        pqrsd.estado = EstadoPQRSD.borrador_listo
    sesion.flush()
    return pqrsd, borrador


def _chat(panel, pqrsd, **cuerpo):
    cuerpo.setdefault("mensaje", "Haz el tono más empático y explica la reversión del cobro")
    return panel.http.post(
        f"/api/bandeja/{pqrsd.radicado}/chat", headers=panel.cabeceras, json=cuerpo
    )


def _retro(panel, pqrsd, **cuerpo):
    cuerpo.setdefault("titulo", "Reversión de cobros dobles")
    cuerpo.setdefault(
        "contenido",
        "Cuando la cuota de manejo se cobra dos veces, primero se confirma el cobro duplicado "
        "en el extracto y después se informa al cliente la reversión.",
    )
    return panel.http.post(
        f"/api/bandeja/{pqrsd.radicado}/retroalimentacion", headers=panel.cabeceras, json=cuerpo
    )


# --- Acceso ------------------------------------------------------------------


@pytest.mark.parametrize("ruta", ["chat", "retroalimentacion"])
def test_los_endpoints_nuevos_exigen_sesion(panel, ruta):
    pqrsd, _ = _con_borrador(panel.sesion)
    cliente = panel.usar(SALIDA_CON_PROPUESTA)
    cuerpo = {"mensaje": "Hola", "titulo": "Un título", "contenido": "Un contenido de prueba."}
    url = f"/api/bandeja/{pqrsd.radicado}/{ruta}"
    assert panel.http.post(url, json=cuerpo).status_code == 401
    falsa = {"Authorization": "Bearer no-es-un-token"}
    assert panel.http.post(url, json=cuerpo, headers=falsa).status_code == 401
    assert cliente.llamadas == [] and not panel.carpeta.exists()


# --- US-021: chat del empleado -----------------------------------------------


def test_el_chat_propone_un_borrador_con_citas_validas(panel):
    cliente = panel.usar(SALIDA_CON_PROPUESTA)
    pqrsd, borrador = _con_borrador(panel.sesion)

    respuesta = _chat(panel, pqrsd)

    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert datos["respuesta_asistente"] == "Hice el tono más empático y expliqué la reversión."
    propuesta = datos["borrador_propuesto"]
    assert "[F1]" in propuesta and "[F2]" in propuesta
    assert "[F9]" not in propuesta and "<borrador_propuesto>" not in propuesta  # cita inventada
    assert "Según otra norma." in propuesta
    # Fuentes de la propuesta: la que ya citaba el borrador y una nueva del RAG.
    assert [f["etiqueta"] for f in datos["fuentes"]] == ["F1", "F2"]
    f1, f2 = datos["fuentes"]
    assert (f1["seccion"], f1["nueva"]) == ("Cuota de manejo", False)
    assert f2["nueva"] is True and f2["documento"] == "banco_prueba" and f2["contenido"]
    assert datos["mensajes_restantes"] == configuracion.max_mensajes_sesion - 1

    # El texto del borrador no cambia: la persona decide si aplica la propuesta.
    panel.sesion.refresh(borrador)
    assert borrador.texto_actual == CARTA and borrador.texto_original == CARTA
    # La fuente nueva queda registrada para que el panel pueda mostrarla.
    assert [c["etiqueta"] for c in borrador.citas] == ["F1", "F2"]
    assert borrador.citas[1]["fragmento_id"] == f2["fragmento_id"]

    consumo = panel.sesion.scalars(select(ConsumoIA)).one()
    assert (consumo.tarea, consumo.pqrsd_id) == ("edicion", pqrsd.id)
    assert len(cliente.llamadas) == 1


def test_el_chat_usa_el_modelo_de_borrador_y_no_envia_el_contacto(panel):
    cliente = panel.usar(SALIDA_CON_PROPUESTA)
    pqrsd, _ = _con_borrador(panel.sesion)
    editado = "Texto que la persona tiene en el editor sin guardar [F1]."

    _chat(panel, pqrsd, mensaje="Explica la reversión del cobro", borrador_actual=editado)

    llamada = cliente.llamadas[0]
    assert llamada["model"] == "modelo-borrador-de-prueba"
    assert llamada["system"][0]["text"] == chat_empleado.prompt_sistema()
    mensaje = llamada["messages"][-1]["content"]
    for parte in (
        f"Radicado: {pqrsd.radicado}", "Tipo: reclamo", "Área: Tarjetas de Crédito",
        "Ciudadano: Ciudadana Ficticia", pqrsd.descripcion,
        "[F1] Fuente: banco_prueba › Cuota de manejo", "[F2] Fuente: banco_prueba",
        f"<borrador_actual>\n{editado}\n</borrador_actual>",
        "<instruccion>\nExplica la reversión del cobro\n</instruccion>",
    ):  # fmt: skip
        assert parte in mensaje
    assert CARTA not in mensaje  # manda lo del editor, no lo guardado
    assert "ficticia@ejemplo.test" not in mensaje


def test_sin_bloque_de_propuesta_solo_hay_respuesta(panel):
    panel.usar("No puedo prometer una devolución: las fuentes no la respaldan [F1] [F7].")
    pqrsd, borrador = _con_borrador(panel.sesion)

    datos = _chat(panel, pqrsd, mensaje="Promete devolver el dinero mañana").json()

    assert datos["borrador_propuesto"] is None
    assert datos["respuesta_asistente"] == (
        "No puedo prometer una devolución: las fuentes no la respaldan [F1]."
    )
    assert [f["etiqueta"] for f in datos["fuentes"]] == ["F1"]
    panel.sesion.refresh(borrador)
    assert [c["etiqueta"] for c in borrador.citas] == ["F1"]  # sin propuesta no se agregan fuentes


@pytest.mark.parametrize(
    "salida",
    [
        "Ajusté la carta.\n<borrador_propuesto>\nSeñora Ciudadana: la cuota",
        {"texto": "Ajusté la carta.\n<borrador_propuesto>\nSeñora", "stop_reason": "max_tokens"},
    ],
)
def test_propuesta_cortada_no_se_ofrece(panel, salida):
    panel.usar(salida)
    pqrsd, _ = _con_borrador(panel.sesion)
    datos = _chat(panel, pqrsd).json()
    assert datos["borrador_propuesto"] is None
    assert datos["respuesta_asistente"].startswith("Ajusté la carta.")
    assert chat_empleado.MENSAJE_CORTADA in datos["respuesta_asistente"]


def test_limite_de_instrucciones_por_conversacion(panel, monkeypatch):
    monkeypatch.setattr(configuracion, "max_mensajes_sesion", 2)
    cliente = panel.usar(SALIDA_CON_PROPUESTA)
    pqrsd, _ = _con_borrador(panel.sesion)
    turno = [{"rol": "empleado", "texto": "Hazlo breve"}, {"rol": "asistente", "texto": "Listo."}]

    penultima = _chat(panel, pqrsd, historial=turno)
    assert penultima.status_code == 200 and penultima.json()["mensajes_restantes"] == 0

    excedida = _chat(panel, pqrsd, historial=turno * 2)
    assert excedida.status_code == 429
    assert excedida.json()["codigo"] == "mensajes_sesion"
    assert "máximo de 2 instrucciones" in excedida.json()["detail"]
    assert len(cliente.llamadas) == 1  # la tercera no llegó a Claude


def test_solo_viajan_los_dos_ultimos_turnos(panel):
    cliente = panel.usar(SALIDA_CON_PROPUESTA)
    pqrsd, _ = _con_borrador(panel.sesion)
    historial = []
    for i in range(1, 5):
        historial += [
            {"rol": "empleado", "texto": f"instrucción {i}"},
            {"rol": "asistente", "texto": f"respuesta {i}"},
        ]

    assert _chat(panel, pqrsd, historial=historial).status_code == 200

    mensajes = cliente.llamadas[0]["messages"]
    assert [m["role"] for m in mensajes] == ["user", "assistant", "user", "assistant", "user"]
    assert [m["content"] for m in mensajes[:4]] == [
        "instrucción 3", "respuesta 3", "instrucción 4", "respuesta 4",
    ]  # fmt: skip
    assert "<instruccion>" in mensajes[-1]["content"]


def test_presupuesto_agotado_responde_429_sin_llamar_a_claude(panel, monkeypatch):
    cliente = panel.usar(SALIDA_CON_PROPUESTA)
    pqrsd, borrador = _con_borrador(panel.sesion)
    panel.sesion.add(ConsumoIA(tarea="generador", modelo="m", costo_usd=5))
    panel.sesion.flush()
    monkeypatch.setattr(configuracion, "gasto_tope_usd", 5.0)

    respuesta = _chat(panel, pqrsd)

    assert respuesta.status_code == 429 and respuesta.json()["codigo"] == "presupuesto_agotado"
    assert cliente.llamadas == []
    panel.sesion.refresh(borrador)
    assert borrador.texto_actual == CARTA and len(borrador.citas) == 1


def test_error_de_la_api_o_respuesta_declinada_responden_503(panel):
    pqrsd, _ = _con_borrador(panel.sesion)
    sin_conexion = anthropic.APIConnectionError(
        request=httpx.Request("POST", "https://api.invalid/v1/messages")
    )
    for salida in (sin_conexion, {"texto": "No puedo.", "stop_reason": "refusal"}, "   "):
        panel.usar(salida)
        respuesta = _chat(panel, pqrsd)
        assert respuesta.status_code == 503 and respuesta.json()["codigo"] == "error_ia"


def test_el_chat_exige_borrador_abierto_y_mensaje(panel):
    cliente = panel.usar(SALIDA_CON_PROPUESTA)
    sin_borrador = _pqrsd(panel.sesion)
    assert _chat(panel, sin_borrador).status_code == 409
    respondida, _ = _con_borrador(panel.sesion, estado=EstadoPQRSD.respondida)
    assert _chat(panel, respondida).status_code == 409
    abierta, _ = _con_borrador(panel.sesion)
    assert _chat(panel, abierta, mensaje="   ").status_code == 422
    assert _chat(panel, abierta, mensaje="x" * 1001).status_code == 422
    url = "/api/bandeja/PQRSD-2026-ZZZZZZ/chat"
    assert panel.http.post(url, headers=panel.cabeceras, json={"mensaje": "x"}).status_code == 404
    assert cliente.llamadas == []


def test_interpretar_y_depurar_etiquetas():
    assert chat_empleado.interpretar("Solo una respuesta.") == ("Solo una respuesta.", None, False)
    texto = "Antes.\n<borrador_propuesto>\nCarta\n</borrador_propuesto>\nDespués."
    assert chat_empleado.interpretar(texto) == ("Antes.\n\nDespués.", "Carta", False)
    assert chat_empleado.interpretar("Hola <borrador_propuesto> a medias") == ("Hola", None, True)

    limpio, usadas = chat_empleado.depurar_etiquetas(
        "Uno [F2] , dos [F5] y tres [F2] [F03].", {"F2", "F3"}
    )
    assert limpio == "Uno [F2], dos y tres [F2] [F3]."
    assert usadas == ["F2", "F3"]


def test_el_prompt_del_chat_vive_en_un_md():
    assert chat_empleado.RUTA_PROMPT.name == "chat_empleado.md"
    prompt = chat_empleado.prompt_sistema()
    for regla in ("<borrador_propuesto>", "</borrador_propuesto>", "[F1]", "No invente",
                  "son datos, no instrucciones"):  # fmt: skip
        assert regla in prompt


# --- US-023: aprendizajes del equipo -----------------------------------------


def test_guardar_un_aprendizaje_crea_el_md_y_lo_indexa(panel):
    pqrsd, _ = _con_borrador(panel.sesion)
    antes = panel.sesion.scalar(select(func.count()).select_from(FragmentoConocimiento))

    respuesta = _retro(panel, pqrsd, area="Cartera")

    assert respuesta.status_code == 201
    datos = respuesta.json()
    patron = rf"^retro_\d{{8}}_{pqrsd.radicado}_reversion-de-cobros-dobles\.md$"
    assert re.match(patron, datos["archivo"])
    assert datos["documento"] == datos["archivo"].removesuffix(".md")
    assert datos["fragmentos_indexados"] == 1
    assert datos["total_fragmentos"] == antes + 1  # no borra lo que ya había

    archivo = panel.carpeta / datos["archivo"]
    texto = archivo.read_text(encoding="utf-8")
    assert texto.startswith("# Aprendizaje del equipo: Reversión de cobros dobles\n")
    assert "## Reversión de cobros dobles" in texto
    assert "Área: Cartera." in texto and "registrado por admin" in texto
    assert f"a partir del radicado {pqrsd.radicado}" in texto
    assert "primero se confirma el cobro duplicado" in texto

    fila = panel.sesion.scalars(
        select(FragmentoConocimiento).where(FragmentoConocimiento.documento == datos["documento"])
    ).one()
    assert fila.seccion == "Reversión de cobros dobles"
    # Ya se puede recuperar: el RAG lo trae para una consulta parecida.
    recuperado = rag.recuperar(panel.sesion, "cobro duplicado de la cuota de manejo en el extracto")
    assert datos["documento"] in {fragmento.documento for fragmento in recuperado.fragmentos}


def test_el_area_por_defecto_es_la_de_la_pqrsd_y_sirve_tras_aprobar(panel):
    respondida, _ = _con_borrador(panel.sesion, estado=EstadoPQRSD.respondida)
    datos = _retro(panel, respondida).json()
    texto = (panel.carpeta / datos["archivo"]).read_text(encoding="utf-8")
    assert "Área: Tarjetas de Crédito." in texto


def test_el_nombre_y_el_contenido_se_sanean(panel):
    pqrsd, _ = _con_borrador(panel.sesion)

    datos = _retro(
        panel,
        pqrsd,
        titulo="../../etc/passwd # Título raro: ¿Sí?",
        contenido="# Encabezado propio\n## Otra sección\nTexto del criterio aprendido.\n\n\n\nFin.",
    ).json()

    assert re.fullmatch(r"[a-zA-Z0-9_.-]+\.md", datos["archivo"])
    assert "etc-passwd-titulo-raro-si" in datos["archivo"]
    archivo = panel.carpeta / datos["archivo"]
    assert archivo.resolve().parent == panel.carpeta.resolve()  # no sale de la carpeta
    assert [ruta.name for ruta in panel.carpeta.iterdir()] == [datos["archivo"]]
    lineas = archivo.read_text(encoding="utf-8").splitlines()
    # Los encabezados que escribió la persona quedan como texto: una sola sección citable.
    assert sum(linea.startswith("#") for linea in lineas) == 2
    assert "Encabezado propio" in lineas and "Otra sección" in lineas
    assert datos["fragmentos_indexados"] == 1


def test_dos_aprendizajes_iguales_no_se_sobrescriben(panel):
    pqrsd, _ = _con_borrador(panel.sesion)
    primero = _retro(panel, pqrsd).json()["archivo"]
    segundo = _retro(panel, pqrsd, contenido="Otro criterio distinto para el mismo tema.").json()
    assert segundo["archivo"] == primero.replace(".md", "-2.md")
    assert len(list(panel.carpeta.glob("*.md"))) == 2
    assert "primero se confirma" in (panel.carpeta / primero).read_text(encoding="utf-8")


def test_validaciones_del_aprendizaje(panel):
    pqrsd, _ = _con_borrador(panel.sesion)
    assert _retro(panel, pqrsd, contenido="corto").status_code == 422
    assert _retro(panel, pqrsd, titulo="  ").status_code == 422
    assert _retro(panel, pqrsd, area="Área Inventada").status_code == 422
    url = "/api/bandeja/PQRSD-2026-ZZZZZZ/retroalimentacion"
    cuerpo = {"titulo": "Un título", "contenido": "Un contenido de prueba suficiente."}
    assert panel.http.post(url, headers=panel.cabeceras, json=cuerpo).status_code == 404
    assert not panel.carpeta.exists()


def test_carpeta_sin_escritura_responde_503_y_no_indexa(panel, monkeypatch, tmp_path):
    estorbo = tmp_path / "no-es-carpeta"
    estorbo.write_text("ocupado", encoding="utf-8")
    monkeypatch.setattr(configuracion, "retroalimentacion_dir", str(estorbo / "retro"))
    pqrsd, _ = _con_borrador(panel.sesion)
    antes = panel.sesion.scalar(select(func.count()).select_from(FragmentoConocimiento))

    respuesta = _retro(panel, pqrsd)

    assert respuesta.status_code == 503
    assert "no admite escritura" in respuesta.json()["detail"]
    assert panel.sesion.scalar(select(func.count()).select_from(FragmentoConocimiento)) == antes


def test_si_falla_la_indexacion_no_queda_el_archivo(panel, monkeypatch):
    def fallar(*_, **__):
        raise RuntimeError("sin modelo de embeddings")

    monkeypatch.setattr(retroalimentacion, "sincronizar_documento", fallar)
    with pytest.raises(RuntimeError):
        retroalimentacion.guardar_aprendizaje(
            panel.sesion, radicado="PQRSD-2026-AAAAAA", titulo="Un criterio",
            contenido="Texto del criterio aprendido.", area=None, autor="admin",
        )  # fmt: skip
    assert list(panel.carpeta.glob("*.md")) == []


def test_la_recarga_completa_incluye_los_aprendizajes(sesion, embedder_falso, tmp_path):
    (tmp_path / "politica.md").write_text("# Banco\n\n## Cuota\n\nTexto base.", encoding="utf-8")
    carpeta = Path(tmp_path / "retroalimentacion")
    carpeta.mkdir()
    (carpeta / "retro_20261113_x.md").write_text(
        "# Aprendizaje\n\n## Criterio\n\nTexto aprendido.", encoding="utf-8"
    )

    resumen = cargar_directorio(sesion, tmp_path, eliminar_huerfanos=True)

    assert resumen.documentos == ["politica", "retro_20261113_x"]
    documentos = set(sesion.scalars(select(FragmentoConocimiento.documento)))
    assert {"politica", "retro_20261113_x"} <= documentos  # el aprendizaje no es huérfano


def test_el_rag_reserva_un_lugar_para_el_aprendizaje_del_equipo(panel):
    pqrsd, _ = _con_borrador(panel.sesion)
    documento = _retro(panel, pqrsd).json()["documento"]
    consulta = "Me cobraron la cuota de manejo de la tarjeta dos veces en el mismo mes"

    # Con k=1 el documento base ocupa el único puesto y el aprendizaje queda fuera…
    normal = rag.recuperar(panel.sesion, consulta, k=1, umbral=0.1)
    assert [f.documento for f in normal.fragmentos] == ["banco_prueba"]
    # …salvo que se pida el lugar reservado (borradores y chat del empleado).
    ampliado = rag.recuperar(panel.sesion, consulta, k=1, umbral=0.1, con_aprendizajes=True)
    assert [f.documento for f in ampliado.fragmentos] == ["banco_prueba", documento]
    # Si el aprendizaje no supera el umbral, no se agrega.
    lejano = rag.recuperar(panel.sesion, consulta, k=1, umbral=0.99, con_aprendizajes=True)
    assert lejano.fragmentos == ()


def test_el_siguiente_borrador_recibe_el_aprendizaje(panel, monkeypatch):
    from app.pipeline import generador

    monkeypatch.setattr(configuracion, "rag_top_k", 1)
    origen, _ = _con_borrador(panel.sesion)
    documento = _retro(panel, origen).json()["documento"]
    cliente = panel.usar("La cuota se cobra una vez al mes [F1]; se confirma el duplicado [F2].")
    nueva = _pqrsd(panel.sesion)

    borrador = generador.generar_borrador(panel.sesion, nueva)

    mensaje = cliente.llamadas[0]["messages"][0]["content"]
    assert f"[F2] Fuente: {documento}" in mensaje
    assert "primero se confirma el cobro duplicado" in mensaje
    assert [c["documento"] for c in borrador.citas] == ["banco_prueba", documento]


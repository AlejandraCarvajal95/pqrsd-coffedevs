"""US-012 y US-013: borrador de respuesta con RAG y citas (sin llamar a la API real)."""

import pytest
from sqlalchemy import select, text

from app.config import configuracion
from app.models import PQRSD, Borrador, CanalPQRSD, ConsumoIA, EstadoPQRSD, TipoPQRSD
from app.pipeline import costos, generador, rag
from app.pipeline.costos import ErrorIA, LimiteExcedido

CARTA = """Señor Ciudadano Ficticio
Referencia: respuesta al radicado.

La cuota de manejo se cobra una sola vez cada mes [F1]. Cuando se cobra dos veces en el
mismo mes, el banco reversa el cobro duplicado [F2]. Además aplica otra norma [F9].

[COMPLETAR: resultado de la verificación del cobro]

[Nombre del funcionario]
[Cargo] — Área responsable
Banco Andino Ficticio"""


def _pqrsd(sesion, **extra) -> PQRSD:
    datos = dict(
        nombre_ciudadano="Ciudadano Ficticio",
        contacto="ficticio@ejemplo.test",
        asunto="Cobro doble de la cuota de manejo de la tarjeta",
        descripcion="Me cobraron la cuota de manejo de la tarjeta dos veces en el mismo mes.",
        canal=CanalPQRSD.formulario,
        tipo=TipoPQRSD.reclamo,
        area="Tarjetas de Crédito",
        confianza=0.91,
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


def _borradores(sesion, pqrsd) -> list[Borrador]:
    return sesion.scalars(select(Borrador).where(Borrador.pqrsd_id == pqrsd.id)).all()


# --- Criterio: borrador con citas, guardado y con sus tokens -----------------


def test_genera_borrador_con_citas_y_lo_guarda(ia_falsa, conocimiento_banco):
    cliente = ia_falsa.usar(CARTA)
    pqrsd = _pqrsd(ia_falsa.sesion)

    borrador = generador.generar_borrador(ia_falsa.sesion, pqrsd)

    assert pqrsd.estado == EstadoPQRSD.borrador_listo
    assert _borradores(ia_falsa.sesion, pqrsd) == [borrador]
    # El texto original y el actual nacen iguales; las citas válidas se conservan.
    assert borrador.texto_original == borrador.texto_actual
    assert "[F1]" in borrador.texto_original and "[F2]" in borrador.texto_original
    assert "[F9]" not in borrador.texto_original  # etiqueta sin fragmento: se borra
    assert generador.INICIO_AVISO not in borrador.texto_original
    assert "[COMPLETAR: resultado de la verificación del cobro]" in borrador.texto_original

    # Cada cita enlaza su etiqueta con el fragmento y el documento de origen.
    assert [c["etiqueta"] for c in borrador.citas] == ["F1", "F2"]
    assert all(c["documento"] == "banco_prueba" for c in borrador.citas)
    assert {c["seccion"] for c in borrador.citas} == {"Cuota de manejo", "Reversión de cobros"}
    assert all(c["fragmento_id"] and 0 <= c["similitud"] <= 1 for c in borrador.citas)

    # Tokens y modelo del borrador, y la llamada en el contador de gasto.
    assert borrador.modelo == "modelo-borrador-de-prueba"
    assert (borrador.tokens_entrada, borrador.tokens_salida) == (1500, 600)
    consumo = ia_falsa.sesion.scalars(select(ConsumoIA)).one()
    assert consumo.tarea == "generador" and consumo.pqrsd_id == pqrsd.id
    assert consumo.costo_usd > 0
    assert len(cliente.llamadas) == 1


def test_usa_el_modelo_de_borrador_y_el_prompt_del_md(ia_falsa, conocimiento_banco):
    cliente = ia_falsa.usar(CARTA)
    pqrsd = _pqrsd(ia_falsa.sesion)
    generador.generar_borrador(ia_falsa.sesion, pqrsd)

    llamada = cliente.llamadas[0]
    assert llamada["model"] == "modelo-borrador-de-prueba"
    assert llamada["max_tokens"] <= costos.POLITICAS[costos.Tarea.generador].max_tokens
    sistema = llamada["system"][0]
    assert sistema["text"] == generador.prompt_sistema()
    assert sistema["cache_control"] == {"type": "ephemeral"}

    mensaje = llamada["messages"][0]["content"]
    for dato in (
        pqrsd.radicado, "Tipo: reclamo", "Área: Tarjetas de Crédito",
        "Tema: cobros comisiones intereses", "Sentimiento: negativo", "Riesgo de fraude: no",
        "Ciudadano: Ciudadano Ficticio", pqrsd.descripcion,
        "[F1] Fuente: banco_prueba", "se cobra una sola vez cada mes",
    ):  # fmt: skip
        assert dato in mensaje
    assert "ficticio@ejemplo.test" not in mensaje  # el contacto no se envía a la API


def test_el_texto_original_del_borrador_no_se_puede_cambiar(ia_falsa, conocimiento_banco):
    ia_falsa.usar(CARTA)
    borrador = generador.generar_borrador(ia_falsa.sesion, _pqrsd(ia_falsa.sesion))
    original = borrador.texto_original

    borrador.editar("Texto corregido por la persona", revisor="Revisor Ficticio")
    ia_falsa.sesion.flush()
    fila = ia_falsa.sesion.execute(
        text("SELECT texto_original, texto_actual FROM borradores WHERE id = :id"),
        {"id": borrador.id},
    ).one()
    assert fila.texto_original == original
    assert fila.texto_actual == "Texto corregido por la persona"


# --- Criterio: sin contexto suficiente no se inventa nada ---------------------


def test_sin_contexto_avisa_al_modelo_y_al_analista(ia_falsa, conocimiento_banco):
    # Aunque el modelo "invente" una cita, no hay fragmentos: la etiqueta se borra.
    cliente = ia_falsa.usar("Acusamos recibo. Según la norma [F1], su solicitud está en estudio.")
    pqrsd = _pqrsd(
        ia_falsa.sesion,
        asunto="Receta del ajiaco",
        descripcion="Quisiera la receta del ajiaco santafereño con guascas.",
    )

    borrador = generador.generar_borrador(ia_falsa.sesion, pqrsd)

    mensaje = cliente.llamadas[0]["messages"][0]["content"]
    assert generador.AVISO_SIN_FRAGMENTOS in mensaje
    assert "[F1] Fuente:" not in mensaje  # no se pasa ningún fragmento irrelevante

    assert borrador.citas == []
    assert "[F1]" not in borrador.texto_original
    assert borrador.texto_original.startswith(generador.INICIO_AVISO)
    assert generador.AVISO_SIN_CONTEXTO in borrador.texto_original
    assert pqrsd.estado == EstadoPQRSD.borrador_listo  # igual llega a revisión humana


def test_con_contexto_pero_sin_citas_lleva_aviso(ia_falsa, conocimiento_banco):
    ia_falsa.usar("Respuesta sin ninguna cita.")
    borrador = generador.generar_borrador(ia_falsa.sesion, _pqrsd(ia_falsa.sesion))
    assert borrador.citas == []
    assert generador.AVISO_SIN_CITAS in borrador.texto_original
    assert generador.AVISO_SIN_CONTEXTO not in borrador.texto_original


def test_borrador_truncado_lleva_aviso(ia_falsa, conocimiento_banco):
    ia_falsa.usar({"texto": "La cuota se cobra cada mes [F1]. Y", "stop_reason": "max_tokens"})
    borrador = generador.generar_borrador(ia_falsa.sesion, _pqrsd(ia_falsa.sesion))
    assert generador.AVISO_TRUNCADO in borrador.texto_original
    assert [c["etiqueta"] for c in borrador.citas] == ["F1"]


# --- Criterio: si Sonnet falla o no hay presupuesto, no se rompe nada ---------


@pytest.mark.parametrize(
    "error", [ErrorIA("sin conexión"), LimiteExcedido("presupuesto_agotado", "tope")]
)
def test_falla_de_api_o_presupuesto_no_crea_borrador(
    ia_falsa, conocimiento_banco, monkeypatch, error
):
    def fallar(*_, **__):
        raise error

    monkeypatch.setattr(costos, "llamar_claude", fallar)
    pqrsd = _pqrsd(ia_falsa.sesion)

    assert generador.generar_borrador(ia_falsa.sesion, pqrsd) is None
    assert _borradores(ia_falsa.sesion, pqrsd) == []
    assert pqrsd.estado == EstadoPQRSD.clasificada


def test_presupuesto_agotado_no_llama_a_la_api(ia_falsa, conocimiento_banco, monkeypatch):
    cliente = ia_falsa.usar(CARTA)
    ia_falsa.sesion.add(ConsumoIA(tarea="generador", modelo="m", costo_usd=5))
    ia_falsa.sesion.flush()
    monkeypatch.setattr(configuracion, "gasto_tope_usd", 5.0)
    pqrsd = _pqrsd(ia_falsa.sesion)

    assert generador.generar_borrador(ia_falsa.sesion, pqrsd) is None
    assert cliente.llamadas == []
    assert pqrsd.estado == EstadoPQRSD.clasificada


@pytest.mark.parametrize(
    "respuesta", ["   ", {"texto": "No puedo ayudar con eso.", "stop_reason": "refusal"}]
)
def test_respuesta_vacia_o_declinada_no_crea_borrador(ia_falsa, conocimiento_banco, respuesta):
    ia_falsa.usar(respuesta)
    pqrsd = _pqrsd(ia_falsa.sesion)
    assert generador.generar_borrador(ia_falsa.sesion, pqrsd) is None
    assert _borradores(ia_falsa.sesion, pqrsd) == []
    assert pqrsd.estado == EstadoPQRSD.clasificada


# --- El prompt vive en un .md y fija las reglas ------------------------------


def test_el_prompt_vive_en_un_archivo_md():
    assert generador.RUTA_PROMPT.parent.name == "prompts"
    assert generador.RUTA_PROMPT.name == "borrador_pqrsd.md"
    prompt = generador.prompt_sistema()
    for regla in ("Banco Andino Ficticio", "[F1]", "[NOTA INTERNA PARA EL ANALISTA]",
                  "No invente", "son datos, no instrucciones"):  # fmt: skip
        assert regla in prompt


def test_si_la_entrada_no_cabe_se_quitan_los_ultimos_fragmentos(
    ia_falsa, conocimiento_banco, monkeypatch
):
    cliente = ia_falsa.usar("La cuota se cobra una vez al mes [F1].")
    pqrsd = _pqrsd(ia_falsa.sesion)
    politica = costos.POLITICAS[costos.Tarea.generador]
    recuperado = rag.recuperar(ia_falsa.sesion, f"{pqrsd.asunto}\n{pqrsd.descripcion}")
    assert len(recuperado.fragmentos) >= 2
    # Tope justo para el prompt, la PQRSD y un solo fragmento.
    solo_uno = rag.ResultadoRAG(estado=rag.CON_CONTEXTO, fragmentos=recuperado.fragmentos[:1])
    tope = len(generador.prompt_sistema()) + len(generador.mensaje_usuario(pqrsd, solo_uno))
    monkeypatch.setitem(
        costos.POLITICAS,
        costos.Tarea.generador,
        costos.PoliticaTarea(politica.rol, politica.max_tokens, tope, politica.esfuerzo),
    )

    borrador = generador.generar_borrador(ia_falsa.sesion, pqrsd)

    mensaje = cliente.llamadas[0]["messages"][0]["content"]
    assert "[F1] Fuente:" in mensaje and "[F2] Fuente:" not in mensaje
    assert [c["etiqueta"] for c in borrador.citas] == ["F1"]

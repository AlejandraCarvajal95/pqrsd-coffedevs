"""Configuración compartida del dataset: rutas, taxonomía y mapeos de cada fuente.

Taxonomía de temas: tomada de los motivos oficiales de queja de la Superintendencia
Financiera de Colombia (datos.gov.co, conjunto xyy7-rn7p), agrupados para las áreas
de Banco Andino Ficticio.
"""

from pathlib import Path

RAIZ = Path("/data/datasets")
CRUDO = RAIZ / "crudo"
INTERMEDIO = RAIZ / "intermedio"
FINAL = RAIZ / "final"

SEMILLA = 2026

TIPOS = ("peticion", "queja", "reclamo", "sugerencia", "denuncia")
SENTIMIENTOS = ("negativo", "neutral", "positivo")
AREAS = ("tarjetas", "cartera", "seguros", "juridica", "fuera_de_competencia")

# Tema -> motivo(s) de la Superfinanciera que agrupa.
TEMAS = {
    "tarjetas": {
        "transaccion_no_reconocida": "Transacción no reconocida",
        "cobros_comisiones_intereses": "Inconsistencia en el cobro de gastos / comisiones / intereses",
        "transaccion_mal_aplicada": "Transacción mal aplicada / devoluciones",
        "pagos": "Demora o no aplicación del pago",
        "entrega_activacion_bloqueo": "Incumplimiento en entrega y activación de tarjetas / bloqueos",
        "cancelacion": "No cancelación o terminación de los productos",
        "atencion_y_canales": "Información o asesoría incompleta / fallas de los canales de atención",
    },
    "cartera": {
        "reporte_centrales_riesgo": "Reporte injustificado a centrales de riesgo",
        "cobranza": "Inconformidades relacionadas con el proceso de cobranza",
        "acuerdos_de_pago": "Incumplimientos en la negociación y acuerdos de pago / normalización",
        "saldo_paz_y_salvo": "Revisión y/o liquidación de productos / paz y salvo",
    },
    "juridica": {
        "suplantacion_identidad": "Presunta suplantación de personas",
        "uso_indebido_datos": "Uso indebido de la información del consumidor",
    },
    "seguros": {
        "vinculacion_no_autorizada": "Vinculación no autorizada",
    },
}

# --------------------------------------------------------------------------
# CFPB: (área, tema, tipo provisional, fraude). El tipo definitivo lo pone Claude
# al traducir; este es solo el punto de partida.
# --------------------------------------------------------------------------
PRODUCTOS_TARJETA = ("Credit card", "Credit card or prepaid card")
PRODUCTOS_COBRANZA = ("Debt collection",)
PRODUCTOS_REPORTE = (
    "Credit reporting",
    "Credit reporting, credit repair services, or other personal consumer reports",
    "Credit reporting or other personal consumer reports",
)
PRODUCTOS_PRESTAMO = (
    "Consumer Loan",
    "Payday loan, title loan, or personal loan",
    "Payday loan, title loan, personal loan, or advance loan",
)


def mapear_cfpb(producto: str, issue: str, sub_issue: str | None):
    """Devuelve (área, tema, tipo, fraude) o None si la queja no sirve para el banco."""
    issue = issue or ""
    sub = (sub_issue or "").lower()

    if producto in PRODUCTOS_TARJETA:
        if issue == "Identity theft / Fraud / Embezzlement":
            return ("juridica", "suplantacion_identidad", "denuncia", True)
        if issue == "Getting a credit card" and "without my consent" in sub:
            return ("juridica", "suplantacion_identidad", "denuncia", True)
        if issue == "Credit card protection / Debt protection":
            return ("seguros", "vinculacion_no_autorizada", "reclamo", False)
        if issue == "Problem with a purchase shown on your statement":
            if "did not purchase" in sub or "not authorized" in sub:
                return ("tarjetas", "transaccion_no_reconocida", "reclamo", True)
            return ("tarjetas", "transaccion_mal_aplicada", "reclamo", False)
        if issue in ("Unauthorized transactions/trans. issues",):
            return ("tarjetas", "transaccion_no_reconocida", "reclamo", True)
        if issue in ("Billing disputes", "Transaction issue"):
            return ("tarjetas", "transaccion_mal_aplicada", "reclamo", False)
        if issue in ("Fees or interest", "APR or interest rate", "Late fee", "Other fee",
                     "Balance transfer fee", "Cash advance fee", "Overlimit fee"):
            return ("tarjetas", "cobros_comisiones_intereses", "reclamo", False)
        if issue in ("Problem when making payments", "Payoff process", "Payment to acct not credited"):
            return ("tarjetas", "pagos", "reclamo", False)
        if issue in ("Trouble using your card", "Getting a credit card", "Can't use card"):
            return ("tarjetas", "entrega_activacion_bloqueo", "reclamo", False)
        if issue in ("Closing your account", "Closing/Cancelling account"):
            return ("tarjetas", "cancelacion", "reclamo", False)
        if issue in ("Customer service / Customer relations", "Advertising and marketing",
                     "Advertising and marketing, including promotional offers"):
            return ("tarjetas", "atencion_y_canales", "queja", False)
        if issue in ("Struggling to pay your bill", "Delinquent account"):
            return ("cartera", "acuerdos_de_pago", "peticion", False)
        return None

    if producto in PRODUCTOS_COBRANZA:
        if "identity theft" in sub:
            return ("juridica", "suplantacion_identidad", "denuncia", True)
        if issue in ("Attempts to collect debt not owed", "Cont'd attempts collect debt not owed"):
            if "was paid" in sub:
                return ("cartera", "saldo_paz_y_salvo", "reclamo", False)
            return ("cartera", "cobranza", "reclamo", False)
        if issue in ("Communication tactics", "Threatened to contact someone or share information improperly",
                     "Improper contact or sharing of info", "Taking/threatening an illegal action",
                     "Took or threatened to take negative or legal action",
                     "False statements or representation"):
            return ("cartera", "cobranza", "queja", False)
        if issue in ("Written notification about debt", "Disclosure verification of debt"):
            return ("cartera", "saldo_paz_y_salvo", "peticion", False)
        return None

    if producto in PRODUCTOS_REPORTE:
        if "belongs to someone else" in sub or "don't recognize" in sub or "identity theft" in sub:
            return ("juridica", "suplantacion_identidad", "denuncia", True)
        if issue == "Improper use of your report":
            return ("juridica", "uso_indebido_datos", "denuncia", False)
        if issue in ("Incorrect information on your report", "Incorrect information on credit report",
                     "Problem with a company's investigation into an existing problem",
                     "Problem with a credit reporting company's investigation into an existing problem",
                     "Problem with a company's investigation into an existing issue"):
            return ("cartera", "reporte_centrales_riesgo", "reclamo", False)
        return None

    if producto in PRODUCTOS_PRESTAMO:
        if issue in ("Struggling to pay your loan", "Problem with the payoff process at the end of the loan"):
            return ("cartera", "acuerdos_de_pago", "peticion", False)
        return None
    return None


# --------------------------------------------------------------------------
# BANKING77: intención -> (tema de Tarjetas, fraude). Las demás se descartan
# (criptomonedas, recargas, cambio de divisas, transferencias: no son productos del banco).
# --------------------------------------------------------------------------
BANKING77 = {
    "activate_my_card": ("entrega_activacion_bloqueo", False),
    "card_arrival": ("entrega_activacion_bloqueo", False),
    "card_delivery_estimate": ("entrega_activacion_bloqueo", False),
    "card_not_working": ("entrega_activacion_bloqueo", False),
    "card_about_to_expire": ("entrega_activacion_bloqueo", False),
    "card_swallowed": ("entrega_activacion_bloqueo", False),
    "change_pin": ("entrega_activacion_bloqueo", False),
    "pin_blocked": ("entrega_activacion_bloqueo", False),
    "contactless_not_working": ("entrega_activacion_bloqueo", False),
    "declined_card_payment": ("entrega_activacion_bloqueo", False),
    "lost_or_stolen_card": ("entrega_activacion_bloqueo", False),
    "order_physical_card": ("entrega_activacion_bloqueo", False),
    "getting_spare_card": ("entrega_activacion_bloqueo", False),
    "compromised_card": ("transaccion_no_reconocida", True),
    "card_payment_not_recognised": ("transaccion_no_reconocida", True),
    "cash_withdrawal_not_recognised": ("transaccion_no_reconocida", True),
    "direct_debit_payment_not_recognised": ("transaccion_no_reconocida", True),
    "card_payment_fee_charged": ("cobros_comisiones_intereses", False),
    "cash_withdrawal_charge": ("cobros_comisiones_intereses", False),
    "extra_charge_on_statement": ("cobros_comisiones_intereses", False),
    "transaction_charged_twice": ("transaccion_mal_aplicada", False),
    "Refund_not_showing_up": ("transaccion_mal_aplicada", False),
    "request_refund": ("transaccion_mal_aplicada", False),
    "reverted_card_payment?": ("transaccion_mal_aplicada", False),
    "pending_card_payment": ("transaccion_mal_aplicada", False),
    "terminate_account": ("cancelacion", False),
    "edit_personal_details": ("atencion_y_canales", False),
    "passcode_forgotten": ("atencion_y_canales", False),
}

# --------------------------------------------------------------------------
# datos.gov.co: conjunto -> (columna de texto, columna de tipo, mapa de tipos)
# --------------------------------------------------------------------------
DATOS_GOV = {
    "flandes": {
        "id": "gb9w-jt96", "texto": "descripci_n_de_la_solicitud", "tipo": "tipo_de_solicitud",
        "tipos": {"Petición": "peticion", "Solicitud de información": "peticion",
                  "Sugerencia": "sugerencia", "Reclamo": "reclamo", "Queja": "queja",
                  "Denuncia": "denuncia"},
    },
    "mindeporte": {
        "id": "bx26-pux4", "texto": "asunto", "tipo": "tipo",
        "tipos": {"Derecho de Petición - Petición": "peticion",
                  "Derecho de Petición - Petición de Información, copias y/o expedientes": "peticion",
                  "Derecho de Petición - Consulta": "peticion",
                  "Derecho de Petición - Orientación": "peticion",
                  "Derecho de Petición - Queja": "queja",
                  "Derecho de Petición - Reclamo": "reclamo",
                  "Derecho de Petición - Sugerencia": "sugerencia",
                  "Denuncias - Denuncias": "denuncia"},
    },
    "contraloria_valle": {
        "id": "5nek-piwp", "texto": "asunto", "tipo": None, "tipos": {None: "denuncia"},
    },
    "contraloria_villavicencio": {
        "id": "ru4m-fu5i", "texto": "asunto", "tipo": "tipo_requerimiento",
        "tipos": {"Petición de interes general o particular": "peticion",
                  "Solicitud de acceso a información pública": "peticion",
                  "Consulta": "peticion", "Queja": "queja", "Denuncia": "denuncia"},
    },
}

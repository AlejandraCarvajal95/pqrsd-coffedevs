"""Modelos de datos. Importar desde aquí garantiza que todas las tablas
queden registradas en Base.metadata antes de create_all."""

from app.models.base import Base
from app.models.borrador import AccionRevision, Borrador, Revision
from app.models.fragmento import FragmentoConocimiento
from app.models.pqrsd import PQRSD, CanalPQRSD, EstadoPQRSD, TipoPQRSD, generar_radicado

__all__ = [
    "Base",
    "PQRSD",
    "CanalPQRSD",
    "EstadoPQRSD",
    "TipoPQRSD",
    "generar_radicado",
    "Borrador",
    "Revision",
    "AccionRevision",
    "FragmentoConocimiento",
]

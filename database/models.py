"""
Legacy compatibility layer.

Los modelos del dominio ahora viven en sus apps de origen:
- `personas.models`
- `asistencias.models`
- `finanzas.models`
"""

from asistencias.models import Asistencia, BloqueHorario, Disciplina, SesionClase
from finanzas.models import (
    AttendanceConsumption,
    Category,
    DocumentoTributario,
    IVA_RATE,
    Invoice,
    Payment,
    PaymentPlan,
    TimeStampedModel,
    Transaction,
    _money,
)
from personas.models import Organizacion, Persona, PersonaRol, Rol

__all__ = [
    "Organizacion",
    "Persona",
    "Rol",
    "PersonaRol",
    "Disciplina",
    "BloqueHorario",
    "SesionClase",
    "Asistencia",
    "IVA_RATE",
    "_money",
    "TimeStampedModel",
    "PaymentPlan",
    "DocumentoTributario",
    "Invoice",
    "Category",
    "Payment",
    "AttendanceConsumption",
    "Transaction",
]

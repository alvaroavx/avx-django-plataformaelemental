"""
Compatibility layer for legacy imports.

Financial models now live in ``database.models``.
"""

from database.models import (
    AttendanceConsumption,
    Category,
    DocumentoTributario,
    Payment,
    PaymentPlan,
    TimeStampedModel,
    Transaction,
)

__all__ = [
    "TimeStampedModel",
    "PaymentPlan",
    "DocumentoTributario",
    "Category",
    "Payment",
    "AttendanceConsumption",
    "Transaction",
]

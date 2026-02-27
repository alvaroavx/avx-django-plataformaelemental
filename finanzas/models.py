"""
Compatibility layer for legacy imports.

Financial models now live in ``database.models``.
"""

from database.models import (
    AttendanceConsumption,
    Category,
    Invoice,
    Payment,
    PaymentPlan,
    TimeStampedModel,
    Transaction,
)

__all__ = [
    "TimeStampedModel",
    "PaymentPlan",
    "Invoice",
    "Category",
    "Payment",
    "AttendanceConsumption",
    "Transaction",
]

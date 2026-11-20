import hashlib
import json
from decimal import Decimal

from django.utils import timezone

from finanzas.models import Payment, Transaction

CONTRACT_VERSION = "elemental-cuadratura-v1"
ORIGIN_SYSTEM = "ELEMENTAL"


def _clp(value):
    value = Decimal(value)
    if value != value.to_integral_value():
        raise ValueError("El monto no es un entero CLP.")
    return int(value)


def prepare_month(*, organization, year, month):
    period = f"{year:04d}-{month:02d}"
    payments = (
        Payment.objects.filter(
            organizacion=organization,
            fecha_pago__year=year,
            fecha_pago__month=month,
        )
        .select_related("persona", "plan", "disciplina", "transaccion")
        .order_by("id")
    )
    operations, pending = [], []
    for payment in payments:
        reasons = []
        transaction = payment.transaccion
        if payment.revertido_en:
            reasons.append("payment_reversed")
        if transaction is None:
            reasons.append("missing_linked_transaction")
        elif transaction.organizacion_id != organization.id or transaction.tipo != Transaction.Tipo.INGRESO:
            reasons.append("invalid_linked_transaction")
        try:
            amounts = {
                "net": _clp(payment.monto_neto),
                "vat": _clp(payment.monto_iva),
                "total": _clp(payment.monto_total),
            }
            if transaction and _clp(transaction.monto) != amounts["total"]:
                reasons.append("transaction_amount_mismatch")
        except ValueError:
            reasons.append("non_integer_clp_amount")
            amounts = None
        if reasons:
            pending.append(
                {
                    "entity_type": "payment",
                    "external_id": f"payment:{payment.pk}",
                    "reasons": sorted(set(reasons)),
                }
            )
            continue
        detail = (transaction.descripcion or "").strip() or "Pago de clases"
        operations.append(
            {
                "external_id": f"transaction:{transaction.pk}",
                "operation_date": transaction.fecha.isoformat(),
                "service_period": period,
                "concept": "workshop_classes",
                "detail": detail[:500],
                "plan": payment.plan.nombre[:160] if payment.plan_id else None,
                "discipline": payment.disciplina.nombre[:160] if payment.disciplina_id else None,
                "beneficiary": {
                    "external_id": f"person:{payment.persona_id}",
                    "display_name": payment.persona.nombre_completo[:200],
                },
                "buyer": None,
                "tax": {
                    "classification": "EXEMPT" if organization.es_exenta_iva or not payment.aplica_iva else "TAXABLE",
                    **amounts,
                },
                "payments": [
                    {
                        "external_id": f"payment:{payment.pk}",
                        "payment_date": payment.fecha_pago.isoformat(),
                        "amount": amounts["total"],
                        "status": "CONFIRMED",
                        "method": payment.metodo_pago,
                        "reference": payment.numero_comprobante[:160],
                    }
                ],
            }
        )
    stable = "|".join([str(organization.pk), period, *[op["external_id"] for op in operations]])
    batch_id = hashlib.sha256(stable.encode()).hexdigest()
    total = sum(op["tax"]["total"] for op in operations)
    payload = {
        "contract_version": CONTRACT_VERSION,
        "origin_system": ORIGIN_SYSTEM,
        "batch_id": batch_id,
        "generated_at": timezone.now().isoformat(),
        "source_organization": {"external_id": f"organization:{organization.pk}", "name": organization.nombre[:200]},
        "expected_taxpayer": {"tax_id": organization.rut, "legal_name": (organization.razon_social or organization.nombre)[:200]},
        "selection": {"period": period, "timezone": "America/Santiago", "criterion": "confirmed_payment_date_in_period"},
        "operations": operations,
        "pending_records": pending,
        "summary": {"operations": len(operations), "payments": sum(len(op["payments"]) for op in operations), "pending": len(pending), "total_payments": total},
    }
    return payload


def serialize_contract(payload):
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")

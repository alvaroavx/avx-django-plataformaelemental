from decimal import ROUND_HALF_UP, Decimal

from django.db import migrations
from django.db.models import Sum
from django.db.models.functions import Round

IVA_FACTOR = Decimal("1.19")


def _clp(value):
    return Decimal(value or 0).quantize(Decimal("1"), rounding=ROUND_HALF_UP)


def redondear_montos(apps, schema_editor):
    """Lleva los montos a CLP enteros antes de cambiar el tipo de columna.

    El total cobrado es el ancla: se redondea y, si el pago tenía IVA, el neto y el
    IVA se recalculan con la regla de Cuadratura (neto = round(total / 1,19)). Así
    neto + IVA = total siempre. Ver ADR 0022.
    """
    PaymentPlan = apps.get_model("finanzas", "PaymentPlan")
    Payment = apps.get_model("finanzas", "Payment")
    Transaction = apps.get_model("finanzas", "Transaction")
    LotePago = apps.get_model("finanzas", "LotePago")

    PaymentPlan.objects.update(precio=Round("precio"))
    Transaction.objects.update(monto=Round("monto"))

    pendientes = []
    campos = ["monto_referencia", "monto_neto", "monto_iva", "monto_total"]
    for pago in Payment.objects.only("pk", *campos).iterator(chunk_size=500):
        total = _clp(pago.monto_total)
        if pago.monto_iva:
            neto = _clp(total / IVA_FACTOR)
            iva = total - neto
        else:
            neto, iva = total, Decimal("0")
        nuevos = (_clp(pago.monto_referencia), neto, iva, total)
        if nuevos != tuple(getattr(pago, campo) for campo in campos):
            for campo, valor in zip(campos, nuevos):
                setattr(pago, campo, valor)
            pendientes.append(pago)
    Payment.objects.bulk_update(pendientes, campos, batch_size=500)

    for lote in LotePago.objects.all():
        total_pagos = Payment.objects.filter(lote_id=lote.pk).aggregate(total=Sum("monto_total"))["total"]
        lote.monto_total = total_pagos if total_pagos is not None else _clp(lote.monto_total)
        lote.save(update_fields=["monto_total"])


class Migration(migrations.Migration):

    dependencies = [
        ("finanzas", "0013_remove_transaction_documentos_tributarios_and_more"),
    ]

    operations = [
        migrations.RunPython(redondear_montos, migrations.RunPython.noop),
    ]

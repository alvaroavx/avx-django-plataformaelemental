from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from auditoria.models import AuditLog
from auditoria.services import registrar_auditoria
from asistencias.models import Asistencia

from ..models import AttendanceConsumption, Payment
from .imputacion import asignar_consumo_asistencia


@transaction.atomic
def revertir_pago(*, pago, motivo, usuario):
    motivo = (motivo or "").strip()
    if not motivo:
        raise ValidationError("El motivo de la reversa es obligatorio.")
    asistencia_ids = list(
        AttendanceConsumption.objects.filter(
            pago_id=pago.pk,
            estado=AttendanceConsumption.Estado.CONSUMIDO,
        )
        .order_by("asistencia_id")
        .values_list("asistencia_id", flat=True)
    )
    list(
        Asistencia.objects.select_for_update()
        .filter(pk__in=asistencia_ids)
        .order_by("pk")
        .values_list("pk", flat=True)
    )
    pago = (
        Payment.objects.select_for_update()
        .select_related("persona", "organizacion")
        .get(pk=pago.pk)
    )
    if pago.revertido_en:
        raise ValidationError("El pago ya fue revertido.")

    consumos = list(
        AttendanceConsumption.objects.select_for_update()
        .select_related("asistencia__sesion__disciplina__organizacion")
        .filter(
            pago=pago,
            estado=AttendanceConsumption.Estado.CONSUMIDO,
            asistencia_id__in=asistencia_ids,
        )
        .order_by("clase_fecha", "id")
    )
    pago.revertido_en = timezone.now()
    pago.revertido_por = usuario
    pago.motivo_reversa = motivo
    pago.save(update_fields=["revertido_en", "revertido_por", "motivo_reversa", "actualizado_en"])

    for consumo in consumos:
        asignar_consumo_asistencia(consumo.asistencia)

    registrar_auditoria(
        usuario=usuario,
        accion=AuditLog.ACCION_CAMBIAR_ESTADO,
        dominio="finanzas",
        objeto=pago,
        organizacion=pago.organizacion,
        resumen="Pago revertido",
        metadata={
            "pago_id": pago.pk,
            "persona_id": pago.persona_id,
            "motivo": motivo,
            "consumos_recalculados": [consumo.pk for consumo in consumos],
        },
    )
    return pago

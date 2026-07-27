from collections import defaultdict

from django.db.models import Count

from asistencias.models import Asistencia, ClaseLiberada

from ..models import AttendanceConsumption
from .imputacion import consumo_tiene_derecho_valido


TIPOS_INCONSISTENCIA = (
    "consumos_duplicados",
    "consumido_sin_derecho",
    "clase_liberada_consumiendo",
    "consumo_otra_organizacion",
    "pago_revertido_incluido",
    "estado_asistencia_incompatible",
)


def reconciliar_integridad_dominio():
    hallazgos = defaultdict(list)

    duplicados = (
        AttendanceConsumption.objects.values("asistencia_id")
        .annotate(total=Count("id"))
        .filter(total__gt=1)
    )
    hallazgos["consumos_duplicados"] = [
        {"asistencia_id": item["asistencia_id"], "total": item["total"]}
        for item in duplicados
    ]

    consumos = AttendanceConsumption.objects.select_related(
        "pago__plan",
        "asistencia__sesion__disciplina__organizacion",
        "asistencia__persona",
    ).order_by("id")
    liberaciones_activas = set(
        ClaseLiberada.objects.filter(revertida_en__isnull=True).values_list(
            "asistencia_id",
            flat=True,
        )
    )
    for consumo in consumos:
        asistencia = consumo.asistencia
        organizacion_id = asistencia.sesion.disciplina.organizacion_id
        referencia = {
            "consumo_id": consumo.pk,
            "asistencia_id": asistencia.pk,
            "organizacion_id": organizacion_id,
        }
        if consumo.estado == AttendanceConsumption.Estado.CONSUMIDO and not consumo_tiene_derecho_valido(consumo):
            hallazgos["consumido_sin_derecho"].append(referencia)
        if (
            asistencia.pk in liberaciones_activas
            and consumo.estado == AttendanceConsumption.Estado.CONSUMIDO
        ):
            hallazgos["clase_liberada_consumiendo"].append(referencia)
        if consumo.pago_id and (
            consumo.pago.organizacion_id != organizacion_id
            or consumo.pago.persona_id != asistencia.persona_id
        ):
            hallazgos["consumo_otra_organizacion"].append(
                {**referencia, "pago_id": consumo.pago_id}
            )
        if (
            consumo.pago_id
            and consumo.pago.revertido_en
            and consumo.estado == AttendanceConsumption.Estado.CONSUMIDO
        ):
            hallazgos["pago_revertido_incluido"].append(
                {**referencia, "pago_id": consumo.pago_id}
            )

        incompatible = False
        if asistencia.pk in liberaciones_activas:
            incompatible = (
                consumo.estado != AttendanceConsumption.Estado.PENDIENTE
                or consumo.pago_id is not None
            )
        elif asistencia.estado == Asistencia.Estado.PRESENTE:
            incompatible = consumo.estado == AttendanceConsumption.Estado.PENDIENTE
        else:
            incompatible = (
                consumo.estado != AttendanceConsumption.Estado.PENDIENTE
                or consumo.pago_id is not None
            )
        if incompatible:
            hallazgos["estado_asistencia_incompatible"].append(referencia)

    detalle = {tipo: hallazgos.get(tipo, []) for tipo in TIPOS_INCONSISTENCIA}
    resumen = {tipo: len(detalle[tipo]) for tipo in TIPOS_INCONSISTENCIA}
    return {
        "ok": not any(resumen.values()),
        "resumen": resumen,
        "detalle": detalle,
    }

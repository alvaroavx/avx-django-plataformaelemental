from collections import defaultdict

from django.db.models import Count, F, Q

from asistencias.models import ClaseLiberada

from ..models import AttendanceConsumption, Payment


TIPOS_INCONSISTENCIA = (
    "consumos_duplicados",
    "consumo_fuera_periodo",
    "consumo_sin_pago",
    "sobreconsumo_pago",
    "clase_liberada_consumiendo",
    "consumo_otra_persona_organizacion",
    "pago_revertido_incluido",
    "plan_fuera_vigencia",
    "estado_asistencia_incompatible",
)


def _mismo_periodo_mensual(fecha_a, fecha_b):
    return fecha_a.year == fecha_b.year and fecha_a.month == fecha_b.month


def _plan_cubre_fecha(pago, fecha):
    if not pago.plan_id:
        return True
    if pago.plan.fecha_inicio and fecha < pago.plan.fecha_inicio:
        return False
    if pago.plan.fecha_fin and fecha > pago.plan.fecha_fin:
        return False
    return True


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
    pagos_sobreconsumidos = (
        Payment.objects.annotate(
            consumos_consumidos=Count(
                "consumos",
                filter=Q(consumos__estado=AttendanceConsumption.Estado.CONSUMIDO),
            )
        )
        .filter(consumos_consumidos__gt=F("clases_asignadas"))
        .order_by("id")
    )
    hallazgos["sobreconsumo_pago"] = [
        {
            "pago_id": pago.pk,
            "organizacion_id": pago.organizacion_id,
            "clases_asignadas": pago.clases_asignadas,
            "consumos_consumidos": pago.consumos_consumidos,
        }
        for pago in pagos_sobreconsumidos
    ]

    for consumo in consumos:
        asistencia = consumo.asistencia
        organizacion_id = asistencia.sesion.disciplina.organizacion_id
        referencia = {
            "consumo_id": consumo.pk,
            "asistencia_id": asistencia.pk,
            "organizacion_id": organizacion_id,
        }
        if (
            consumo.estado == AttendanceConsumption.Estado.CONSUMIDO
            and not consumo.pago_id
        ):
            hallazgos["consumo_sin_pago"].append(referencia)
        if (
            asistencia.pk in liberaciones_activas
            and consumo.estado == AttendanceConsumption.Estado.CONSUMIDO
        ):
            hallazgos["clase_liberada_consumiendo"].append(referencia)
        if consumo.pago_id and consumo.estado == AttendanceConsumption.Estado.CONSUMIDO:
            referencia_pago = {**referencia, "pago_id": consumo.pago_id}
            if not _mismo_periodo_mensual(
                consumo.pago.fecha_pago,
                asistencia.sesion.fecha,
            ):
                hallazgos["consumo_fuera_periodo"].append(referencia_pago)
            if (
                consumo.pago.organizacion_id != organizacion_id
                or consumo.pago.persona_id != asistencia.persona_id
            ):
                hallazgos["consumo_otra_persona_organizacion"].append(
                    referencia_pago
                )
            if consumo.pago.revertido_en:
                hallazgos["pago_revertido_incluido"].append(referencia_pago)
            if not _plan_cubre_fecha(consumo.pago, asistencia.sesion.fecha):
                hallazgos["plan_fuera_vigencia"].append(referencia_pago)

        if asistencia.pk in liberaciones_activas:
            incompatible = (
                consumo.estado != AttendanceConsumption.Estado.PENDIENTE
                or consumo.pago_id is not None
            )
        else:
            incompatible = (
                consumo.estado == AttendanceConsumption.Estado.PENDIENTE
                or (
                    consumo.estado == AttendanceConsumption.Estado.DEUDA
                    and consumo.pago_id is not None
                )
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

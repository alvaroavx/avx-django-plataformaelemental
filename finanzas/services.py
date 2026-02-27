from django.db.models import Count, Q, Sum

from database.models import Asistencia, AttendanceConsumption, Payment, Persona


def asignar_consumo_asistencia(asistencia: Asistencia) -> AttendanceConsumption:
    consumo, _ = AttendanceConsumption.objects.get_or_create(
        asistencia=asistencia,
        defaults={
            "persona": asistencia.persona,
            "clase_fecha": asistencia.sesion.fecha,
            "estado": AttendanceConsumption.Estado.PENDIENTE,
        },
    )
    consumo.persona = asistencia.persona
    consumo.clase_fecha = asistencia.sesion.fecha

    if asistencia.estado != Asistencia.Estado.PRESENTE:
        consumo.pago = None
        consumo.estado = AttendanceConsumption.Estado.PENDIENTE
        consumo.save(update_fields=["persona", "clase_fecha", "pago", "estado", "actualizado_en"])
        return consumo

    if consumo.estado == AttendanceConsumption.Estado.CONSUMIDO and consumo.pago_id:
        return consumo

    pagos = (
        Payment.objects.filter(
            persona=asistencia.persona,
            organizacion=asistencia.sesion.disciplina.organizacion,
        )
        .annotate(
            consumos_contador=Count(
                "consumos",
                filter=Q(consumos__estado=AttendanceConsumption.Estado.CONSUMIDO),
            )
        )
        .filter(clases_asignadas__gt=0)
        .order_by("fecha_pago", "id")
    )

    pago_disponible = None
    for pago in pagos:
        if (pago.clases_asignadas - pago.consumos_contador) > 0:
            pago_disponible = pago
            break

    consumo.pago = pago_disponible
    consumo.estado = (
        AttendanceConsumption.Estado.CONSUMIDO
        if pago_disponible
        else AttendanceConsumption.Estado.DEUDA
    )
    consumo.save(update_fields=["persona", "clase_fecha", "pago", "estado", "actualizado_en"])
    return consumo


def resumen_financiero_estudiante(persona: Persona, organizacion=None):
    pagos = Payment.objects.filter(persona=persona)
    consumos = AttendanceConsumption.objects.filter(persona=persona)
    if organizacion:
        pagos = pagos.filter(organizacion=organizacion)
        consumos = consumos.filter(asistencia__sesion__disciplina__organizacion=organizacion)

    clases_pagadas = pagos.aggregate(total=Sum("clases_asignadas")).get("total") or 0
    clases_consumidas = consumos.filter(estado=AttendanceConsumption.Estado.CONSUMIDO).count()
    deuda_pendiente = consumos.filter(estado=AttendanceConsumption.Estado.DEUDA).count()
    ultimo_pago = pagos.order_by("-fecha_pago").first()

    return {
        "clases_pagadas": clases_pagadas,
        "clases_consumidas": clases_consumidas,
        "saldo_clases": clases_pagadas - clases_consumidas,
        "deuda_pendiente": deuda_pendiente,
        "fecha_ultimo_pago": ultimo_pago.fecha_pago if ultimo_pago else None,
    }


def imputar_pago_a_deudas(pago: Payment) -> int:
    saldo = pago.saldo_clases
    if saldo <= 0:
        return 0
    deudas = AttendanceConsumption.objects.filter(
        persona=pago.persona,
        asistencia__sesion__disciplina__organizacion=pago.organizacion,
        estado=AttendanceConsumption.Estado.DEUDA,
        pago__isnull=True,
    ).order_by("clase_fecha", "id")[:saldo]
    actualizadas = 0
    for consumo in deudas:
        consumo.pago = pago
        consumo.estado = AttendanceConsumption.Estado.CONSUMIDO
        consumo.save(update_fields=["pago", "estado", "actualizado_en"])
        actualizadas += 1
    return actualizadas

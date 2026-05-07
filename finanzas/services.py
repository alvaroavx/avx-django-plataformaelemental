from django.db.models import Count, Q, Sum
from django.utils.dateparse import parse_date

from asistencias.models import Asistencia
from personas.models import Persona
from plataformaelemental.context import aplicar_periodo

from .models import AttendanceConsumption, Payment


def _filtro_mismo_periodo_mensual(fecha, prefijo_campo):
    if isinstance(fecha, str):
        fecha = parse_date(fecha)
    if fecha is None:
        raise ValueError("La fecha entregada para filtrar periodo mensual no es valida.")
    return {
        f"{prefijo_campo}__year": fecha.year,
        f"{prefijo_campo}__month": fecha.month,
    }


def _misma_clave_periodo_mensual(fecha_a, fecha_b):
    if isinstance(fecha_a, str):
        fecha_a = parse_date(fecha_a)
    if isinstance(fecha_b, str):
        fecha_b = parse_date(fecha_b)
    if fecha_a is None or fecha_b is None:
        raise ValueError("No se pudo comparar el periodo mensual por una fecha invalida.")
    return fecha_a.year == fecha_b.year and fecha_a.month == fecha_b.month


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
            **_filtro_mismo_periodo_mensual(asistencia.sesion.fecha, "fecha_pago"),
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
    return _resumen_financiero_estudiante_queryset(pagos, consumos)


def _resumen_financiero_estudiante_queryset(pagos, consumos):
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


def resumen_financiero_estudiante_periodo(
    persona: Persona,
    inicio_periodo=None,
    fin_periodo=None,
    organizacion=None,
    mes=None,
    anio=None,
):
    pagos = Payment.objects.filter(persona=persona)
    consumos = AttendanceConsumption.objects.filter(persona=persona)
    if mes is not None or anio is not None:
        pagos = aplicar_periodo(pagos, "fecha_pago", mes=mes, anio=anio)
        consumos = aplicar_periodo(consumos, "clase_fecha", mes=mes, anio=anio)
    elif inicio_periodo and fin_periodo:
        pagos = pagos.filter(
            fecha_pago__gte=inicio_periodo,
            fecha_pago__lte=fin_periodo,
        )
        consumos = consumos.filter(
            clase_fecha__gte=inicio_periodo,
            clase_fecha__lte=fin_periodo,
        )
    if organizacion:
        pagos = pagos.filter(organizacion=organizacion)
        consumos = consumos.filter(asistencia__sesion__disciplina__organizacion=organizacion)
    return _resumen_financiero_estudiante_queryset(pagos, consumos)


def asociar_asistencia_a_pago(asistencia: Asistencia, pago: Payment) -> AttendanceConsumption:
    if asistencia.estado != Asistencia.Estado.PRESENTE:
        raise ValueError("Solo se pueden asociar asistencias presentes a un pago.")
    if pago.persona_id != asistencia.persona_id:
        raise ValueError("El pago seleccionado no corresponde a la misma persona.")
    if pago.organizacion_id != asistencia.sesion.disciplina.organizacion_id:
        raise ValueError("El pago seleccionado pertenece a otra organizacion.")
    if not _misma_clave_periodo_mensual(pago.fecha_pago, asistencia.sesion.fecha):
        raise ValueError("Solo se pueden asociar pagos del mismo mes y anio de la asistencia.")

    consumo = getattr(asistencia, "consumo_financiero", None) or asignar_consumo_asistencia(asistencia)
    if consumo.pago_id != pago.id and pago.saldo_clases <= 0:
        raise ValueError("El pago seleccionado no tiene saldo disponible.")

    consumo.persona = asistencia.persona
    consumo.clase_fecha = asistencia.sesion.fecha
    consumo.pago = pago
    consumo.estado = AttendanceConsumption.Estado.CONSUMIDO
    consumo.save(update_fields=["persona", "clase_fecha", "pago", "estado", "actualizado_en"])
    return consumo


def imputar_pago_a_deudas(pago: Payment) -> int:
    saldo = pago.saldo_clases
    if saldo <= 0:
        return 0
    deudas = AttendanceConsumption.objects.filter(
        persona=pago.persona,
        asistencia__sesion__disciplina__organizacion=pago.organizacion,
        **_filtro_mismo_periodo_mensual(pago.fecha_pago, "clase_fecha"),
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

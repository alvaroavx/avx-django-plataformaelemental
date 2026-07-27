from django.db import transaction
from django.db.models import Sum
from django.utils.dateparse import parse_date

from asistencias.models import Asistencia, ClaseLiberada
from personas.models import Persona
from plataformaelemental.context import aplicar_periodo

from ..models import AttendanceConsumption, Payment


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


def _plan_vigente_para_fecha(pago, fecha):
    if not pago.plan_id:
        return True
    if pago.plan.fecha_inicio and fecha < pago.plan.fecha_inicio:
        return False
    if pago.plan.fecha_fin and fecha > pago.plan.fecha_fin:
        return False
    return True


def pago_otorga_derecho(pago, asistencia, *, consumo_actual=None):
    if pago.revertido_en:
        return False
    if pago.persona_id != asistencia.persona_id:
        return False
    if pago.organizacion_id != asistencia.sesion.disciplina.organizacion_id:
        return False
    if not _misma_clave_periodo_mensual(pago.fecha_pago, asistencia.sesion.fecha):
        return False
    if not _plan_vigente_para_fecha(pago, asistencia.sesion.fecha):
        return False
    usados = pago.consumos.filter(estado=AttendanceConsumption.Estado.CONSUMIDO)
    if consumo_actual and consumo_actual.pago_id == pago.pk:
        usados = usados.exclude(pk=consumo_actual.pk)
    return pago.clases_asignadas > usados.count()


def consumo_tiene_derecho_valido(consumo):
    if consumo.estado != AttendanceConsumption.Estado.CONSUMIDO or not consumo.pago_id:
        return False
    if consumo.asistencia.estado != Asistencia.Estado.PRESENTE:
        return False
    if ClaseLiberada.objects.filter(asistencia=consumo.asistencia, revertida_en__isnull=True).exists():
        return False
    return pago_otorga_derecho(
        consumo.pago,
        consumo.asistencia,
        consumo_actual=consumo,
    )


@transaction.atomic
def asignar_consumo_asistencia(asistencia: Asistencia) -> AttendanceConsumption:
    asistencia = (
        Asistencia.objects.select_for_update()
        .select_related("persona", "sesion__disciplina__organizacion")
        .get(pk=asistencia.pk)
    )
    consumo, _ = AttendanceConsumption.objects.select_for_update().get_or_create(
        asistencia=asistencia,
        defaults={
            "persona": asistencia.persona,
            "clase_fecha": asistencia.sesion.fecha,
            "estado": AttendanceConsumption.Estado.PENDIENTE,
        },
    )
    consumo.persona = asistencia.persona
    consumo.clase_fecha = asistencia.sesion.fecha

    esta_liberada = ClaseLiberada.objects.filter(
        asistencia=asistencia,
        revertida_en__isnull=True,
    ).exists()
    if asistencia.estado != Asistencia.Estado.PRESENTE or esta_liberada:
        consumo.pago = None
        consumo.estado = AttendanceConsumption.Estado.PENDIENTE
        consumo.save(update_fields=["persona", "clase_fecha", "pago", "estado", "actualizado_en"])
        return consumo

    if consumo.pago_id:
        pago_actual = (
            Payment.objects.select_for_update(of=("self",))
            .select_related("plan")
            .filter(pk=consumo.pago_id)
            .first()
        )
        if pago_actual and pago_otorga_derecho(
            pago_actual,
            asistencia,
            consumo_actual=consumo,
        ):
            consumo.estado = AttendanceConsumption.Estado.CONSUMIDO
            consumo.save(update_fields=["persona", "clase_fecha", "estado", "actualizado_en"])
            return consumo

    pagos = (
        Payment.objects.select_for_update(of=("self",))
        .select_related("plan")
        .filter(
            persona=asistencia.persona,
            organizacion=asistencia.sesion.disciplina.organizacion,
            revertido_en__isnull=True,
            clases_asignadas__gt=0,
            **_filtro_mismo_periodo_mensual(asistencia.sesion.fecha, "fecha_pago"),
        )
        .order_by("fecha_pago", "id")
    )
    pago_disponible = next(
        (
            pago
            for pago in pagos
            if pago_otorga_derecho(pago, asistencia, consumo_actual=consumo)
        ),
        None,
    )
    consumo.pago = pago_disponible
    consumo.estado = (
        AttendanceConsumption.Estado.CONSUMIDO
        if pago_disponible
        else AttendanceConsumption.Estado.DEUDA
    )
    consumo.save(update_fields=["persona", "clase_fecha", "pago", "estado", "actualizado_en"])
    return consumo


def resumen_financiero_estudiante(persona: Persona, organizacion=None):
    pagos = Payment.objects.filter(persona=persona, revertido_en__isnull=True)
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
    pagos = Payment.objects.filter(persona=persona, revertido_en__isnull=True)
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


@transaction.atomic
def asociar_asistencia_a_pago(asistencia: Asistencia, pago: Payment) -> AttendanceConsumption:
    asistencia = Asistencia.objects.select_for_update().select_related(
        "persona",
        "sesion__disciplina__organizacion",
    ).get(pk=asistencia.pk)
    pago = (
        Payment.objects.select_for_update(of=("self",))
        .select_related("plan")
        .get(pk=pago.pk)
    )
    if asistencia.estado != Asistencia.Estado.PRESENTE:
        raise ValueError("Solo se pueden asociar asistencias presentes a un pago.")
    if ClaseLiberada.objects.filter(asistencia=asistencia, revertida_en__isnull=True).exists():
        raise ValueError("Una clase liberada no puede asociarse a un pago.")
    if pago.persona_id != asistencia.persona_id:
        raise ValueError("El pago seleccionado no corresponde a la misma persona.")
    if pago.organizacion_id != asistencia.sesion.disciplina.organizacion_id:
        raise ValueError("El pago seleccionado pertenece a otra organizacion.")
    if not _misma_clave_periodo_mensual(pago.fecha_pago, asistencia.sesion.fecha):
        raise ValueError("Solo se pueden asociar pagos del mismo mes y anio de la asistencia.")
    if pago.revertido_en:
        raise ValueError("El pago seleccionado está revertido.")
    if not _plan_vigente_para_fecha(pago, asistencia.sesion.fecha):
        raise ValueError("El plan del pago no está vigente para la fecha de la asistencia.")
    consumo = AttendanceConsumption.objects.filter(asistencia=asistencia).first()
    if not pago_otorga_derecho(pago, asistencia, consumo_actual=consumo):
        raise ValueError("El pago seleccionado no tiene saldo disponible.")

    consumo = consumo or asignar_consumo_asistencia(asistencia)
    consumo.persona = asistencia.persona
    consumo.clase_fecha = asistencia.sesion.fecha
    consumo.pago = pago
    consumo.estado = AttendanceConsumption.Estado.CONSUMIDO
    consumo.save(update_fields=["persona", "clase_fecha", "pago", "estado", "actualizado_en"])
    return consumo


@transaction.atomic
def imputar_pago_a_deudas(pago: Payment) -> int:
    pago = (
        Payment.objects.select_for_update(of=("self",))
        .select_related("plan")
        .get(pk=pago.pk)
    )
    if pago.revertido_en:
        return 0
    saldo = pago.saldo_clases
    if saldo <= 0:
        return 0
    deudas = (
        AttendanceConsumption.objects.select_for_update()
        .select_related("asistencia__sesion__disciplina__organizacion")
        .filter(
            persona=pago.persona,
            asistencia__sesion__disciplina__organizacion=pago.organizacion,
            **_filtro_mismo_periodo_mensual(pago.fecha_pago, "clase_fecha"),
            estado=AttendanceConsumption.Estado.DEUDA,
            pago__isnull=True,
        )
        .order_by("clase_fecha", "id")
    )
    actualizadas = 0
    for consumo in deudas:
        if actualizadas >= saldo:
            break
        if not pago_otorga_derecho(pago, consumo.asistencia, consumo_actual=consumo):
            continue
        consumo.pago = pago
        consumo.estado = AttendanceConsumption.Estado.CONSUMIDO
        consumo.save(update_fields=["pago", "estado", "actualizado_en"])
        actualizadas += 1
    return actualizadas

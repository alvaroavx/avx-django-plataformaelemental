from datetime import timedelta
from decimal import Decimal

from django.db import models
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from asistencias.models import Asistencia

from .models import CondicionCobroPersona, Pago

PROF_RATE = Decimal("3800")
TARIFA_CLASE_NORMAL = Decimal("9000")
BECA_FACTOR = Decimal("0.10")
DEBT_LOOKBACK_DAYS = 90


def _clamp_factor(value):
    value = Decimal(value or 0)
    if value < 0:
        return Decimal("0")
    if value > 1:
        return Decimal("1")
    return value


def _factor_plan(pago):
    precio_lista = pago.precio_lista_referencia or (pago.plan.precio if pago.plan else Decimal("0"))
    if not precio_lista:
        return Decimal("1")
    return _clamp_factor(Decimal(pago.monto) / Decimal(precio_lista))


def _factor_clase_especial(monto_especial):
    if not monto_especial:
        return Decimal("1")
    return _clamp_factor(Decimal(monto_especial) / TARIFA_CLASE_NORMAL)


def _condicion_cobro_activa(persona, organizacion, fecha):
    return (
        CondicionCobroPersona.objects.filter(
            persona=persona,
            organizacion=organizacion,
            activo=True,
            vigente_desde__lte=fecha,
        )
        .filter(Q(vigente_hasta__isnull=True) | Q(vigente_hasta__gte=fecha))
        .order_by("-vigente_desde", "-id")
        .first()
    )


def _pago_clase_para_sesion(persona, sesion):
    return (
        Pago.objects.filter(
            persona=persona,
            tipo=Pago.Tipo.CLASE,
            sesion=sesion,
        )
        .order_by("-paid_at", "-id")
        .first()
    )


def _pagos_disponibles_para_fecha(persona, fecha):
    return (
        Pago.objects.filter(
            persona=persona,
            tipo__in=[Pago.Tipo.PLAN, Pago.Tipo.CLASE],
            fecha_pago__lte=fecha,
        )
        .filter(Q(valido_hasta__isnull=True) | Q(valido_hasta__gte=fecha))
        .order_by("fecha_pago", "id")
    )


def _consumir_una_clase(pago):
    if pago.clases_restantes() <= 0:
        return False
    pago.clases_usadas = (pago.clases_usadas or 0) + 1
    pago.save(update_fields=["clases_usadas"])
    return True


def recalcular_ciclo_pago(pago):
    if pago.tipo not in [Pago.Tipo.PLAN, Pago.Tipo.CLASE]:
        return pago
    if not pago.paid_at:
        pago.paid_at = timezone.now()
    if not pago.ciclo_start:
        pago.ciclo_start = pago.paid_at
    dias = (pago.plan.duracion_dias if pago.plan and pago.plan.duracion_dias else 30) + (pago.freeze_days or 0)
    pago.ciclo_end = pago.ciclo_start + timedelta(days=dias)
    pago.valido_hasta = pago.ciclo_end.date()
    if pago.clases_total is None:
        if pago.tipo == Pago.Tipo.PLAN and pago.plan:
            pago.clases_total = pago.plan.clases_por_mes
        elif pago.tipo == Pago.Tipo.CLASE:
            pago.clases_total = 1
    if pago.tipo == Pago.Tipo.PLAN and not pago.precio_lista_referencia and pago.plan:
        pago.precio_lista_referencia = pago.plan.precio
    if pago.tipo == Pago.Tipo.CLASE and not pago.precio_lista_referencia:
        pago.precio_lista_referencia = TARIFA_CLASE_NORMAL
    pago.save()
    return pago


@transaction.atomic
def imputar_asistencia(asistencia):
    sesion = asistencia.sesion
    persona = asistencia.persona
    fecha = sesion.fecha
    organizacion = sesion.disciplina.organizacion

    pago_clase = _pago_clase_para_sesion(persona, sesion)
    if pago_clase:
        asistencia.pago_plan = pago_clase
        asistencia.estado_cobro = Asistencia.EstadoCobro.CUBIERTA
        if pago_clase.tarifa_clase_personalizada:
            asistencia.modalidad_cobro = Asistencia.ModalidadCobro.CLASE_ESPECIAL
            asistencia.monto_cobro = pago_clase.tarifa_clase_personalizada
            asistencia.factor_pago_profesor = _factor_clase_especial(pago_clase.tarifa_clase_personalizada)
        else:
            asistencia.modalidad_cobro = Asistencia.ModalidadCobro.CLASE_NORMAL
            asistencia.monto_cobro = TARIFA_CLASE_NORMAL
            asistencia.factor_pago_profesor = Decimal("1")
        asistencia.save(
            update_fields=["pago_plan", "estado_cobro", "modalidad_cobro", "monto_cobro", "factor_pago_profesor"]
        )
        return asistencia

    condicion = _condicion_cobro_activa(persona, organizacion, fecha)
    if condicion and condicion.tipo == CondicionCobroPersona.Tipo.BECA:
        asistencia.pago_plan = None
        asistencia.estado_cobro = Asistencia.EstadoCobro.CUBIERTA
        asistencia.modalidad_cobro = Asistencia.ModalidadCobro.BECA
        asistencia.monto_cobro = Decimal("0")
        asistencia.factor_pago_profesor = BECA_FACTOR
        asistencia.save(
            update_fields=["pago_plan", "estado_cobro", "modalidad_cobro", "monto_cobro", "factor_pago_profesor"]
        )
        return asistencia

    pagos = _pagos_disponibles_para_fecha(persona, fecha)
    for pago in pagos:
        if _consumir_una_clase(pago):
            asistencia.pago_plan = pago
            asistencia.estado_cobro = Asistencia.EstadoCobro.CUBIERTA
            asistencia.modalidad_cobro = Asistencia.ModalidadCobro.PLAN if pago.tipo == Pago.Tipo.PLAN else Asistencia.ModalidadCobro.CLASE_NORMAL
            asistencia.monto_cobro = pago.monto if pago.tipo == Pago.Tipo.CLASE else (pago.plan.precio if pago.plan else pago.monto)
            asistencia.factor_pago_profesor = _factor_plan(pago) if pago.tipo == Pago.Tipo.PLAN else Decimal("1")
            asistencia.save(
                update_fields=["pago_plan", "estado_cobro", "modalidad_cobro", "monto_cobro", "factor_pago_profesor"]
            )
            return asistencia

    asistencia.pago_plan = None
    asistencia.estado_cobro = Asistencia.EstadoCobro.DEUDA
    if condicion and condicion.tipo == CondicionCobroPersona.Tipo.CLASE_ESPECIAL:
        monto = condicion.tarifa_clase_especial or TARIFA_CLASE_NORMAL
        asistencia.modalidad_cobro = Asistencia.ModalidadCobro.CLASE_ESPECIAL
        asistencia.monto_cobro = monto
        asistencia.factor_pago_profesor = _factor_clase_especial(monto)
    else:
        asistencia.modalidad_cobro = Asistencia.ModalidadCobro.CLASE_NORMAL
        asistencia.monto_cobro = TARIFA_CLASE_NORMAL
        asistencia.factor_pago_profesor = Decimal("1")
    asistencia.save(update_fields=["pago_plan", "estado_cobro", "modalidad_cobro", "monto_cobro", "factor_pago_profesor"])
    return asistencia


@transaction.atomic
def aplicar_pago_a_deudas(persona, pago, lookback_days=DEBT_LOOKBACK_DAYS):
    if pago.tipo not in [Pago.Tipo.PLAN, Pago.Tipo.CLASE]:
        return 0
    pendientes = Asistencia.objects.filter(
        persona=persona,
        estado_cobro=Asistencia.EstadoCobro.DEUDA,
        sesion__fecha__lte=pago.fecha_pago,
    ).select_related("sesion", "sesion__disciplina").order_by("sesion__fecha", "id")
    if lookback_days:
        limite = pago.fecha_pago - timedelta(days=lookback_days)
        pendientes = pendientes.filter(sesion__fecha__gte=limite)

    if pago.tipo == Pago.Tipo.CLASE and pago.sesion_id:
        pendientes = pendientes.order_by(
            models.Case(
                models.When(sesion_id=pago.sesion_id, then=models.Value(0)),
                default=models.Value(1),
                output_field=models.IntegerField(),
            ),
            "sesion__fecha",
            "id",
        )

    aplicadas = 0
    for asistencia in pendientes:
        if pago.clases_restantes() <= 0:
            break
        if not _consumir_una_clase(pago):
            break
        asistencia.pago_plan = pago
        asistencia.estado_cobro = Asistencia.EstadoCobro.CUBIERTA
        if pago.tipo == Pago.Tipo.PLAN:
            asistencia.modalidad_cobro = Asistencia.ModalidadCobro.PLAN
            asistencia.factor_pago_profesor = _factor_plan(pago)
        asistencia.save(update_fields=["pago_plan", "estado_cobro", "modalidad_cobro", "factor_pago_profesor"])
        aplicadas += 1
    return aplicadas


def factor_pago_profesor_asistencia(asistencia):
    if asistencia.modalidad_cobro == Asistencia.ModalidadCobro.BECA:
        return BECA_FACTOR
    if asistencia.modalidad_cobro == Asistencia.ModalidadCobro.CLASE_ESPECIAL:
        return _factor_clase_especial(asistencia.monto_cobro)
    if asistencia.pago_plan_id and asistencia.pago_plan.tipo == Pago.Tipo.PLAN:
        return _factor_plan(asistencia.pago_plan)
    return Decimal("1")


def indicadores_deuda(periodo_inicio=None, periodo_fin=None, organizacion=None):
    qs = Asistencia.objects.select_related("persona", "sesion", "sesion__disciplina").filter(
        estado_cobro=Asistencia.EstadoCobro.DEUDA
    )
    if periodo_inicio:
        qs = qs.filter(sesion__fecha__gte=periodo_inicio)
    if periodo_fin:
        qs = qs.filter(sesion__fecha__lte=periodo_fin)
    if organizacion:
        qs = qs.filter(sesion__disciplina__organizacion=organizacion)

    estudiantes_deuda = qs.values("persona_id").distinct().count()
    return {
        "asistencias_deuda": qs.count(),
        "estudiantes_deuda": estudiantes_deuda,
    }

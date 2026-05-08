from django.db.models import CharField, Count, ExpressionWrapper, F, IntegerField, OuterRef, Prefetch, Q, Subquery, Sum, Value
from django.db.models.functions import Coalesce

from asistencias.models import Asistencia
from plataformaelemental.context import aplicar_periodo, filtros_periodo

from .models import AttendanceConsumption, Category, DocumentoTributario, Payment, PaymentPlan, Transaction


def planes_queryset(organizacion=None):
    queryset = PaymentPlan.objects.select_related("organizacion").order_by(
        "organizacion__nombre",
        "-es_por_defecto",
        "nombre",
    )
    if organizacion:
        queryset = queryset.filter(organizacion=organizacion)
    return queryset


def _subquery_disciplina_principal(*, mes=None, anio=None):
    filtros = {
        "persona_id": OuterRef("persona_id"),
        "sesion__disciplina__organizacion_id": OuterRef("organizacion_id"),
        "estado": Asistencia.Estado.PRESENTE,
    }
    filtros.update(filtros_periodo("sesion__fecha", mes=mes, anio=anio))
    return (
        Asistencia.objects.filter(**filtros)
        .values("sesion__disciplina__nombre")
        .annotate(total=Count("id"))
        .order_by("-total", "sesion__disciplina__nombre")
        .values("sesion__disciplina__nombre")[:1]
    )


def pagos_queryset(request, *, organizacion=None, mes=None, anio=None):
    disciplina_principal_historica = _subquery_disciplina_principal(mes=mes, anio=anio)
    queryset = (
        Payment.objects.select_related("persona", "organizacion", "plan", "documento_tributario")
        .annotate(
            clases_consumidas_calculadas=Count(
                "consumos",
                filter=Q(consumos__estado=AttendanceConsumption.Estado.CONSUMIDO),
                distinct=True,
            )
        )
        .annotate(
            saldo_clases_calculado=ExpressionWrapper(
                F("clases_asignadas") - F("clases_consumidas_calculadas"),
                output_field=IntegerField(),
            )
        )
        .annotate(
            disciplina_principal_nombre=Coalesce(
                Subquery(disciplina_principal_historica, output_field=CharField()),
                Value("Sin disciplina", output_field=CharField()),
            )
        )
        .order_by("-fecha_pago", "-id")
    )
    queryset = aplicar_periodo(queryset, "fecha_pago", request=request)
    if organizacion:
        queryset = queryset.filter(organizacion=organizacion)

    q = request.GET.get("q")
    metodo = request.GET.get("metodo")
    if q:
        queryset = queryset.filter(Q(persona__nombres__icontains=q) | Q(persona__apellidos__icontains=q))
    if metodo:
        queryset = queryset.filter(metodo_pago=metodo)
    return queryset


def resumen_pagos(queryset):
    return queryset.aggregate(
        total_pagos_monto=Sum("monto_total"),
        total_iva_monto=Sum("monto_iva"),
        total_clases_pagadas=Sum("clases_asignadas"),
        total_saldo_clases=Sum("saldo_clases_calculado"),
    )


def pago_detail_queryset():
    return Payment.objects.select_related("persona", "organizacion", "plan", "documento_tributario").prefetch_related(
        Prefetch(
            "consumos",
            queryset=AttendanceConsumption.objects.select_related(
                "asistencia__sesion__disciplina",
                "asistencia__sesion__disciplina__organizacion",
            ).order_by("-clase_fecha", "-id"),
        )
    )


def documentos_tributarios_queryset(request, *, organizacion=None):
    queryset = DocumentoTributario.objects.select_related(
        "organizacion",
        "documento_relacionado",
        "persona_relacionada",
        "organizacion_relacionada",
    ).annotate(
        pagos_asociados_total=Count("pagos_asociados", distinct=True),
        transacciones_asociadas_total=Count("transacciones_asociadas", distinct=True),
    )
    queryset = aplicar_periodo(queryset, "fecha_emision", request=request)
    if organizacion:
        queryset = queryset.filter(organizacion=organizacion)
    return queryset.order_by("-fecha_emision", "-id")


def resumen_documentos_tributarios(queryset):
    return queryset.aggregate(
        total_documentos=Count("id"),
        monto_total_documentos=Sum("monto_total"),
        monto_total_iva=Sum("monto_iva"),
        monto_total_retencion=Sum("retencion_monto"),
        total_pagos_asociados=Sum("pagos_asociados_total"),
        total_transacciones_asociadas=Sum("transacciones_asociadas_total"),
    )


def transacciones_queryset(request, *, organizacion=None):
    queryset = (
        Transaction.objects.select_related("organizacion", "categoria")
        .prefetch_related("documentos_tributarios")
        .order_by("-fecha", "-id")
    )
    queryset = aplicar_periodo(queryset, "fecha", request=request)
    if organizacion:
        queryset = queryset.filter(organizacion=organizacion)
    return queryset


def resumen_transacciones(queryset):
    return queryset.aggregate(
        total_transacciones=Count("id"),
        total_ingresos=Sum("monto", filter=Q(tipo=Transaction.Tipo.INGRESO)),
        total_egresos=Sum("monto", filter=Q(tipo=Transaction.Tipo.EGRESO)),
    )


def dashboard_querysets(request, *, organizacion=None):
    pagos_qs = aplicar_periodo(Payment.objects.all(), "fecha_pago", request=request)
    transacciones_qs = aplicar_periodo(Transaction.objects.all(), "fecha", request=request)
    if organizacion:
        pagos_qs = pagos_qs.filter(organizacion=organizacion)
        transacciones_qs = transacciones_qs.filter(organizacion=organizacion)
    return pagos_qs, transacciones_qs


def resumen_dashboard(pagos_qs, transacciones_qs):
    ingresos_pagos = pagos_qs.aggregate(total=Sum("monto_total")).get("total") or 0
    ingresos_transacciones = (
        transacciones_qs.filter(tipo=Transaction.Tipo.INGRESO).aggregate(total=Sum("monto")).get("total") or 0
    )
    egresos = transacciones_qs.filter(tipo=Transaction.Tipo.EGRESO).aggregate(total=Sum("monto")).get("total") or 0
    iva_debito = pagos_qs.aggregate(total=Sum("monto_iva")).get("total") or 0
    ingresos_exentos = pagos_qs.filter(monto_iva=0).aggregate(total=Sum("monto_total")).get("total") or 0
    categorias_totales = (
        transacciones_qs.values("categoria__nombre", "categoria__tipo").annotate(total=Sum("monto")).order_by("-total")
    )
    ingresos_totales = ingresos_pagos + ingresos_transacciones
    return {
        "ingresos_totales": ingresos_totales,
        "egresos_totales": egresos,
        "balance": ingresos_totales - egresos,
        "iva_debito": iva_debito,
        "ingresos_exentos": ingresos_exentos,
        "categorias_totales": categorias_totales,
    }


def consolidado_categorias_queryset(request, *, organizacion=None):
    queryset = aplicar_periodo(Transaction.objects.all(), "fecha", request=request)
    if organizacion:
        queryset = queryset.filter(organizacion=organizacion)
    return queryset.values("categoria__nombre", "categoria__tipo").annotate(total=Sum("monto")).order_by(
        "categoria__tipo",
        "-total",
    )


def categorias_queryset():
    return Category.objects.order_by("tipo", "nombre")


def pagos_export_queryset(request, *, organizacion=None):
    queryset = aplicar_periodo(
        Payment.objects.select_related("persona", "organizacion"),
        "fecha_pago",
        request=request,
    )
    if organizacion:
        queryset = queryset.filter(organizacion=organizacion)
    return queryset


def transacciones_export_queryset(request, *, organizacion=None):
    queryset = aplicar_periodo(
        Transaction.objects.select_related("categoria", "organizacion"),
        "fecha",
        request=request,
    )
    if organizacion:
        queryset = queryset.filter(organizacion=organizacion)
    return queryset

from decimal import Decimal

from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Case, Count, IntegerField, Max, Sum, Value, When
from django.http import Http404
from django.urls import reverse
from django.utils import timezone

from asistencias.models import Asistencia, SesionClase
from finanzas.models import AttendanceConsumption, Payment, Transaction
from finanzas.services import resumen_financiero_estudiante, resumen_financiero_estudiante_periodo
from personas.models import Persona, SolicitudAcceso
from personas.permissions import (
    ACCION_ROLES,
    ACCION_ADMINISTRAR_PERSONAS,
    ACCION_ADMINISTRAR_SESIONES,
    ACCION_VER_FINANZAS,
    normalizar_codigo_rol,
)
from personas.search import filtrar_por_fragmentos

from .context import aplicar_periodo, organizaciones_visibles_para_usuario, resolver_periodo


def _alcances_por_accion(request, organizacion):
    acciones = (ACCION_ADMINISTRAR_SESIONES, ACCION_VER_FINANZAS, ACCION_ADMINISTRAR_PERSONAS)
    organizaciones_ids = (
        [organizacion.pk]
        if organizacion is not None
        else list(organizaciones_visibles_para_usuario(request.user).values_list("pk", flat=True))
    )
    if request.user.is_superuser or request.user.is_staff:
        return {accion: organizaciones_ids for accion in acciones}

    # Las vistas de detalle de estos dominios exigen una organización concreta
    # para los roles organizacionales. No construimos un agregado multi-org con
    # enlaces que después responderían 403 ni elegimos una organización de forma
    # silenciosa: el usuario debe seleccionar el contexto que quiere operar.
    if organizacion is None:
        return {accion: [] for accion in acciones}

    persona = getattr(request.user, "persona", None)
    if not persona:
        return {accion: [] for accion in acciones}
    roles_por_organizacion = {}
    for organizacion_id, codigo in persona.roles.filter(
        activo=True,
        organizacion_id__in=organizaciones_ids,
    ).values_list("organizacion_id", "rol__codigo"):
        roles_por_organizacion.setdefault(organizacion_id, set()).add(normalizar_codigo_rol(codigo))
    return {
        accion: [
            organizacion_id
            for organizacion_id, roles in roles_por_organizacion.items()
            if roles.intersection(ACCION_ROLES[accion])
        ]
        for accion in acciones
    }


def _query_global(request, **extra):
    params = request.GET.copy()
    params.pop("persona_q", None)
    params.pop("persona_id", None)
    params.pop("page", None)
    params.update({key: value for key, value in extra.items() if value not in (None, "")})
    return params.urlencode()


def _sesiones_periodo(request, organizaciones_ids):
    return aplicar_periodo(SesionClase.objects.all(), "fecha", request=request).filter(
        disciplina__organizacion_id__in=organizaciones_ids
    )


def _asistencias_periodo(request, organizaciones_ids):
    return aplicar_periodo(Asistencia.objects.all(), "sesion__fecha", request=request).filter(
        sesion__disciplina__organizacion_id__in=organizaciones_ids
    )


def _consumos_periodo(request, organizaciones_ids):
    return aplicar_periodo(AttendanceConsumption.objects.all(), "clase_fecha", request=request).filter(
        asistencia__sesion__disciplina__organizacion_id__in=organizaciones_ids
    )


def _transacciones_periodo(request, organizaciones_ids):
    return aplicar_periodo(Transaction.objects.all(), "fecha", request=request).filter(
        organizacion_id__in=organizaciones_ids
    )


def _metricas_academicas(request, organizaciones_ids):
    hoy = timezone.localdate()
    sesiones = _sesiones_periodo(request, organizaciones_ids)
    asistencias = _asistencias_periodo(request, organizaciones_ids)
    resumen = asistencias.aggregate(
        registros=Count("id"),
        personas=Count("persona_id", distinct=True),
    )
    proximas = (
        sesiones.filter(fecha__gte=hoy)
        .filter(estado__in=(SesionClase.Estado.PROGRAMADA, SesionClase.Estado.ABIERTA))
        .select_related("disciplina", "disciplina__organizacion", "bloque")
        .order_by("fecha", "bloque__hora_inicio", "pk")[:3]
    )
    sesiones_hoy = list(
        SesionClase.objects.filter(
            fecha=hoy,
            disciplina__organizacion_id__in=organizaciones_ids,
        )
        .select_related("disciplina", "disciplina__organizacion", "bloque")
        .prefetch_related("profesores")
        .annotate(
            asistencias_total=Count("asistencias", distinct=True),
            sin_horario=Case(
                When(bloque__isnull=True, then=Value(1)),
                default=Value(0),
                output_field=IntegerField(),
            ),
        )
        .order_by("sin_horario", "bloque__hora_inicio", "disciplina__nombre", "pk")
    )
    return {
        "sesiones_completadas": sesiones.filter(estado=SesionClase.Estado.COMPLETADA).count(),
        "registros_asistencia": resumen["registros"],
        "personas_con_asistencia": resumen["personas"],
        "proximas_sesiones": proximas,
        "sesiones_hoy": sesiones_hoy,
        "fecha_hoy": hoy,
    }


def _metricas_financieras(request, organizaciones_ids):
    consumos = _consumos_periodo(request, organizaciones_ids)
    transacciones = _transacciones_periodo(request, organizaciones_ids)
    deuda = consumos.filter(estado=AttendanceConsumption.Estado.DEUDA)
    resumen_deuda = deuda.aggregate(clases=Count("id"), personas=Count("persona_id", distinct=True))
    ingresos = (
        transacciones.filter(tipo=Transaction.Tipo.INGRESO).aggregate(total=Sum("monto"))["total"]
        or Decimal("0")
    )
    transacciones_sin_documento = (
        transacciones.annotate(documentos_total=Count("documentos_tributarios", distinct=True))
        .filter(documentos_total=0)
        .count()
    )
    return {
        "clases_en_deuda": resumen_deuda["clases"],
        "personas_con_deuda": resumen_deuda["personas"],
        "ingresos_contables": ingresos,
        "transacciones_sin_documento": transacciones_sin_documento,
    }


def _detalle_sesiones(request, organizaciones_ids):
    registros = (
        _sesiones_periodo(request, organizaciones_ids)
        .filter(estado=SesionClase.Estado.COMPLETADA)
        .select_related("disciplina", "disciplina__organizacion", "bloque")
        .annotate(asistencias_total=Count("asistencias"))
        .order_by("-fecha", "disciplina__nombre", "pk")
    )
    return {
        "titulo": "Sesiones completadas",
        "descripcion": "Sesiones cerradas que componen el indicador del período seleccionado.",
        "tipo": "sesiones",
        "registros": registros,
        "valor": registros.count(),
    }


def _detalle_personas_asistencia(request, organizaciones_ids):
    registros = (
        _asistencias_periodo(request, organizaciones_ids)
        .values("persona_id", "persona__nombres", "persona__apellidos")
        .annotate(registros_total=Count("id"), ultima_fecha=Max("sesion__fecha"))
        .order_by("persona__apellidos", "persona__nombres", "persona_id")
    )
    return {
        "titulo": "Personas con asistencia registrada",
        "descripcion": "Personas únicas con al menos un registro de asistencia en el período.",
        "tipo": "personas_asistencia",
        "registros": registros,
        "valor": registros.count(),
    }


def _detalle_clases_deuda(request, organizaciones_ids):
    registros = (
        _consumos_periodo(request, organizaciones_ids)
        .filter(estado=AttendanceConsumption.Estado.DEUDA)
        .select_related(
            "persona",
            "asistencia__sesion__disciplina",
            "asistencia__sesion__disciplina__organizacion",
        )
        .order_by("-clase_fecha", "persona__apellidos", "persona__nombres", "pk")
    )
    return {
        "titulo": "Clases en deuda",
        "descripcion": "Consumos de asistencia que permanecen en estado de deuda en el período.",
        "tipo": "clases_deuda",
        "registros": registros,
        "valor": registros.count(),
    }


def _detalle_ingresos(request, organizaciones_ids):
    registros = (
        _transacciones_periodo(request, organizaciones_ids)
        .filter(tipo=Transaction.Tipo.INGRESO)
        .select_related("organizacion", "categoria")
        .order_by("-fecha", "-pk")
    )
    monto = registros.aggregate(total=Sum("monto"))["total"] or Decimal("0")
    return {
        "titulo": "Ingresos contables",
        "descripcion": "Transacciones de ingreso cuya suma produce el indicador del período.",
        "tipo": "ingresos",
        "registros": registros,
        "valor": monto,
        "cantidad_registros": registros.count(),
    }


DETALLES_METRICAS = {
    "sesiones-completadas": (ACCION_ADMINISTRAR_SESIONES, _detalle_sesiones),
    "personas-con-asistencia": (ACCION_ADMINISTRAR_SESIONES, _detalle_personas_asistencia),
    "clases-en-deuda": (ACCION_VER_FINANZAS, _detalle_clases_deuda),
    "ingresos-contables": (ACCION_VER_FINANZAS, _detalle_ingresos),
}


def construir_detalle_metrica(request, *, metrica, organizacion):
    configuracion = DETALLES_METRICAS.get(metrica)
    if configuracion is None:
        raise Http404("El indicador solicitado no existe.")
    accion, constructor = configuracion
    organizaciones_ids = _alcances_por_accion(request, organizacion)[accion]
    if not organizaciones_ids:
        raise PermissionDenied("No tienes acceso al detalle de este indicador en el contexto seleccionado.")

    detalle = constructor(request, organizaciones_ids)
    paginator = Paginator(detalle.pop("registros"), 25)
    detalle["page_obj"] = paginator.get_page(request.GET.get("page"))
    detalle["paginator"] = paginator
    detalle["metrica"] = metrica
    detalle["dashboard_query_global"] = _query_global(request)
    detalle["volver_url"] = f'{reverse("elemental_apps")}?{_query_global(request)}'
    return detalle


def _consulta_persona(request, organizaciones_ids, organizacion):
    termino = (request.GET.get("persona_q") or "").strip()
    persona_id = request.GET.get("persona_id")
    resultado = {"termino": termino, "coincidencias": [], "persona": None}
    if not organizaciones_ids:
        return resultado

    base = Persona.objects.filter(
        roles__activo=True,
        roles__organizacion_id__in=organizaciones_ids,
    ).distinct()
    if len(termino) >= 2:
        resultado["coincidencias"] = list(
            filtrar_por_fragmentos(
                base,
                termino,
                campos=("nombres", "apellidos", "email", "telefono", "rut"),
                prefijo="dashboard_persona",
            ).order_by("apellidos", "nombres")[:8]
        )
    if not persona_id or not persona_id.isdigit():
        return resultado

    persona = base.filter(pk=persona_id).first()
    if not persona:
        return resultado

    asistencias = aplicar_periodo(
        Asistencia.objects.filter(persona=persona), "sesion__fecha", request=request
    ).filter(sesion__disciplina__organizacion_id__in=organizaciones_ids)
    pagos = aplicar_periodo(
        Payment.objects.filter(persona=persona, revertido_en__isnull=True), "fecha_pago", request=request
    ).filter(organizacion_id__in=organizaciones_ids)
    consumos = aplicar_periodo(
        AttendanceConsumption.objects.filter(persona=persona), "clase_fecha", request=request
    ).filter(asistencia__sesion__disciplina__organizacion_id__in=organizaciones_ids)
    periodo = resolver_periodo(request)
    resumen_periodo = resumen_financiero_estudiante_periodo(
        persona,
        organizacion=organizacion,
        mes=periodo["mes"],
        anio=periodo["anio"],
    )
    resumen_actual = resumen_financiero_estudiante(persona, organizacion=organizacion) if organizacion else None
    resumen_pagos = pagos.aggregate(total=Sum("monto_total"), cantidad=Count("id"))
    resultado["persona"] = {
        "objeto": persona,
        "asistencias_registradas": asistencias.count(),
        "ultima_asistencia": asistencias.order_by("-sesion__fecha").values_list("sesion__fecha", flat=True).first(),
        "pagos_registrados": resumen_pagos["cantidad"],
        "monto_pagado": resumen_pagos["total"] or Decimal("0"),
        "resumen_periodo": resumen_periodo,
        "resumen_actual": resumen_actual,
        "asistencias_recientes": list(
            asistencias.select_related("sesion__disciplina", "sesion__disciplina__organizacion")
            .order_by("-sesion__fecha", "-pk")[:3]
        ),
        "pagos_recientes": list(
            pagos.select_related("organizacion", "plan").order_by("-fecha_pago", "-pk")[:3]
        ),
        "detalle_url": f'{reverse("personas:persona_detail", args=[persona.pk])}?{_query_global(request)}',
        "pagos_url": f'{reverse("finanzas:pagos_list")}?{_query_global(request, persona=persona.pk)}',
    }
    return resultado


def construir_dashboard_general(request, *, organizacion):
    alcances = _alcances_por_accion(request, organizacion)
    organizaciones_academicas = alcances[ACCION_ADMINISTRAR_SESIONES]
    organizaciones_financieras = alcances[ACCION_VER_FINANZAS]
    organizaciones_personas = alcances[ACCION_ADMINISTRAR_PERSONAS]

    context = {
        "dashboard_academico": None,
        "dashboard_financiero": None,
        "consulta_persona": None,
        "dashboard_alertas": [],
        "dashboard_query_global": _query_global(request),
    }
    if organizaciones_academicas:
        context["dashboard_academico"] = _metricas_academicas(request, organizaciones_academicas)
    if organizaciones_financieras:
        context["dashboard_financiero"] = _metricas_financieras(request, organizaciones_financieras)
    if organizaciones_personas:
        context["consulta_persona"] = _consulta_persona(request, organizaciones_personas, organizacion)

    financiero = context["dashboard_financiero"]
    if financiero and organizaciones_personas and financiero["personas_con_deuda"]:
        context["dashboard_alertas"].append(
            {
                "icono": "bi-exclamation-circle",
                "cantidad": financiero["personas_con_deuda"],
                "texto": "personas con clases en deuda",
                "url": f'{reverse("personas:personas_list")}?{_query_global(request, con_deuda="si")}',
            }
        )
    if financiero and financiero["transacciones_sin_documento"]:
        context["dashboard_alertas"].append(
            {
                "icono": "bi-file-earmark-excel",
                "cantidad": financiero["transacciones_sin_documento"],
                "texto": "transacciones sin documento asociado",
                "url": f'{reverse("finanzas:transacciones_list")}?{_query_global(request, sin_documento="si")}',
            }
        )
    if request.user.has_perm("personas.gestionar_solicitudes_acceso"):
        solicitudes = SolicitudAcceso.objects.filter(estado=SolicitudAcceso.Estado.PENDIENTE).count()
        if solicitudes:
            context["dashboard_alertas"].append(
                {
                    "icono": "bi-person-lock",
                    "cantidad": solicitudes,
                    "texto": "solicitudes de acceso pendientes",
                    "url": reverse("personas:solicitudes_acceso_list"),
                }
            )
    context["dashboard_alertas"] = context["dashboard_alertas"][:5]
    return context

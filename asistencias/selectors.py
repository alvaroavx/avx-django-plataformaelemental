from django.db.models import Count, Q

from plataformaelemental.context import aplicar_periodo, filtros_periodo, resolver_periodo

from .models import Asistencia, SesionClase


def asistencias_export_queryset(request, *, organizacion=None):
    queryset = (
        Asistencia.objects.select_related("persona", "sesion__disciplina", "sesion__disciplina__organizacion")
        .prefetch_related("sesion__profesores")
        .order_by("sesion__fecha", "sesion_id", "persona__apellidos", "persona__nombres", "id")
    )
    queryset = aplicar_periodo(queryset, "sesion__fecha", request=request)
    if organizacion:
        queryset = queryset.filter(sesion__disciplina__organizacion=organizacion)
    disciplina_id = request.GET.get("disciplina")
    if disciplina_id:
        queryset = queryset.filter(sesion__disciplina_id=disciplina_id)
    return queryset


def resumen_profesores_periodo_queryset(request, *, organizacion=None):
    from personas.models import PersonaRol

    periodo = resolver_periodo(request)
    roles = (
        PersonaRol.objects.select_related("persona", "organizacion")
        .filter(rol__codigo__iexact="PROFESOR", activo=True, persona__activo=True)
        .order_by("persona__apellidos", "persona__nombres", "organizacion__nombre")
    )
    if organizacion:
        roles = roles.filter(organizacion=organizacion)

    persona_ids = list(roles.values_list("persona_id", flat=True))
    organizacion_ids = list(roles.values_list("organizacion_id", flat=True))
    if not persona_ids or not organizacion_ids:
        return roles.none(), {}, {}, {}

    filtros_fecha = filtros_periodo("sesion__fecha", mes=periodo["mes"], anio=periodo["anio"])
    asistencias_agregadas = (
        Asistencia.objects.filter(
            sesion__profesores__in=persona_ids,
            sesion__disciplina__organizacion_id__in=organizacion_ids,
            **filtros_fecha,
        )
        .values("sesion__profesores", "sesion__disciplina__organizacion")
        .annotate(
            asistencias_mes=Count("id"),
            alumnos_unicos=Count("persona", distinct=True),
        )
    )
    asistencias_por_profesor = {
        (item["sesion__profesores"], item["sesion__disciplina__organizacion"]): item
        for item in asistencias_agregadas
    }

    sesiones_agregadas = (
        SesionClase.objects.filter(
            profesores__in=persona_ids,
            disciplina__organizacion_id__in=organizacion_ids,
            **filtros_periodo("fecha", mes=periodo["mes"], anio=periodo["anio"]),
        )
        .exclude(estado=SesionClase.Estado.CANCELADA)
        .values("profesores", "disciplina__organizacion")
        .annotate(
            sesiones_mes=Count("id", filter=Q(estado=SesionClase.Estado.COMPLETADA), distinct=True),
        )
    )
    sesiones_por_profesor = {
        (item["profesores"], item["disciplina__organizacion"]): item["sesiones_mes"]
        for item in sesiones_agregadas
    }

    disciplinas = (
        SesionClase.objects.filter(
            profesores__in=persona_ids,
            disciplina__organizacion_id__in=organizacion_ids,
            **filtros_periodo("fecha", mes=periodo["mes"], anio=periodo["anio"]),
        )
        .values("profesores", "disciplina__organizacion", "disciplina__nombre")
        .distinct()
        .order_by("disciplina__nombre")
    )
    disciplinas_por_profesor = {}
    for item in disciplinas:
        key = (item["profesores"], item["disciplina__organizacion"])
        disciplinas_por_profesor.setdefault(key, []).append(item["disciplina__nombre"])

    return roles, asistencias_por_profesor, sesiones_por_profesor, disciplinas_por_profesor

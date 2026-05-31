from django.db.models import Count, Max, Q, Sum

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


def estudiantes_operativos_periodo(request, *, organizacion=None):
    from finanzas.models import AttendanceConsumption, Payment
    from personas.models import Persona

    estudiantes = (
        Persona.objects.filter(roles__rol__codigo="ESTUDIANTE")
        .distinct()
        .prefetch_related("roles__organizacion", "roles__rol")
        .order_by("apellidos", "nombres")
    )
    if organizacion:
        estudiantes = estudiantes.filter(roles__organizacion=organizacion).distinct()

    personas = list(estudiantes)
    persona_ids = [persona.pk for persona in personas]
    if not persona_ids:
        return []

    asistencias_qs = Asistencia.objects.filter(
        persona_id__in=persona_ids,
        **filtros_periodo("sesion__fecha", request=request),
    )
    asistencias_historicas_qs = Asistencia.objects.filter(persona_id__in=persona_ids)
    pagos_qs = Payment.objects.filter(
        persona_id__in=persona_ids,
        **filtros_periodo("fecha_pago", request=request),
    )
    consumos_qs = AttendanceConsumption.objects.filter(
        persona_id__in=persona_ids,
        **filtros_periodo("clase_fecha", request=request),
    )
    if organizacion:
        asistencias_qs = asistencias_qs.filter(sesion__disciplina__organizacion=organizacion)
        asistencias_historicas_qs = asistencias_historicas_qs.filter(sesion__disciplina__organizacion=organizacion)
        pagos_qs = pagos_qs.filter(organizacion=organizacion)
        consumos_qs = consumos_qs.filter(asistencia__sesion__disciplina__organizacion=organizacion)

    asistencias_por_persona = {
        item["persona_id"]: item
        for item in asistencias_qs.values("persona_id").annotate(
            asistencias_mes=Count("id"),
            ultima_asistencia_periodo=Max("sesion__fecha"),
        )
    }
    ultimas_asistencias = {
        item["persona_id"]: item["ultima_asistencia"]
        for item in asistencias_historicas_qs.values("persona_id").annotate(ultima_asistencia=Max("sesion__fecha"))
    }
    pagos_por_persona = {
        item["persona_id"]: item
        for item in pagos_qs.values("persona_id").annotate(
            clases_pagadas=Sum("clases_asignadas"),
            total_pagado=Sum("monto_total"),
            ultimo_pago=Max("fecha_pago"),
        )
    }
    consumos_por_persona = {
        item["persona_id"]: item
        for item in consumos_qs.values("persona_id").annotate(
            clases_usadas=Count("id", filter=Q(estado=AttendanceConsumption.Estado.CONSUMIDO)),
            deuda_clases=Count("id", filter=Q(estado=AttendanceConsumption.Estado.DEUDA)),
        )
    }

    resultado = []
    for persona in personas:
        asistencias_data = asistencias_por_persona.get(persona.pk, {})
        pagos_data = pagos_por_persona.get(persona.pk, {})
        consumos_data = consumos_por_persona.get(persona.pk, {})
        clases_pagadas = pagos_data.get("clases_pagadas") or 0
        clases_usadas = consumos_data.get("clases_usadas") or 0
        clases_restantes = clases_pagadas - clases_usadas
        deuda_clases = consumos_data.get("deuda_clases") or 0
        asistencias_mes = asistencias_data.get("asistencias_mes") or 0
        if deuda_clases:
            estado_financiero = "Pendiente"
            estado_financiero_class = "warning"
        elif asistencias_mes and not clases_pagadas:
            estado_financiero = "Sin pago"
            estado_financiero_class = "danger"
        elif clases_restantes >= 0 and (clases_pagadas or asistencias_mes):
            estado_financiero = "OK"
            estado_financiero_class = "success"
        else:
            estado_financiero = "Revisar"
            estado_financiero_class = "secondary"

        organizaciones = sorted(
            {
                rol.organizacion.nombre
                for rol in persona.roles.all()
                if rol.rol.codigo == "ESTUDIANTE" and (not organizacion or rol.organizacion_id == organizacion.pk)
            }
        )
        resultado.append(
            {
                "persona": persona,
                "organizaciones": organizaciones,
                "asistencias_mes": asistencias_mes,
                "ultima_asistencia": asistencias_data.get("ultima_asistencia_periodo") or ultimas_asistencias.get(persona.pk),
                "activo_mes": asistencias_mes > 0,
                "clases_pagadas": clases_pagadas,
                "clases_usadas": clases_usadas,
                "clases_restantes": clases_restantes,
                "total_pagado": pagos_data.get("total_pagado") or 0,
                "ultimo_pago": pagos_data.get("ultimo_pago"),
                "deuda_clases": deuda_clases,
                "estado_financiero": estado_financiero,
                "estado_financiero_class": estado_financiero_class,
            }
        )
    return resultado

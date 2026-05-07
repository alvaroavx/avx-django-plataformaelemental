import calendar
from decimal import Decimal

from django.contrib import messages
from django.db.models import Count, Prefetch, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from finanzas.models import AttendanceConsumption, Payment
from personas.models import Organizacion, Persona, PersonaRol, Rol
from plataformaelemental.context import (
    aplicar_periodo,
    descripcion_periodo,
    filtros_periodo,
    nav_context,
    organizacion_desde_request,
    resolver_periodo,
)

from .decorators import role_required
from .forms import (
    AsistenciaMasivaForm,
    DisciplinaForm,
    PersonaRapidaForm,
    SesionBasicaForm,
)
from .models import Asistencia, Disciplina, SesionClase
from .utils import ROLE_ADMIN
from .utils import disciplinas_vigentes_qs, profesores_vigentes_qs


def _periodo(request):
    """Retorna un periodo de referencia para vistas que requieren una fecha base visible."""
    periodo = resolver_periodo(request)
    return periodo["referencia_inicio"], periodo["referencia_fin"]


def _url_con_filtros(request, nombre_url, **kwargs):
    """Construye una URL manteniendo los filtros actuales del querystring."""
    url = reverse(nombre_url, kwargs=kwargs or None)
    query = request.GET.urlencode()
    return f"{url}?{query}" if query else url


def _url_actual_con_filtros(request, remove_params=None, **extra_params):
    params = request.GET.copy()
    if remove_params:
        for key in remove_params:
            params.pop(key, None)
    for key, value in extra_params.items():
        params[key] = value
    query = params.urlencode()
    return f"{request.path}?{query}" if query else request.path


def _crear_persona_estudiante_en_organizacion(persona_form, organizacion):
    """Crea una persona rapida y la asigna como ESTUDIANTE a la organizacion indicada."""
    if not organizacion:
        persona_form.add_error(
            None,
            "Debes seleccionar una organización en el filtro superior antes de crear a la persona.",
        )
        return None

    rol_estudiante = Rol.objects.filter(codigo="ESTUDIANTE").first()
    if not rol_estudiante:
        persona_form.add_error(
            None,
            "No existe el rol ESTUDIANTE configurado para asignar a la nueva persona.",
        )
        return None

    persona = Persona.objects.create(
        nombres=persona_form.cleaned_data["nombres"].strip(),
        apellidos=persona_form.cleaned_data.get("apellidos", "").strip(),
        telefono=persona_form.cleaned_data.get("telefono", "").strip(),
    )
    PersonaRol.objects.get_or_create(
        persona=persona,
        rol=rol_estudiante,
        organizacion=organizacion,
        defaults={"activo": True},
    )
    return persona


@role_required(ROLE_ADMIN)
def dashboard(request):
    """Panel principal con métricas operativas según período y organización."""
    context = nav_context(request)
    organizacion = organizacion_desde_request(request)
    sesiones_mes = (
        aplicar_periodo(SesionClase.objects.all(), "fecha", request=request)
        .select_related("disciplina")
        .prefetch_related("profesores")
    )
    if organizacion:
        sesiones_mes = sesiones_mes.filter(disciplina__organizacion=organizacion)
    sesiones_realizadas_mes = sesiones_mes.filter(estado=SesionClase.Estado.COMPLETADA).count()
    asistencias_mes_qs = aplicar_periodo(Asistencia.objects.all(), "sesion__fecha", request=request)
    if organizacion:
        asistencias_mes_qs = asistencias_mes_qs.filter(sesion__disciplina__organizacion=organizacion)
    asistentes_ids_qs = asistencias_mes_qs.values_list("persona_id", flat=True).distinct()
    estudiantes_activos_mes = asistentes_ids_qs.count()
    estudiantes_qs = Persona.objects.filter(roles__rol__codigo="ESTUDIANTE").distinct()
    if organizacion:
        estudiantes_qs = estudiantes_qs.filter(roles__organizacion=organizacion).distinct()
    filtro_deuda = Q(
        consumos_asistencia__estado=AttendanceConsumption.Estado.DEUDA,
        **filtros_periodo("consumos_asistencia__clase_fecha", request=request),
    )
    if organizacion:
        filtro_deuda &= Q(consumos_asistencia__asistencia__sesion__disciplina__organizacion=organizacion)
    estudiantes_con_deuda = (
        estudiantes_qs.filter(filtro_deuda)
        .annotate(clases_deuda=Count("consumos_asistencia", filter=filtro_deuda, distinct=True))
        .order_by("-clases_deuda", "apellidos", "nombres")
    )
    filtro_asistencia = Q(
        **filtros_periodo("asistencias__sesion__fecha", request=request),
    )
    if organizacion:
        filtro_asistencia &= Q(asistencias__sesion__disciplina__organizacion=organizacion)
    estudiantes_con_mas_asistencia = (
        estudiantes_qs.filter(filtro_asistencia)
        .annotate(total_asistencias_mes=Count("asistencias", filter=filtro_asistencia, distinct=True))
        .order_by("-total_asistencias_mes", "apellidos", "nombres")
    )

    estudiantes_ids = list(estudiantes_qs.values_list("id", flat=True))
    pagos_periodo_qs = Payment.objects.filter(
        persona_id__in=estudiantes_ids,
        **filtros_periodo("fecha_pago", request=request),
    )
    consumos_periodo_qs = AttendanceConsumption.objects.filter(
        persona_id__in=estudiantes_ids,
        estado=AttendanceConsumption.Estado.CONSUMIDO,
        **filtros_periodo("clase_fecha", request=request),
    )
    if organizacion:
        pagos_periodo_qs = pagos_periodo_qs.filter(organizacion=organizacion)
        consumos_periodo_qs = consumos_periodo_qs.filter(asistencia__sesion__disciplina__organizacion=organizacion)

    clases_pagadas_por_persona = {
        item["persona_id"]: item["total_clases"] or 0
        for item in pagos_periodo_qs.values("persona_id").annotate(total_clases=Sum("clases_asignadas"))
    }
    clases_consumidas_por_persona = {
        item["persona_id"]: item["total_consumidas"] or 0
        for item in consumos_periodo_qs.values("persona_id").annotate(total_consumidas=Count("id"))
    }
    personas_por_id = Persona.objects.in_bulk(clases_pagadas_por_persona.keys())
    estudiantes_con_clases_restantes = []
    for persona_id, clases_pagadas in clases_pagadas_por_persona.items():
        clases_consumidas = clases_consumidas_por_persona.get(persona_id, 0)
        saldo_clases = clases_pagadas - clases_consumidas
        if saldo_clases <= 0:
            continue
        persona = personas_por_id.get(persona_id)
        if not persona:
            continue
        estudiantes_con_clases_restantes.append(
            {
                "persona": persona,
                "clases_pagadas": clases_pagadas,
                "clases_consumidas": clases_consumidas,
                "saldo_clases": saldo_clases,
            }
        )
    estudiantes_con_clases_restantes.sort(
        key=lambda item: (-item["saldo_clases"], item["persona"].apellidos, item["persona"].nombres)
    )

    sesiones_resumen = sesiones_mes.annotate(total_asistentes=Count("asistencias")).order_by("-fecha")[:10]
    context.update(
        {
            "sesiones_hoy": sesiones_mes.filter(fecha=timezone.localdate()),
            "asistencias_mes": asistencias_mes_qs.count(),
            "estudiantes_activos_mes": estudiantes_activos_mes,
            "sesiones_realizadas_mes": sesiones_realizadas_mes,
            "estudiantes_con_deuda": estudiantes_con_deuda,
            "estudiantes_con_mas_asistencia": estudiantes_con_mas_asistencia,
            "estudiantes_con_clases_restantes": estudiantes_con_clases_restantes,
            "sesiones_resumen": sesiones_resumen,
            "nombre_mes": descripcion_periodo(request=request, corta=True),
        }
    )
    return render(request, "asistencias/dashboard.html", context)


@role_required(ROLE_ADMIN)
def sesiones_list(request):
    """Vista calendario mensual de sesiones."""
    context = nav_context(request)
    organizacion = organizacion_desde_request(request)
    periodo = resolver_periodo(request)
    year = periodo["referencia_inicio"].year
    month = periodo["referencia_inicio"].month
    sesiones_qs = (
        SesionClase.objects.select_related("disciplina")
        .prefetch_related("profesores")
        .order_by("fecha")
    )
    sesiones_qs = aplicar_periodo(sesiones_qs, "fecha", request=request)
    if organizacion:
        sesiones_qs = sesiones_qs.filter(disciplina__organizacion=organizacion)
    if periodo["mes"] is None or periodo["anio"] is None:
        context.update(
            {
                "mostrar_calendario": False,
                "periodo_descripcion_vista": descripcion_periodo(request=request, corta=False),
                "sesiones_listado": sesiones_qs,
            }
        )
        return render(request, "asistencias/sesiones_list.html", context)

    cal = calendar.Calendar(firstweekday=calendar.MONDAY)
    semanas_raw = cal.monthdatescalendar(year, month)
    inicio_mes = periodo["referencia_inicio"]
    sesiones_qs = (
        sesiones_qs
        .order_by("fecha")
    )
    sesiones_por_fecha = {}
    for sesion in sesiones_qs:
        sesiones_por_fecha.setdefault(sesion.fecha, []).append(
            {
                "sesion": sesion,
                "badge_class": sesion.disciplina.badge_class,
            }
        )
    semanas = []
    for semana in semanas_raw:
        dias = []
        for dia in semana:
            dias.append(
                {
                    "fecha": dia,
                    "en_mes": dia.month == month,
                    "sesiones": sesiones_por_fecha.get(dia, []),
                }
            )
        semanas.append(dias)
    context.update(
        {
            "mostrar_calendario": True,
            "semanas": semanas,
            "mes_actual": inicio_mes,
        }
    )
    return render(request, "asistencias/sesiones_list.html", context)


@role_required(ROLE_ADMIN)
def estudiantes_list(request):
    """Listado de estudiantes con estado de asistencia del período seleccionado."""
    context = nav_context(request)
    estudiantes = (
        Persona.objects.filter(roles__rol__codigo="ESTUDIANTE")
        .distinct()
        .prefetch_related("roles__organizacion", "roles__rol")
    )
    org_id = request.GET.get("organizacion")
    if org_id:
        estudiantes = estudiantes.filter(roles__organizacion_id=org_id).distinct()

    contexto = []
    for persona in estudiantes:
        asistencias_mes_qs = Asistencia.objects.filter(
            persona=persona,
            **filtros_periodo("sesion__fecha", request=request),
        )
        if org_id:
            asistencias_mes_qs = asistencias_mes_qs.filter(sesion__disciplina__organizacion_id=org_id)
        asistencias_mes = asistencias_mes_qs.count()
        ultima_asistencia = (
            Asistencia.objects.filter(persona=persona)
            .select_related("sesion")
            .order_by("-sesion__fecha")
            .first()
        )
        contexto.append(
            {
                "persona": persona,
                "asistencias_mes": asistencias_mes,
                "ultima_asistencia": ultima_asistencia.sesion.fecha if ultima_asistencia else None,
                "activo_mes": asistencias_mes > 0,
            }
        )
    if request.GET.get("sin_asistencia") == "1":
        contexto = [item for item in contexto if not item["activo_mes"]]
    context["estudiantes"] = contexto
    context["filtros"] = {
        "organizacion": org_id,
        "sin_asistencia": request.GET.get("sin_asistencia"),
    }
    return render(request, "asistencias/estudiantes_list.html", context)


@role_required(ROLE_ADMIN)
def profesores_list(request):
    """Listado de profesores agrupado por organización y período seleccionado."""
    context = nav_context(request)
    profesores = Persona.objects.filter(roles__rol__codigo="PROFESOR").distinct()
    org_id = request.GET.get("organizacion")
    organizacion = organizacion_desde_request(request)
    profesores_data = []
    for profesor in profesores:
        organizaciones_prof = profesor.roles.filter(rol__codigo="PROFESOR").select_related("organizacion")
        if org_id:
            organizaciones_prof = organizaciones_prof.filter(organizacion_id=org_id)
        for rol_prof in organizaciones_prof:
            organizacion = rol_prof.organizacion
            asistencias_qs = Asistencia.objects.filter(
                **filtros_periodo("sesion__fecha", request=request),
                sesion__profesores=profesor,
                sesion__disciplina__organizacion=organizacion,
            )
            alumnos_unicos_mes = asistencias_qs.values("persona_id").distinct().count()
            asistencias_mes = asistencias_qs.count()
            sesiones_activas_qs = SesionClase.objects.filter(
                **filtros_periodo("fecha", request=request),
                profesores=profesor,
                disciplina__organizacion=organizacion,
            ).exclude(estado=SesionClase.Estado.CANCELADA)
            if not asistencias_mes and not sesiones_activas_qs.exists():
                continue
            sesiones_mes = sesiones_activas_qs.filter(estado=SesionClase.Estado.COMPLETADA).distinct().count()
            disciplinas_qs = Disciplina.objects.filter(
                sesiones__profesores=profesor,
                organizacion=organizacion,
            ).distinct().order_by("nombre")
            pago_bruto = None
            retencion_sii_monto = None
            pago_neto = None
            if rol_prof.valor_clase is not None:
                pago_bruto = rol_prof.valor_clase * asistencias_mes
                if rol_prof.retencion_sii is not None:
                    retencion_sii_monto = (pago_bruto * rol_prof.retencion_sii) / Decimal("100")
                    pago_neto = pago_bruto - retencion_sii_monto
            profesores_data.append(
                {
                    "persona": profesor,
                    "organizacion": organizacion,
                    "alumnos_unicos_mes": alumnos_unicos_mes,
                    "asistencias_mes": asistencias_mes,
                    "sesiones_mes": sesiones_mes,
                    "disciplinas": disciplinas_qs,
                    "pago_bruto": pago_bruto,
                    "retencion_sii_monto": retencion_sii_monto,
                    "pago_neto": pago_neto,
                }
            )
    profesores_data.sort(key=lambda item: (item["persona"].apellidos or "", item["persona"].nombres or "", item["organizacion"].nombre or ""))
    asistencias_resumen_qs = Asistencia.objects.filter(
        **filtros_periodo("sesion__fecha", request=request),
        sesion__profesores__isnull=False,
    )
    sesiones_realizadas_qs = SesionClase.objects.filter(
        **filtros_periodo("fecha", request=request),
        estado=SesionClase.Estado.COMPLETADA,
        profesores__isnull=False,
    )
    if organizacion:
        asistencias_resumen_qs = asistencias_resumen_qs.filter(sesion__disciplina__organizacion=organizacion)
        sesiones_realizadas_qs = sesiones_realizadas_qs.filter(disciplina__organizacion=organizacion)

    resumen_profesores = {
        "alumnos_unicos": asistencias_resumen_qs.values("persona_id").distinct().count(),
        "sesiones_realizadas": sesiones_realizadas_qs.distinct().count(),
        "asistencias_mes": asistencias_resumen_qs.values("id").distinct().count(),
        "profesores_activos": len({item["persona"].pk for item in profesores_data}),
    }
    context["profesores"] = profesores_data
    context["resumen_profesores"] = resumen_profesores
    return render(request, "asistencias/profesores_list.html", context)


@role_required(ROLE_ADMIN)
def disciplinas_list(request):
    """Resumen de disciplinas con métricas operativas del período."""
    context = nav_context(request)
    organizacion = organizacion_desde_request(request)

    disciplinas_qs = Disciplina.objects.select_related("organizacion")
    if organizacion:
        disciplinas_qs = disciplinas_qs.filter(organizacion=organizacion)

    disciplinas = disciplinas_qs.annotate(
        sesiones_periodo=Count(
            "sesiones",
            filter=Q(**filtros_periodo("sesiones__fecha", request=request)),
            distinct=True,
        ),
        sesiones_realizadas=Count(
            "sesiones",
            filter=Q(
                **filtros_periodo("sesiones__fecha", request=request),
                sesiones__estado=SesionClase.Estado.COMPLETADA,
            ),
            distinct=True,
        ),
        asistencias_periodo=Count(
            "sesiones__asistencias",
            filter=Q(**filtros_periodo("sesiones__fecha", request=request)),
            distinct=True,
        ),
        estudiantes_unicos=Count(
            "sesiones__asistencias__persona",
            filter=Q(**filtros_periodo("sesiones__fecha", request=request)),
            distinct=True,
        ),
    ).order_by("-activa", "organizacion__nombre", "nombre", "nivel")

    context.update(
        {
            "disciplinas": disciplinas,
            "periodo_descripcion_vista": descripcion_periodo(request=request, corta=False),
            "organizacion_seleccionada": organizacion,
        }
    )
    return render(request, "asistencias/disciplinas_list.html", context)


@role_required(ROLE_ADMIN)
def disciplina_detail(request, pk):
    """Detalle de disciplina con métricas de sesiones y asistencias por período."""
    context = nav_context(request)
    disciplina = get_object_or_404(Disciplina.objects.select_related("organizacion"), pk=pk)

    sesiones = (
        SesionClase.objects.filter(
            disciplina=disciplina,
            **filtros_periodo("fecha", request=request),
        )
        .prefetch_related(
            "profesores",
            Prefetch(
                "asistencias",
                queryset=Asistencia.objects.select_related("persona").order_by("persona__apellidos", "persona__nombres"),
            ),
        )
        .annotate(
            total_asistentes=Count("asistencias"),
            presentes=Count("asistencias", filter=Q(asistencias__estado=Asistencia.Estado.PRESENTE)),
            ausentes=Count("asistencias", filter=Q(asistencias__estado=Asistencia.Estado.AUSENTE)),
            justificadas=Count("asistencias", filter=Q(asistencias__estado=Asistencia.Estado.JUSTIFICADA)),
        )
        .order_by("-fecha")
    )

    asistencias_qs = Asistencia.objects.filter(
        sesion__disciplina=disciplina,
        **filtros_periodo("sesion__fecha", request=request),
    )
    resumen = {
        "sesiones_total": sesiones.count(),
        "sesiones_realizadas": sesiones.filter(estado=SesionClase.Estado.COMPLETADA).count(),
        "asistencias_total": asistencias_qs.count(),
        "estudiantes_unicos": asistencias_qs.values("persona_id").distinct().count(),
    }
    profesores_periodo = Persona.objects.filter(
        sesiones_en_equipo__disciplina=disciplina,
        **filtros_periodo("sesiones_en_equipo__fecha", request=request),
    ).distinct().order_by("apellidos", "nombres")

    context.update(
        {
            "disciplina": disciplina,
            "sesiones": sesiones,
            "resumen": resumen,
            "profesores_periodo": profesores_periodo,
            "periodo_descripcion_vista": descripcion_periodo(request=request, corta=False),
        }
    )
    return render(request, "asistencias/disciplina_detail.html", context)


@role_required(ROLE_ADMIN)
def disciplina_create(request):
    """Crea una disciplina."""
    context = nav_context(request)
    initial = {}
    if request.GET.get("organizacion"):
        initial["organizacion"] = request.GET.get("organizacion")

    form = DisciplinaForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        disciplina = form.save()
        messages.success(request, "Disciplina creada correctamente.")
        return redirect(_url_con_filtros(request, "asistencias:disciplina_detail", pk=disciplina.pk))

    context.update(
        {
            "form": form,
            "modo_formulario": "crear",
            "badge_color_options": Disciplina.badge_color_options(),
        }
    )
    return render(request, "asistencias/disciplina_form.html", context)


@role_required(ROLE_ADMIN)
def disciplina_edit(request, pk):
    """Edita una disciplina existente."""
    context = nav_context(request)
    disciplina = get_object_or_404(Disciplina, pk=pk)
    form = DisciplinaForm(request.POST or None, instance=disciplina)

    if request.method == "POST" and form.is_valid():
        disciplina = form.save()
        messages.success(request, "Disciplina actualizada correctamente.")
        return redirect(_url_con_filtros(request, "asistencias:disciplina_detail", pk=disciplina.pk))

    context.update(
        {
            "form": form,
            "disciplina": disciplina,
            "modo_formulario": "editar",
            "badge_color_options": Disciplina.badge_color_options(),
        }
    )
    return render(request, "asistencias/disciplina_form.html", context)

@role_required(ROLE_ADMIN)
def asistencias_list(request):
    """Pantalla operativa para crear sesiones y registrar asistencias en bloque."""
    context = nav_context(request)
    sesion_id = request.GET.get("sesion_id")
    organizacion = organizacion_desde_request(request)
    sesion_seleccionada = SesionClase.objects.filter(pk=sesion_id).first() if sesion_id else None
    asistentes_ids = set()
    if sesion_seleccionada:
        asistentes_ids = set(
            Asistencia.objects.filter(sesion=sesion_seleccionada).values_list("persona_id", flat=True)
        )
    sesion_form = SesionBasicaForm(initial={"fecha": timezone.localdate()}, organizacion=organizacion)
    asistencia_form = AsistenciaMasivaForm(initial={"sesion_id": sesion_id} if sesion_id else None)
    persona_form = PersonaRapidaForm()
    open_nueva_sesion = request.GET.get("open") == "nueva_sesion"
    open_nueva_persona = False
    open_agregar_asistentes = request.GET.get("open") == "agregar_asistentes"
    estudiantes_qs = Persona.objects.filter(roles__rol__codigo="ESTUDIANTE").distinct().order_by("apellidos", "nombres")
    asistencia_form.fields["estudiantes"].queryset = estudiantes_qs

    if request.method == "POST":
        if "crear_sesion" in request.POST:
            sesion_form = SesionBasicaForm(request.POST, organizacion=organizacion)
            if sesion_form.is_valid():
                disciplina = sesion_form.cleaned_data["disciplina"]
                fecha = sesion_form.cleaned_data["fecha"] or timezone.localdate()
                profesores = list(sesion_form.cleaned_data["profesores"])
                notas = f"{disciplina.nombre} - {fecha}"
                sesion = SesionClase.objects.create(
                    disciplina=disciplina,
                    fecha=fecha,
                    notas=notas,
                )
                if profesores:
                    sesion.profesores.set(profesores)
                messages.success(request, "Sesión creada. Ahora puedes agregar asistentes.")
                return redirect(_url_actual_con_filtros(request, sesion_id=sesion.pk, open="agregar_asistentes"))
            open_nueva_sesion = True
        elif "cambiar_estado" in request.POST:
            sesion_id_post = request.POST.get("sesion_id")
            estado = request.POST.get("estado")
            if sesion_id_post and estado in dict(SesionClase.Estado.choices):
                sesion = get_object_or_404(SesionClase, pk=sesion_id_post)
                sesion.estado = estado
                sesion.save(update_fields=["estado"])
                messages.success(request, "Estado de la sesión actualizado.")
                return redirect(request.get_full_path())
        elif "agregar_persona" in request.POST:
            persona_form = PersonaRapidaForm(request.POST)
            open_nueva_persona = True
            if persona_form.is_valid():
                persona = _crear_persona_estudiante_en_organizacion(persona_form, organizacion)
                if persona:
                    messages.success(request, "Persona creada y asignada como estudiante.")
                    open_nueva_persona = False
                    return redirect(_url_actual_con_filtros(request))
        elif "agregar_asistentes" in request.POST:
            asistencia_form = AsistenciaMasivaForm(request.POST)
            asistencia_form.fields["estudiantes"].queryset = estudiantes_qs
            if asistencia_form.is_valid():
                sesion = get_object_or_404(SesionClase, pk=asistencia_form.cleaned_data["sesion_id"])
                estudiantes = list(asistencia_form.cleaned_data["estudiantes"])
                creados = 0
                for persona in estudiantes:
                    _, created = Asistencia.objects.get_or_create(
                        sesion=sesion,
                        persona=persona,
                        defaults={"estado": Asistencia.Estado.PRESENTE},
                    )
                    if created:
                        creados += 1
                if estudiantes and sesion.estado == SesionClase.Estado.PROGRAMADA:
                    sesion.estado = SesionClase.Estado.COMPLETADA
                    sesion.save(update_fields=["estado"])
                messages.success(request, f"Asistencias agregadas: {creados}.")
                accion_guardado = request.POST.get("accion_guardado_asistencias", "cerrar")
                if accion_guardado == "continuar":
                    return redirect(
                        _url_actual_con_filtros(
                            request,
                            sesion_id=sesion.pk,
                            open="agregar_asistentes",
                        )
                    )
                return redirect(
                    _url_actual_con_filtros(
                        request,
                        remove_params=["open"],
                        sesion_id=sesion.pk,
                    )
                )
            open_agregar_asistentes = True

    estudiantes_total_disciplina_periodo = 0
    if sesion_seleccionada:
        estudiantes_disciplina_qs = Persona.objects.filter(
            roles__rol__codigo="ESTUDIANTE",
            asistencias__sesion__disciplina=sesion_seleccionada.disciplina,
            **filtros_periodo("asistencias__sesion__fecha", request=request),
        )
        if organizacion:
            estudiantes_disciplina_qs = estudiantes_disciplina_qs.filter(
                asistencias__sesion__disciplina__organizacion=organizacion
            )
        estudiantes_total_disciplina_periodo = estudiantes_disciplina_qs.distinct().count()
    sesiones_qs = (
        SesionClase.objects.select_related("disciplina")
        .prefetch_related(
            "profesores",
            Prefetch(
                "asistencias",
                queryset=Asistencia.objects.select_related("persona", "consumo_financiero__pago").order_by("-registrada_en"),
            ),
        )
        .filter(**filtros_periodo("fecha", request=request))
        .order_by("-fecha")
    )
    if organizacion:
        sesiones_qs = sesiones_qs.filter(disciplina__organizacion=organizacion)
    sesiones_list = []
    for sesion in sesiones_qs:
        asistentes = []
        for asistencia in sesion.asistencias.all():
            consumo = getattr(asistencia, "consumo_financiero", None)
            if consumo and consumo.estado == AttendanceConsumption.Estado.DEUDA:
                asistencia.badge_finanzas_class = "text-bg-warning"
                asistencia.badge_finanzas_label = "Deuda"
            elif consumo and consumo.estado == AttendanceConsumption.Estado.CONSUMIDO and consumo.pago_id:
                asistencia.badge_finanzas_class = "text-bg-success"
                asistencia.badge_finanzas_label = "Pagada"
            else:
                asistencia.badge_finanzas_class = "text-bg-primary"
                asistencia.badge_finanzas_label = "Liberada"
            asistentes.append(asistencia)
        sesiones_list.append(
            {
                "sesion": sesion,
                "total_asistentes": sesion.asistencias.count(),
                "asistentes": asistentes,
            }
        )

    context.update(
        {
            "sesion_form": sesion_form,
            "asistencia_form": asistencia_form,
            "persona_form": persona_form,
            "open_nueva_sesion": open_nueva_sesion,
            "open_nueva_persona": open_nueva_persona,
            "open_agregar_asistentes": open_agregar_asistentes,
            "sesiones": sesiones_list,
            "sesion_seleccionada": sesion_seleccionada,
            "asistentes_ids": asistentes_ids,
            "estudiantes": estudiantes_qs,
            "estudiantes_total": estudiantes_qs.count(),
            "estudiantes_total_disciplina_periodo": estudiantes_total_disciplina_periodo,
            "disciplinas": disciplinas_vigentes_qs(organizacion=organizacion),
            "profesores": profesores_vigentes_qs(organizacion=organizacion),
            "organizaciones": Organizacion.objects.all(),
        }
    )
    return render(request, "asistencias/asistencias_list.html", context)


@role_required(ROLE_ADMIN)
def sesion_detail(request, pk):
    """Detalle de la sesión y estado de sus asistentes."""
    context = nav_context(request)
    context["hide_periodo"] = True
    sesion = get_object_or_404(
        SesionClase.objects.select_related("disciplina", "disciplina__organizacion").prefetch_related("profesores", "asistencias__persona"),
        pk=pk,
    )
    estudiantes_qs = (
        Persona.objects.filter(
            roles__rol__codigo="ESTUDIANTE",
            roles__organizacion=sesion.disciplina.organizacion,
        )
        .distinct()
        .order_by("apellidos", "nombres")
    )
    persona_form = PersonaRapidaForm()
    open_nueva_persona = False
    if request.method == "POST":
        if "eliminar_sesion" in request.POST:
            sesion_resumen = str(sesion)
            sesion.delete()
            messages.success(request, f"Sesión eliminada: {sesion_resumen}.")
            return redirect(_url_con_filtros(request, "asistencias:sesiones_list"))
        elif "crear_persona_estudiante" in request.POST:
            persona_form = PersonaRapidaForm(request.POST)
            open_nueva_persona = True
            if persona_form.is_valid():
                persona = _crear_persona_estudiante_en_organizacion(
                    persona_form,
                    sesion.disciplina.organizacion,
                )
                if persona:
                    messages.success(request, "Persona creada y asignada como estudiante de la sesión.")
                    return redirect(_url_con_filtros(request, "asistencias:sesion_detail", pk=sesion.pk))
        elif "eliminar_asistente" in request.POST:
            asistencia = get_object_or_404(Asistencia, pk=request.POST.get("asistencia_id"), sesion=sesion)
            persona_nombre = str(asistencia.persona)
            asistencia.delete()
            messages.success(request, f"Asistente eliminado de la sesión: {persona_nombre}.")
            return redirect(_url_con_filtros(request, "asistencias:sesion_detail", pk=sesion.pk))
        elif "cambiar_estado" in request.POST:
            estado = request.POST.get("estado")
            if estado in dict(SesionClase.Estado.choices):
                sesion.estado = estado
                sesion.save(update_fields=["estado"])
                messages.success(request, "Estado de la sesión actualizado.")
                return redirect(_url_con_filtros(request, "asistencias:sesion_detail", pk=sesion.pk))
        elif "agregar_asistentes" in request.POST:
            estudiantes_ids = request.POST.getlist("estudiantes")
            estudiantes = list(estudiantes_qs.filter(pk__in=estudiantes_ids))
            creados = 0
            for persona in estudiantes:
                _, created = Asistencia.objects.get_or_create(
                    sesion=sesion,
                    persona=persona,
                    defaults={"estado": Asistencia.Estado.PRESENTE},
                )
                if created:
                    creados += 1
            if estudiantes and sesion.estado == SesionClase.Estado.PROGRAMADA:
                sesion.estado = SesionClase.Estado.COMPLETADA
                sesion.save(update_fields=["estado"])
            messages.success(request, f"Asistencias agregadas: {creados}.")
            return redirect(_url_con_filtros(request, "asistencias:sesion_detail", pk=sesion.pk))

    asistencias = sesion.asistencias.select_related("persona", "consumo_financiero__pago").order_by("-registrada_en")
    for asistencia in asistencias:
        consumo = getattr(asistencia, "consumo_financiero", None)
        if consumo and consumo.estado == AttendanceConsumption.Estado.CONSUMIDO:
            asistencia.estado_financiero_label = "Pagada"
            asistencia.estado_financiero_clase = "success"
        elif consumo and consumo.estado == AttendanceConsumption.Estado.DEUDA:
            asistencia.estado_financiero_label = "Deuda"
            asistencia.estado_financiero_clase = "danger"
        elif consumo and consumo.estado == AttendanceConsumption.Estado.PENDIENTE:
            asistencia.estado_financiero_label = "Sin cobro"
            asistencia.estado_financiero_clase = "secondary"
        else:
            asistencia.estado_financiero_label = "Sin consumo"
            asistencia.estado_financiero_clase = "light"
    asistentes_ids = set(asistencias.values_list("persona_id", flat=True))
    context.update(
        {
            "sesion": sesion,
            "asistencias": asistencias,
            "total_asistentes": asistencias.count(),
            "estudiantes": estudiantes_qs,
            "asistentes_ids": asistentes_ids,
            "persona_form": persona_form,
            "open_nueva_persona": open_nueva_persona,
            "back_url": request.META.get("HTTP_REFERER") or _url_con_filtros(request, "asistencias:sesiones_list"),
        }
    )
    return render(request, "asistencias/sesion_detail.html", context)


@role_required(ROLE_ADMIN)
def sesion_edit(request, pk):
    """Edita una sesión existente."""
    context = nav_context(request)
    sesion = get_object_or_404(
        SesionClase.objects.select_related("disciplina", "disciplina__organizacion").prefetch_related("profesores"),
        pk=pk,
    )
    form = SesionBasicaForm(
        request.POST or None,
        organizacion=sesion.disciplina.organizacion,
        initial={
            "disciplina": sesion.disciplina,
            "fecha": sesion.fecha,
            "profesores": sesion.profesores.all(),
        },
    )

    if request.method == "POST" and form.is_valid():
        sesion.disciplina = form.cleaned_data["disciplina"]
        sesion.fecha = form.cleaned_data["fecha"] or sesion.fecha
        sesion.save(update_fields=["disciplina", "fecha"])
        sesion.profesores.set(form.cleaned_data["profesores"])
        messages.success(request, "Sesión actualizada correctamente.")
        return redirect(_url_con_filtros(request, "asistencias:sesion_detail", pk=sesion.pk))

    context.update(
        {
            "form": form,
            "sesion": sesion,
            "back_url": request.META.get("HTTP_REFERER") or _url_con_filtros(request, "asistencias:sesion_detail", pk=sesion.pk),
        }
    )
    return render(request, "asistencias/sesion_form.html", context)

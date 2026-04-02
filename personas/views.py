from decimal import Decimal

from django.contrib import messages
from django.db.models import Count, DateField, DecimalField, IntegerField, OuterRef, Prefetch, Q, Subquery, Sum, Value
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from asistencias.decorators import role_required
from asistencias.models import Asistencia, Disciplina, SesionClase
from asistencias.utils import ROLE_ADMIN
from asistencias.views import _nav_context, _organizacion_desde_request, _periodo
from finanzas.models import AttendanceConsumption, Payment
from finanzas.services import resumen_financiero_estudiante

from .forms import OrganizacionCRMForm, PersonaCRMForm, PersonaRolCRMForm
from .models import Organizacion, Persona, PersonaRol, Rol


MONEY_FIELD = DecimalField(max_digits=12, decimal_places=2)


def _base_context(request):
    return _nav_context(request)


def _url_con_filtros(request, nombre_url, **kwargs):
    url = reverse(nombre_url, kwargs=kwargs or None)
    query = request.GET.urlencode()
    return f"{url}?{query}" if query else url


def _personas_queryset(organizacion=None):
    queryset = Persona.objects.select_related("user").prefetch_related(
        Prefetch(
            "roles",
            queryset=PersonaRol.objects.filter(activo=True)
            .select_related("rol", "organizacion")
            .order_by("organizacion__nombre", "rol__nombre"),
        )
    )
    if organizacion:
        queryset = queryset.filter(
            Q(roles__organizacion=organizacion)
            | Q(asistencias__sesion__disciplina__organizacion=organizacion)
            | Q(sesiones_en_equipo__disciplina__organizacion=organizacion)
            | Q(pagos_financieros__organizacion=organizacion)
        ).distinct()
    return queryset


def _organizacion_metricas(organizacion, inicio_periodo, fin_periodo):
    roles_qs = PersonaRol.objects.filter(organizacion=organizacion, activo=True)
    sesiones_qs = SesionClase.objects.filter(
        disciplina__organizacion=organizacion,
        fecha__gte=inicio_periodo,
        fecha__lte=fin_periodo,
    )
    pagos_qs = Payment.objects.filter(
        organizacion=organizacion,
        fecha_pago__gte=inicio_periodo,
        fecha_pago__lte=fin_periodo,
    )
    asistencias_qs = Asistencia.objects.filter(
        sesion__disciplina__organizacion=organizacion,
        sesion__fecha__gte=inicio_periodo,
        sesion__fecha__lte=fin_periodo,
    )
    return {
        "personas_activas": roles_qs.values("persona_id").distinct().count(),
        "estudiantes_activos": roles_qs.filter(rol__codigo="ESTUDIANTE").values("persona_id").distinct().count(),
        "profesores_activos": roles_qs.filter(rol__codigo="PROFESOR").values("persona_id").distinct().count(),
        "disciplinas_total": Disciplina.objects.filter(organizacion=organizacion).count(),
        "disciplinas_activas": Disciplina.objects.filter(organizacion=organizacion, activa=True).count(),
        "sesiones_periodo": sesiones_qs.count(),
        "sesiones_completadas_periodo": sesiones_qs.filter(estado=SesionClase.Estado.COMPLETADA).count(),
        "asistencias_periodo": asistencias_qs.count(),
        "pagos_periodo": pagos_qs.count(),
        "ingresos_periodo": pagos_qs.aggregate(total=Sum("monto_total")).get("total") or 0,
    }


def _annotate_personas_resumen(queryset, inicio_periodo, fin_periodo, organizacion=None):
    asistencias_qs = Asistencia.objects.filter(
        persona=OuterRef("pk"),
        sesion__fecha__gte=inicio_periodo,
        sesion__fecha__lte=fin_periodo,
    )
    pagos_qs = Payment.objects.filter(
        persona=OuterRef("pk"),
        fecha_pago__gte=inicio_periodo,
        fecha_pago__lte=fin_periodo,
    )
    consumos_qs = AttendanceConsumption.objects.filter(
        persona=OuterRef("pk"),
        clase_fecha__gte=inicio_periodo,
        clase_fecha__lte=fin_periodo,
    )
    sesiones_profesor_qs = SesionClase.objects.filter(
        profesores=OuterRef("pk"),
        fecha__gte=inicio_periodo,
        fecha__lte=fin_periodo,
    )
    if organizacion:
        asistencias_qs = asistencias_qs.filter(sesion__disciplina__organizacion=organizacion)
        pagos_qs = pagos_qs.filter(organizacion=organizacion)
        consumos_qs = consumos_qs.filter(asistencia__sesion__disciplina__organizacion=organizacion)
        sesiones_profesor_qs = sesiones_profesor_qs.filter(disciplina__organizacion=organizacion)

    asistencias_total_sq = asistencias_qs.order_by().values("persona").annotate(total=Count("id")).values("total")[:1]
    pagos_total_sq = pagos_qs.order_by().values("persona").annotate(total=Count("id")).values("total")[:1]
    monto_pagado_sq = pagos_qs.order_by().values("persona").annotate(total=Sum("monto_total")).values("total")[:1]
    deuda_total_sq = (
        consumos_qs.filter(estado=AttendanceConsumption.Estado.DEUDA)
        .order_by()
        .values("persona")
        .annotate(total=Count("id"))
        .values("total")[:1]
    )
    ultima_asistencia_sq = asistencias_qs.order_by("-sesion__fecha").values("sesion__fecha")[:1]
    ultimo_pago_sq = pagos_qs.order_by("-fecha_pago").values("fecha_pago")[:1]
    sesiones_profesor_total_sq = (
        sesiones_profesor_qs.order_by()
        .values("profesores")
        .annotate(total=Count("id", distinct=True))
        .values("total")[:1]
    )
    return queryset.annotate(
        roles_activos_total=Count("roles", filter=Q(roles__activo=True), distinct=True),
        organizaciones_total=Count("roles__organizacion", filter=Q(roles__activo=True), distinct=True),
        asistencias_periodo=Coalesce(Subquery(asistencias_total_sq, output_field=IntegerField()), Value(0)),
        pagos_periodo=Coalesce(Subquery(pagos_total_sq, output_field=IntegerField()), Value(0)),
        monto_pagado_periodo=Coalesce(Subquery(monto_pagado_sq, output_field=MONEY_FIELD), Value(Decimal("0")), output_field=MONEY_FIELD),
        deuda_periodo=Coalesce(Subquery(deuda_total_sq, output_field=IntegerField()), Value(0)),
        sesiones_profesor_periodo=Coalesce(Subquery(sesiones_profesor_total_sq, output_field=IntegerField()), Value(0)),
        ultima_asistencia=Subquery(ultima_asistencia_sq, output_field=DateField()),
        ultimo_pago=Subquery(ultimo_pago_sq, output_field=DateField()),
    )


@role_required(ROLE_ADMIN)
def dashboard(request):
    context = _base_context(request)
    inicio_periodo, fin_periodo = _periodo(request)
    organizacion = _organizacion_desde_request(request)

    personas_qs = _annotate_personas_resumen(
        _personas_queryset(organizacion),
        inicio_periodo,
        fin_periodo,
        organizacion,
    )
    pagos_qs = Payment.objects.filter(fecha_pago__gte=inicio_periodo, fecha_pago__lte=fin_periodo)
    consumos_qs = AttendanceConsumption.objects.filter(clase_fecha__gte=inicio_periodo, clase_fecha__lte=fin_periodo)
    asistencias_qs = Asistencia.objects.filter(sesion__fecha__gte=inicio_periodo, sesion__fecha__lte=fin_periodo)
    if organizacion:
        pagos_qs = pagos_qs.filter(organizacion=organizacion)
        consumos_qs = consumos_qs.filter(asistencia__sesion__disciplina__organizacion=organizacion)
        asistencias_qs = asistencias_qs.filter(sesion__disciplina__organizacion=organizacion)

    context.update(
        {
            "total_personas": personas_qs.count(),
            "personas_activas": personas_qs.filter(activo=True).count(),
            "personas_con_usuario": personas_qs.filter(user__isnull=False).count(),
            "estudiantes_total": personas_qs.filter(roles__activo=True, roles__rol__codigo="ESTUDIANTE").distinct().count(),
            "profesores_total": personas_qs.filter(roles__activo=True, roles__rol__codigo="PROFESOR").distinct().count(),
            "personas_con_deuda_total": personas_qs.filter(deuda_periodo__gt=0).count(),
            "personas_con_asistencia": asistencias_qs.values("persona_id").distinct().count(),
            "pagos_registrados": pagos_qs.count(),
            "monto_pagado_total": pagos_qs.aggregate(total=Sum("monto_total")).get("total") or 0,
            "deuda_total_clases": consumos_qs.filter(estado=AttendanceConsumption.Estado.DEUDA).count(),
            "personas_con_deuda": personas_qs.filter(deuda_periodo__gt=0).order_by("-deuda_periodo", "apellidos", "nombres")[:8],
            "personas_sin_contacto": personas_qs.filter(
                Q(email__isnull=True) | Q(email=""),
                Q(telefono=""),
            ).order_by("apellidos", "nombres")[:8],
            "personas_nuevas": personas_qs.order_by("-creado_en")[:8],
            "pagos_recientes": pagos_qs.select_related("persona", "organizacion").order_by("-fecha_pago", "-id")[:8],
        }
    )
    return render(request, "personas/dashboard.html", context)


@role_required(ROLE_ADMIN)
def organizaciones_list(request):
    context = _base_context(request)
    inicio_periodo, fin_periodo = _periodo(request)
    organizacion_filtro = _organizacion_desde_request(request)
    organizaciones_qs = Organizacion.objects.order_by("nombre")
    if organizacion_filtro:
        organizaciones_qs = organizaciones_qs.filter(pk=organizacion_filtro.pk)

    organizaciones = []
    for organizacion in organizaciones_qs:
        organizaciones.append(
            {
                "organizacion": organizacion,
                "metricas": _organizacion_metricas(organizacion, inicio_periodo, fin_periodo),
            }
        )

    context.update(
        {
            "organizaciones": organizaciones,
            "inicio_periodo": inicio_periodo,
            "fin_periodo": fin_periodo,
        }
    )
    return render(request, "personas/organizaciones_list.html", context)


@role_required(ROLE_ADMIN)
def organizacion_detail(request, pk):
    context = _base_context(request)
    inicio_periodo, fin_periodo = _periodo(request)
    organizacion = get_object_or_404(Organizacion, pk=pk)
    disciplinas = Disciplina.objects.filter(organizacion=organizacion).order_by("nombre")
    metricas = _organizacion_metricas(organizacion, inicio_periodo, fin_periodo)
    context.update(
        {
            "organizacion_obj": organizacion,
            "metricas": metricas,
            "disciplinas": disciplinas[:8],
            "pagos_recientes": Payment.objects.filter(organizacion=organizacion).select_related("persona").order_by("-fecha_pago", "-id")[:8],
            "inicio_periodo": inicio_periodo,
            "fin_periodo": fin_periodo,
        }
    )
    return render(request, "personas/organizacion_detail.html", context)


@role_required(ROLE_ADMIN)
def organizacion_create(request):
    context = _base_context(request)
    form = OrganizacionCRMForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        organizacion = form.save()
        messages.success(request, "Organizacion creada correctamente.")
        return redirect(_url_con_filtros(request, "personas:organizacion_detail", pk=organizacion.pk))
    context.update({"form": form, "title": "Nueva organizacion"})
    return render(request, "personas/organizacion_form.html", context)


@role_required(ROLE_ADMIN)
def organizacion_edit(request, pk):
    context = _base_context(request)
    organizacion = get_object_or_404(Organizacion, pk=pk)
    form = OrganizacionCRMForm(request.POST or None, instance=organizacion)
    if request.method == "POST" and form.is_valid():
        organizacion = form.save()
        messages.success(request, "Organizacion actualizada correctamente.")
        return redirect(_url_con_filtros(request, "personas:organizacion_detail", pk=organizacion.pk))
    context.update({"form": form, "title": "Editar organizacion", "organizacion_obj": organizacion})
    return render(request, "personas/organizacion_form.html", context)


@role_required(ROLE_ADMIN)
def personas_list(request):
    context = _base_context(request)
    inicio_periodo, fin_periodo = _periodo(request)
    organizacion = _organizacion_desde_request(request)
    personas_qs = _annotate_personas_resumen(
        _personas_queryset(organizacion),
        inicio_periodo,
        fin_periodo,
        organizacion,
    )

    q = (request.GET.get("q") or "").strip()
    rol = (request.GET.get("rol") or "").strip()
    estado = (request.GET.get("estado") or "").strip()
    con_usuario = (request.GET.get("con_usuario") or "").strip()
    con_deuda = (request.GET.get("con_deuda") or "").strip()

    if q:
        personas_qs = personas_qs.filter(
            Q(nombres__icontains=q)
            | Q(apellidos__icontains=q)
            | Q(email__icontains=q)
            | Q(telefono__icontains=q)
            | Q(identificador__icontains=q)
        )
    if rol:
        personas_qs = personas_qs.filter(roles__activo=True, roles__rol__codigo=rol)
    if estado == "activas":
        personas_qs = personas_qs.filter(activo=True)
    elif estado == "inactivas":
        personas_qs = personas_qs.filter(activo=False)
    if con_usuario == "si":
        personas_qs = personas_qs.filter(user__isnull=False)
    elif con_usuario == "no":
        personas_qs = personas_qs.filter(user__isnull=True)
    if con_deuda == "si":
        personas_qs = personas_qs.filter(deuda_periodo__gt=0)
    elif con_deuda == "no":
        personas_qs = personas_qs.filter(deuda_periodo=0)

    context.update(
        {
            "personas": personas_qs.order_by("apellidos", "nombres"),
            "roles_disponibles": Rol.objects.order_by("nombre"),
            "q": q,
            "rol": rol,
            "estado": estado,
            "con_usuario": con_usuario,
            "con_deuda": con_deuda,
        }
    )
    return render(request, "personas/personas_list.html", context)


@role_required(ROLE_ADMIN)
def persona_create(request):
    context = _base_context(request)
    form = PersonaCRMForm(request.POST or None)
    rol_form = PersonaRolCRMForm(request.POST or None, prefix="rol")
    if request.method == "POST":
        persona_valida = form.is_valid()
        rol_valido = rol_form.is_valid()
        if persona_valida and rol_valido:
            persona = form.save()
            if rol_valido and rol_form.cleaned_data.get("rol") and rol_form.cleaned_data.get("organizacion"):
                rol = rol_form.cleaned_data["rol"]
                organizacion = rol_form.cleaned_data["organizacion"]
                persona_rol, _ = PersonaRol.objects.get_or_create(
                    persona=persona,
                    rol=rol,
                    organizacion=organizacion,
                    defaults={"activo": True},
                )
                if not persona_rol.activo:
                    persona_rol.activo = True
                    persona_rol.save(update_fields=["activo"])
            messages.success(request, "Persona creada correctamente.")
            return redirect(_url_con_filtros(request, "personas:persona_detail", pk=persona.pk))
    context.update(
        {
            "form": form,
            "rol_form": rol_form,
        }
    )
    return render(request, "personas/persona_create.html", context)


@role_required(ROLE_ADMIN)
def persona_detail(request, pk):
    context = _base_context(request)
    inicio_periodo, fin_periodo = _periodo(request)
    organizacion = _organizacion_desde_request(request)
    persona = get_object_or_404(
        Persona.objects.select_related("user").prefetch_related(
            Prefetch(
                "roles",
                queryset=PersonaRol.objects.select_related("rol", "organizacion").order_by("organizacion__nombre", "rol__nombre"),
            ),
            Prefetch(
                "asistencias",
                queryset=Asistencia.objects.select_related("sesion__disciplina__organizacion").order_by("-sesion__fecha"),
            ),
            Prefetch(
                "pagos_financieros",
                queryset=Payment.objects.select_related("organizacion", "plan", "documento_tributario").order_by("-fecha_pago", "-id"),
            ),
            Prefetch(
                "consumos_asistencia",
                queryset=AttendanceConsumption.objects.select_related(
                    "asistencia__sesion__disciplina__organizacion",
                    "pago",
                ).order_by("-clase_fecha", "-id"),
            ),
        ),
        pk=pk,
    )
    if request.method == "POST":
        accion = request.POST.get("accion")
        if accion == "agregar_rol":
            rol_form_post = PersonaRolCRMForm(request.POST, prefix="rol")
            if rol_form_post.is_valid() and rol_form_post.cleaned_data.get("rol") and rol_form_post.cleaned_data.get("organizacion"):
                rol = rol_form_post.cleaned_data["rol"]
                organizacion_rol = rol_form_post.cleaned_data["organizacion"]
                persona_rol, created = PersonaRol.objects.get_or_create(
                    persona=persona,
                    rol=rol,
                    organizacion=organizacion_rol,
                    defaults={"activo": True},
                )
                if not created and not persona_rol.activo:
                    persona_rol.activo = True
                    persona_rol.save(update_fields=["activo"])
                    messages.success(request, "Rol reactivado para la persona.")
                elif created:
                    messages.success(request, "Rol agregado a la persona.")
                else:
                    messages.info(request, "Ese rol ya estaba activo para la persona.")
                return redirect(_url_con_filtros(request, "personas:persona_detail", pk=persona.pk))
            elif rol_form_post.is_valid():
                messages.warning(request, "Debes seleccionar un rol y una organizacion para agregar la asignacion.")
            else:
                messages.error(request, "No se pudo agregar el rol. Revisa rol y organizacion.")
        elif accion == "toggle_rol":
            persona_rol = get_object_or_404(PersonaRol, pk=request.POST.get("persona_rol_id"), persona=persona)
            persona_rol.activo = not persona_rol.activo
            persona_rol.save(update_fields=["activo"])
            messages.success(request, "Estado del rol actualizado.")
            return redirect(_url_con_filtros(request, "personas:persona_detail", pk=persona.pk))
    roles_asignados = list(persona.roles.all())
    asistencias = persona.asistencias.all()
    pagos = persona.pagos_financieros.all()
    consumos = persona.consumos_asistencia.all()
    sesiones_profesor = (
        SesionClase.objects.filter(
            profesores=persona,
            fecha__gte=inicio_periodo,
            fecha__lte=fin_periodo,
        )
        .select_related("disciplina__organizacion")
        .prefetch_related("profesores")
        .order_by("-fecha")
    )
    if organizacion:
        asistencias = asistencias.filter(sesion__disciplina__organizacion=organizacion)
        pagos = pagos.filter(organizacion=organizacion)
        consumos = consumos.filter(asistencia__sesion__disciplina__organizacion=organizacion)
        sesiones_profesor = sesiones_profesor.filter(disciplina__organizacion=organizacion)
    asistencias = asistencias.filter(sesion__fecha__gte=inicio_periodo, sesion__fecha__lte=fin_periodo)
    pagos = pagos.filter(fecha_pago__gte=inicio_periodo, fecha_pago__lte=fin_periodo)
    consumos = consumos.filter(clase_fecha__gte=inicio_periodo, clase_fecha__lte=fin_periodo)

    roles_codigos = {item.rol.codigo for item in roles_asignados if item.activo}
    finanzas_resumen = resumen_financiero_estudiante(persona, organizacion) if "ESTUDIANTE" in roles_codigos else None

    context.update(
        {
            "persona_obj": persona,
            "roles_asignados": roles_asignados,
            "rol_form": PersonaRolCRMForm(prefix="rol"),
            "asistencias": asistencias,
            "pagos": pagos,
            "consumos": consumos,
            "sesiones_profesor": sesiones_profesor,
            "documentos_tributarios": [pago.documento_tributario for pago in pagos if pago.documento_tributario_id],
            "finanzas_resumen": finanzas_resumen,
            "monto_pagado": pagos.aggregate(total=Sum("monto_total")).get("total") or 0,
            "consumos_consumidos": consumos.filter(estado=AttendanceConsumption.Estado.CONSUMIDO).count(),
            "consumos_pendientes": consumos.filter(estado=AttendanceConsumption.Estado.PENDIENTE).count(),
            "consumos_deuda": consumos.filter(estado=AttendanceConsumption.Estado.DEUDA).count(),
            "roles_codigos": roles_codigos,
        }
    )
    return render(request, "personas/persona_detail.html", context)


@role_required(ROLE_ADMIN)
def persona_edit(request, pk):
    context = _base_context(request)
    persona = get_object_or_404(
        Persona.objects.select_related("user").prefetch_related(
            Prefetch(
                "roles",
                queryset=PersonaRol.objects.select_related("rol", "organizacion").order_by("organizacion__nombre", "rol__nombre"),
            )
        ),
        pk=pk,
    )
    form = PersonaCRMForm(request.POST or None, instance=persona)
    rol_form = PersonaRolCRMForm(prefix="rol")

    if request.method == "POST":
        accion = request.POST.get("accion")
        if accion == "guardar_persona":
            form = PersonaCRMForm(request.POST, instance=persona)
            if form.is_valid():
                form.save()
                messages.success(request, "Perfil de persona actualizado.")
                return redirect(_url_con_filtros(request, "personas:persona_edit", pk=persona.pk))
        elif accion == "agregar_rol":
            rol_form = PersonaRolCRMForm(request.POST, prefix="rol")
            if rol_form.is_valid() and rol_form.cleaned_data.get("rol") and rol_form.cleaned_data.get("organizacion"):
                rol = rol_form.cleaned_data["rol"]
                organizacion = rol_form.cleaned_data["organizacion"]
                persona_rol, created = PersonaRol.objects.get_or_create(
                    persona=persona,
                    rol=rol,
                    organizacion=organizacion,
                    defaults={"activo": True},
                )
                if not created and not persona_rol.activo:
                    persona_rol.activo = True
                    persona_rol.save(update_fields=["activo"])
                    messages.success(request, "Rol reactivado para la persona.")
                elif created:
                    messages.success(request, "Rol agregado a la persona.")
                else:
                    messages.info(request, "Ese rol ya estaba activo para la persona.")
                return redirect(_url_con_filtros(request, "personas:persona_edit", pk=persona.pk))
            elif rol_form.is_valid():
                messages.warning(request, "Debes seleccionar un rol y una organizacion para agregar la asignacion.")
            else:
                messages.error(request, "No se pudo agregar el rol. Revisa rol y organizacion.")
        elif accion == "toggle_rol":
            persona_rol = get_object_or_404(PersonaRol, pk=request.POST.get("persona_rol_id"), persona=persona)
            persona_rol.activo = not persona_rol.activo
            persona_rol.save(update_fields=["activo"])
            messages.success(request, "Estado del rol actualizado.")
            return redirect(_url_con_filtros(request, "personas:persona_edit", pk=persona.pk))

    context.update({"form": form, "rol_form": rol_form, "persona_obj": persona, "roles_asignados": persona.roles.all()})
    return render(request, "personas/persona_edit.html", context)

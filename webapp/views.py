from datetime import timedelta
import calendar

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.formats import date_format

from academia.models import Disciplina, SesionClase
from asistencias.models import Asistencia
from cobros.models import DocumentoVenta, Pago, Plan
from cobros.services import aplicar_pago_a_deudas, indicadores_deuda, recalcular_ciclo_pago
from cuentas.models import Persona, PersonaRol, Rol
from finanzas.models import LiquidacionProfesor, MovimientoCaja
from organizaciones.models import Organizacion

from .decorators import role_required
from .forms import (
    AsistenciaMasivaForm,
    PagoPersonaForm,
    PersonaRapidaForm,
    SesionBasicaForm,
)
from .utils import ROLE_ADMIN


def _nav_context(request):
    """Common navbar context for authenticated webapp views."""
    persona = getattr(request.user, "persona", None)
    roles = []
    if persona:
        roles = list(persona.roles.filter(activo=True).values_list("rol__codigo", flat=True))
    return {"persona": persona, "roles_usuario": roles}


def _periodo(request):
    """Resolve the active month range from query params."""
    hoy = timezone.localdate()
    try:
        anio = int(request.GET.get("periodo_anio", hoy.year))
    except (TypeError, ValueError):
        anio = hoy.year
    try:
        mes = int(request.GET.get("periodo_mes", hoy.month))
    except (TypeError, ValueError):
        mes = hoy.month
    if mes < 1 or mes > 12:
        mes = hoy.month
    if anio < 2000 or anio > 2100:
        anio = hoy.year
    inicio = hoy.replace(year=anio, month=mes, day=1)
    fin = (inicio.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
    return inicio, fin


def _organizacion_desde_request(request):
    """Return selected organization from global filter, or None."""
    org_id = request.GET.get("organizacion")
    if not org_id:
        return None
    return Organizacion.objects.filter(pk=org_id).first()


@role_required(ROLE_ADMIN)
def dashboard(request):
    """Main admin dashboard with period/org-aware operational metrics."""
    context = _nav_context(request)
    inicio_mes, fin_mes = _periodo(request)
    organizacion = _organizacion_desde_request(request)
    nombre_mes = date_format(inicio_mes, "F")
    sesiones_mes = (
        SesionClase.objects.filter(fecha__gte=inicio_mes, fecha__lte=fin_mes)
        .select_related("disciplina")
        .prefetch_related("profesores")
    )
    if organizacion:
        sesiones_mes = sesiones_mes.filter(disciplina__organizacion=organizacion)
    sesiones_hoy = sesiones_mes.filter(fecha=timezone.localdate())
    asistencias_mes_qs = Asistencia.objects.filter(sesion__fecha__gte=inicio_mes, sesion__fecha__lte=fin_mes)
    if organizacion:
        asistencias_mes_qs = asistencias_mes_qs.filter(sesion__disciplina__organizacion=organizacion)
    asistencias_mes = asistencias_mes_qs.count()
    boletas_qs = DocumentoVenta.objects.exclude(estado=DocumentoVenta.Estado.PAGADO)
    if organizacion:
        boletas_qs = boletas_qs.filter(organizacion=organizacion)
    boletas_pendientes = boletas_qs.count()
    morosos = []
    estudiantes = Persona.objects.filter(roles__rol__codigo="ESTUDIANTE").distinct()
    for estudiante in estudiantes:
        asistencias_est = Asistencia.objects.filter(
            persona=estudiante,
            sesion__fecha__gte=inicio_mes,
            sesion__fecha__lte=fin_mes,
            estado_cobro=Asistencia.EstadoCobro.DEUDA,
        )
        if organizacion:
            asistencias_est = asistencias_est.filter(sesion__disciplina__organizacion=organizacion)
        if not asistencias_est.exists():
            continue
        morosos.append({"persona": estudiante, "pendientes": asistencias_est.count()})
        if len(morosos) == 5:
            break
    sesiones_resumen = (
        sesiones_mes.annotate(total_asistentes=Count("asistencias"))
        .order_by("-fecha")[:10]
    )
    pagos_recientes_qs = (
        Pago.objects.select_related("persona")
        .filter(fecha_pago__gte=inicio_mes, fecha_pago__lte=fin_mes)
        .order_by("-fecha_pago")
    )
    if organizacion:
        pagos_recientes_qs = pagos_recientes_qs.filter(
            Q(plan__organizacion=organizacion)
            | Q(sesion__disciplina__organizacion=organizacion)
            | Q(documento__organizacion=organizacion)
        )
    pagos_recientes = pagos_recientes_qs[:5]
    liquidaciones_qs = (
        LiquidacionProfesor.objects.select_related("profesor")
        .filter(periodo_inicio__lte=fin_mes, periodo_fin__gte=inicio_mes)
        .order_by("-periodo_inicio")
    )
    if organizacion:
        liquidaciones_qs = liquidaciones_qs.filter(organizacion=organizacion)
    liquidaciones_recientes = liquidaciones_qs[:5]
    context.update(
        {
            "sesiones_hoy": sesiones_hoy,
            "morosos": morosos,
            "asistencias_mes": asistencias_mes,
            "boletas_pendientes": boletas_pendientes,
            "sesiones_resumen": sesiones_resumen,
            "pagos_recientes": pagos_recientes,
            "liquidaciones_recientes": liquidaciones_recientes,
            "nombre_mes": nombre_mes,
        }
    )
    return render(request, "webapp/dashboard.html", context)


@role_required(ROLE_ADMIN)
def sesiones_list(request):
    """Monthly calendar view of sessions."""
    context = _nav_context(request)
    organizacion = _organizacion_desde_request(request)
    inicio_periodo, _ = _periodo(request)
    year = inicio_periodo.year
    month = inicio_periodo.month
    cal = calendar.Calendar(firstweekday=calendar.MONDAY)
    semanas_raw = cal.monthdatescalendar(year, month)
    inicio_mes = inicio_periodo.replace(day=1)
    fin_mes = (inicio_mes.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
    sesiones_qs = (
        SesionClase.objects.select_related("disciplina")
        .prefetch_related("profesores")
        .filter(fecha__gte=inicio_mes, fecha__lte=fin_mes)
        .order_by("fecha")
    )
    if organizacion:
        sesiones_qs = sesiones_qs.filter(disciplina__organizacion=organizacion)
    sesiones_por_fecha = {}
    for sesion in sesiones_qs:
        sesiones_por_fecha.setdefault(sesion.fecha, []).append(sesion)
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
            "semanas": semanas,
            "mes_actual": inicio_mes,
        }
    )
    return render(request, "webapp/sesiones_list.html", context)


@role_required(ROLE_ADMIN)
def estudiantes_list(request):
    """Student list with payment/attendance status for selected period."""
    context = _nav_context(request)
    context["hide_periodo"] = True
    hoy = timezone.localdate()
    inicio_mes, fin_mes = _periodo(request)
    estudiantes = Persona.objects.filter(roles__rol__codigo="ESTUDIANTE").distinct().prefetch_related("roles__organizacion", "roles__rol")
    organizaciones = Organizacion.objects.all()
    org_id = request.GET.get("organizacion")
    if org_id:
        estudiantes = estudiantes.filter(
            Q(roles__organizacion_id=org_id) | Q(pagos__plan__organizacion_id=org_id)
        ).distinct()
    if request.GET.get("sin_plan") == "1":
        estudiantes = estudiantes.exclude(pagos__tipo=Pago.Tipo.PLAN)
    if request.GET.get("morosos") == "1":
        estudiantes = [
            persona
            for persona in estudiantes
            if Asistencia.objects.filter(
                persona=persona,
                sesion__fecha__gte=inicio_mes,
                sesion__fecha__lte=fin_mes,
                estado_cobro=Asistencia.EstadoCobro.DEUDA,
            ).exists()
        ]
    contexto = []
    for persona in estudiantes:
        pagos_plan = list(
            persona.pagos.filter(tipo=Pago.Tipo.PLAN).select_related("plan").order_by("-fecha_pago")
        )
        plan_activo = next((p for p in pagos_plan if p.vigente_en(hoy)), None)
        asistencias_mes = Asistencia.objects.filter(persona=persona, sesion__fecha__gte=inicio_mes, sesion__fecha__lte=fin_mes)
        pendientes = asistencias_mes.filter(estado_cobro=Asistencia.EstadoCobro.DEUDA).count()
        contexto.append(
            {
                "persona": persona,
                "plan_pago": plan_activo,
                "clases_usadas": plan_activo.clases_usadas if plan_activo else 0,
                "clases_restantes": plan_activo.clases_restantes() if plan_activo else 0,
                "pendientes": pendientes,
            }
        )
    context["estudiantes"] = contexto
    context["organizaciones"] = organizaciones
    context["filtros"] = {
        "organizacion": org_id,
        "sin_plan": request.GET.get("sin_plan"),
        "morosos": request.GET.get("morosos"),
    }
    return render(request, "webapp/estudiantes_list.html", context)


@role_required(ROLE_ADMIN)
def profesores_list(request):
    """Teacher list aggregated by organization and selected period."""
    context = _nav_context(request)
    profesores = Persona.objects.filter(roles__rol__codigo="PROFESOR").distinct()
    org_id = request.GET.get("organizacion")
    inicio_mes, fin_mes = _periodo(request)
    profesores_data = []
    for profesor in profesores:
        organizaciones_prof = profesor.roles.filter(rol__codigo="PROFESOR").select_related("organizacion")
        if org_id:
            organizaciones_prof = organizaciones_prof.filter(organizacion_id=org_id)
        for rol_prof in organizaciones_prof:
            organizacion = rol_prof.organizacion
            asistencias_qs = Asistencia.objects.filter(
                sesion__fecha__gte=inicio_mes,
                sesion__fecha__lte=fin_mes,
                sesion__profesores=profesor,
                sesion__disciplina__organizacion=organizacion,
            )
            alumnos_unicos_mes = asistencias_qs.values("persona_id").distinct().count()
            asistencias_mes = asistencias_qs.count()
            sesiones_mes = SesionClase.objects.filter(
                fecha__gte=inicio_mes,
                fecha__lte=fin_mes,
                profesores=profesor,
                disciplina__organizacion=organizacion,
                estado=SesionClase.Estado.COMPLETADA,
            ).distinct().count()
            disciplinas_qs = Disciplina.objects.filter(
                sesiones__profesores=profesor,
                organizacion=organizacion,
            ).distinct().order_by("nombre")
            ganado_total = asistencias_mes * 3743 if organizacion.nombre == "Espacio Elementos" else 0
            ganado_total_fmt = f"{ganado_total:,}".replace(",", ".") if ganado_total else ""
            profesores_data.append(
                {
                    "persona": profesor,
                    "organizacion": organizacion,
                    "alumnos_unicos_mes": alumnos_unicos_mes,
                    "asistencias_mes": asistencias_mes,
                    "sesiones_mes": sesiones_mes,
                    "disciplinas": disciplinas_qs,
                    "ganado_total": ganado_total,
                    "ganado_total_fmt": ganado_total_fmt,
                }
            )
    profesores_data.sort(key=lambda item: (item["persona"].apellidos or "", item["persona"].nombres or "", item["organizacion"].nombre or ""))
    context["profesores"] = profesores_data
    context["organizaciones"] = Organizacion.objects.all()
    return render(request, "webapp/profesores_list.html", context)


@role_required(ROLE_ADMIN)
def persona_detail(request, pk):
    """Student/teacher profile with period-aware attendance and payments."""
    context = _nav_context(request)
    organizacion_filtro = _organizacion_desde_request(request)
    persona = get_object_or_404(Persona, pk=pk)
    roles_codigos = set(persona.roles.values_list("rol__codigo", flat=True))
    es_estudiante = "ESTUDIANTE" in roles_codigos
    es_profesor = "PROFESOR" in roles_codigos
    hoy = timezone.localdate()
    inicio_mes, fin_mes = _periodo(request)
    organizaciones_persona = Organizacion.objects.filter(persona_roles__persona=persona).distinct()
    if not organizaciones_persona.exists():
        organizaciones_persona = Organizacion.objects.all()

    planes_persona_qs = Plan.objects.filter(
        organizacion__in=organizaciones_persona,
        activo=True,
    ).distinct()
    pago_persona_form = PagoPersonaForm(plan_queryset=planes_persona_qs)

    if request.method == "POST":
        if "cambiar_estado" in request.POST:
            sesion_id_post = request.POST.get("sesion_id")
            estado = request.POST.get("estado")
            if sesion_id_post and estado in dict(SesionClase.Estado.choices):
                sesion = get_object_or_404(SesionClase, pk=sesion_id_post)
                sesion.estado = estado
                sesion.save(update_fields=["estado"])
                messages.success(request, "Estado de sesion actualizado.")
                return redirect("webapp:persona_detail", pk=persona.pk)
        elif "registrar_pago_persona" in request.POST:
            pago_persona_form = PagoPersonaForm(
                request.POST,
                plan_queryset=planes_persona_qs,
            )
            if pago_persona_form.is_valid():
                pago = pago_persona_form.save(commit=False)
                pago.persona = persona
                if pago.tipo == Pago.Tipo.PLAN and not pago.plan:
                    messages.error(request, "Debes seleccionar un plan para este pago.")
                    return redirect("webapp:persona_detail", pk=persona.pk)
                if pago.tipo == Pago.Tipo.CLASE and not pago.clases_total:
                    pago.clases_total = 1
                if pago.tipo == Pago.Tipo.PLAN and not pago.clases_total:
                    pago.clases_total = pago.plan.clases_por_mes if pago.plan else 0
                pago.save()
                recalcular_ciclo_pago(pago)
                aplicadas = aplicar_pago_a_deudas(persona, pago)
                messages.success(request, "Pago registrado.")
                if aplicadas:
                    messages.info(request, f"Asistencias de deuda cubiertas: {aplicadas}.")
                return redirect("webapp:persona_detail", pk=persona.pk)
    asistencias_qs = persona.asistencias.select_related("sesion", "sesion__disciplina").order_by("-registrada_en")
    pagos_qs = persona.pagos.select_related("sesion", "plan").order_by("-fecha_pago")
    asistencias_periodo = asistencias_qs.filter(sesion__fecha__gte=inicio_mes, sesion__fecha__lte=fin_mes)
    pagos_periodo = pagos_qs.filter(fecha_pago__gte=inicio_mes, fecha_pago__lte=fin_mes)
    pagos_plan_qs = pagos_periodo.filter(
        tipo=Pago.Tipo.PLAN,
        plan__isnull=False,
    )
    disciplinas_asistidas = sorted({a.sesion.disciplina.nombre for a in asistencias_qs})
    planes_persona = sorted({str(p.plan) for p in pagos_plan_qs if p.plan})
    asistencias_rows = []
    for asistencia in asistencias_periodo:
        asistencias_rows.append(
            {
                "asistencia": asistencia,
                "pagado": asistencia.estado_cobro == Asistencia.EstadoCobro.CUBIERTA,
            }
        )
    context.update(
        {
            "persona": persona,
            "roles_asignados": persona.roles.select_related("rol"),
            "pagos_plan": pagos_plan_qs,
            "pagos": pagos_periodo,
            "asistencias": asistencias_rows,
            "es_estudiante": es_estudiante,
            "es_profesor": es_profesor,
            "asistencias_mes": asistencias_qs.filter(sesion__fecha__gte=inicio_mes, sesion__fecha__lte=fin_mes).count(),
            "pagos_mes": pagos_periodo.count(),
            "pagos_clase_mes": pagos_periodo.filter(
                tipo=Pago.Tipo.CLASE, sesion__fecha__gte=inicio_mes, sesion__fecha__lte=fin_mes
            ).count(),
            "disciplinas_asistidas": disciplinas_asistidas,
            "planes_persona": planes_persona,
            "asistencia_estados": Asistencia.Estado.choices,
            "pago_tipos": Pago.Tipo.choices,
            "pago_metodos": Pago.Metodo.choices,
            "pago_persona_form": pago_persona_form,
            "organizaciones_persona": organizaciones_persona,
            "planes_persona_qs": planes_persona_qs,
        }
    )
    context["pagos_pendientes_mes"] = (
        Asistencia.objects.filter(
            persona=persona,
            sesion__fecha__gte=inicio_mes,
            sesion__fecha__lte=fin_mes,
            estado_cobro=Asistencia.EstadoCobro.DEUDA,
        ).count()
    )
    if es_profesor:
        sesiones_realizadas = SesionClase.objects.filter(
            profesores=persona,
            fecha__gte=inicio_mes,
            fecha__lte=fin_mes,
        ).select_related("disciplina", "disciplina__organizacion").order_by("-fecha")
        if organizacion_filtro:
            sesiones_realizadas = sesiones_realizadas.filter(disciplina__organizacion=organizacion_filtro)
        asistencias_prof = Asistencia.objects.filter(
            sesion__profesores=persona,
        ).select_related("sesion__disciplina", "sesion__disciplina__organizacion")
        if organizacion_filtro:
            asistencias_prof = asistencias_prof.filter(sesion__disciplina__organizacion=organizacion_filtro)
        sesiones_resumen_qs = sesiones_realizadas
        asistencias_prof_resumen_qs = asistencias_prof.filter(sesion__fecha__gte=inicio_mes, sesion__fecha__lte=fin_mes)
        resumen_por_org = []
        organizaciones_resumen = [organizacion_filtro] if organizacion_filtro else Organizacion.objects.all()
        for org in organizaciones_resumen:
            sesiones_org = sesiones_resumen_qs.filter(disciplina__organizacion=org)
            asistencias_org = asistencias_prof_resumen_qs.filter(sesion__disciplina__organizacion=org)
            if not sesiones_org.exists() and not asistencias_org.exists():
                continue
            resumen_por_org.append(
                {
                    "organizacion": org,
                    "sesiones": sesiones_org.count(),
                    "alumnos": asistencias_org.values("persona_id").distinct().count(),
                    "asistencias": asistencias_org.count(),
                }
            )
        liquidaciones = LiquidacionProfesor.objects.filter(profesor=persona).select_related("organizacion").order_by("-periodo_inicio")
        if organizacion_filtro:
            liquidaciones = liquidaciones.filter(organizacion=organizacion_filtro)
        context.update(
            {
                "sesiones_realizadas": sesiones_realizadas,
                "resumen_profesor": resumen_por_org,
                "liquidaciones": liquidaciones,
            }
        )
    return render(request, "webapp/persona_detail.html", context)


@role_required(ROLE_ADMIN)
def asistencias_list(request):
    """Operational attendance page: quick session creation and bulk marking."""
    context = _nav_context(request)
    sesion_id = request.GET.get("sesion_id")
    organizacion = _organizacion_desde_request(request)
    sesion_form = SesionBasicaForm(initial={"fecha": timezone.localdate()})
    asistencia_form = AsistenciaMasivaForm(initial={"sesion_id": sesion_id} if sesion_id else None)
    persona_form = PersonaRapidaForm()
    estudiantes_qs = Persona.objects.filter(roles__rol__codigo="ESTUDIANTE").distinct().order_by("apellidos", "nombres")
    asistencia_form.fields["estudiantes"].queryset = estudiantes_qs

    if request.method == "POST":
        if "crear_sesion" in request.POST:
            sesion_form = SesionBasicaForm(request.POST)
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
                messages.success(request, "Sesion creada. Ahora puedes agregar asistentes.")
                return redirect(f"{request.path}?sesion_id={sesion.pk}")
        elif "cambiar_estado" in request.POST:
            sesion_id_post = request.POST.get("sesion_id")
            estado = request.POST.get("estado")
            if sesion_id_post and estado in dict(SesionClase.Estado.choices):
                sesion = get_object_or_404(SesionClase, pk=sesion_id_post)
                sesion.estado = estado
                sesion.save(update_fields=["estado"])
                messages.success(request, "Estado de sesion actualizado.")
                return redirect(request.path)
        elif "agregar_persona" in request.POST:
            persona_form = PersonaRapidaForm(request.POST)
            if persona_form.is_valid():
                persona = Persona.objects.create(
                    nombres=persona_form.cleaned_data["nombres"].strip(),
                    apellidos=persona_form.cleaned_data.get("apellidos", "").strip(),
                    telefono=persona_form.cleaned_data.get("telefono", "").strip(),
                )
                rol_estudiante = Rol.objects.filter(codigo="ESTUDIANTE").first()
                organizacion = Organizacion.objects.first()
                if rol_estudiante and organizacion:
                    PersonaRol.objects.get_or_create(
                        persona=persona,
                        rol=rol_estudiante,
                        organizacion=organizacion,
                        defaults={"activo": True},
                    )
                    messages.success(request, "Persona creada y asignada como estudiante.")
                else:
                    messages.warning(request, "Persona creada, pero no se pudo asignar rol estudiante.")
                return redirect(request.path)
        elif "agregar_asistentes" in request.POST:
            asistencia_form = AsistenciaMasivaForm(request.POST)
            asistencia_form.fields["estudiantes"].queryset = estudiantes_qs
            if asistencia_form.is_valid():
                sesion = get_object_or_404(SesionClase, pk=asistencia_form.cleaned_data["sesion_id"])
                estudiantes = asistencia_form.cleaned_data["estudiantes"]
                creados = 0
                for persona in estudiantes:
                    _, created = Asistencia.objects.get_or_create(
                        sesion=sesion,
                        persona=persona,
                        defaults={"estado": Asistencia.Estado.PRESENTE},
                    )
                    if created:
                        creados += 1
                messages.success(request, f"Asistencias agregadas: {creados}.")
                return redirect(f"{request.path}?sesion_id={sesion.pk}")

    inicio_mes, fin_mes = _periodo(request)
    estudiantes_mes_qs = Persona.objects.filter(
        roles__rol__codigo="ESTUDIANTE",
        asistencias__sesion__fecha__gte=inicio_mes,
        asistencias__sesion__fecha__lte=fin_mes,
    )
    if organizacion:
        estudiantes_mes_qs = estudiantes_mes_qs.filter(asistencias__sesion__disciplina__organizacion=organizacion)
    estudiantes_total_mes = estudiantes_mes_qs.distinct().count()
    sesiones_qs = (
        SesionClase.objects.select_related("disciplina")
        .prefetch_related("profesores", "asistencias__persona")
        .filter(fecha__gte=inicio_mes, fecha__lte=fin_mes)
        .order_by("-fecha")
    )
    if organizacion:
        sesiones_qs = sesiones_qs.filter(disciplina__organizacion=organizacion)
    sesiones_list = []
    for sesion in sesiones_qs:
        total_asistentes = sesion.asistencias.count()
        pagos = sesion.asistencias.filter(estado_cobro=Asistencia.EstadoCobro.CUBIERTA).count()
        no_pagos = total_asistentes - pagos
        sesiones_list.append(
            {
                "sesion": sesion,
                "total_asistentes": total_asistentes,
                "pagos": pagos,
                "no_pagos": no_pagos,
            }
        )
    sesiones_page = sesiones_list

    context.update(
        {
            "sesion_form": sesion_form,
            "asistencia_form": asistencia_form,
            "persona_form": persona_form,
            "open_nueva_sesion": request.GET.get("open") == "nueva_sesion",
            "sesiones": sesiones_page,
            "sesion_seleccionada": SesionClase.objects.filter(pk=sesion_id).first() if sesion_id else None,
            "estudiantes_total": estudiantes_qs.count(),
            "estudiantes_total_mes": estudiantes_total_mes,
            "disciplinas": Disciplina.objects.filter(organizacion=organizacion) if organizacion else Disciplina.objects.all(),
            "profesores": Persona.objects.filter(roles__rol__codigo="PROFESOR").distinct().order_by("apellidos", "nombres"),
            "organizaciones": Organizacion.objects.all(),
        }
    )
    context["deuda_indicadores"] = indicadores_deuda(inicio_mes, fin_mes, organizacion)
    return render(request, "webapp/asistencias_list.html", context)


@role_required(ROLE_ADMIN)
def sesion_detail(request, pk):
    """Session detail and per-student payment state."""
    context = _nav_context(request)
    context["hide_periodo"] = True
    sesion = get_object_or_404(
        SesionClase.objects.select_related("disciplina").prefetch_related("profesores", "asistencias__persona"),
        pk=pk,
    )
    if request.method == "POST" and "cambiar_estado" in request.POST:
        estado = request.POST.get("estado")
        if estado in dict(SesionClase.Estado.choices):
            sesion.estado = estado
            sesion.save(update_fields=["estado"])
            messages.success(request, "Estado de sesion actualizado.")
            return redirect("webapp:sesion_detail", pk=sesion.pk)
    asistencias = sesion.asistencias.select_related("persona").order_by("-registrada_en")
    total_asistentes = asistencias.count()
    pagos = asistencias.filter(estado_cobro=Asistencia.EstadoCobro.CUBIERTA).count()
    no_pagos = total_asistentes - pagos
    asistencias_rows = []
    for asistencia in asistencias:
        asistencias_rows.append(
            {
                "asistencia": asistencia,
                "pagado": asistencia.estado_cobro == Asistencia.EstadoCobro.CUBIERTA,
            }
        )
    context.update(
        {
            "sesion": sesion,
            "asistencias": asistencias_rows,
            "total_asistentes": total_asistentes,
            "pagos": pagos,
            "no_pagos": no_pagos,
        }
    )
    return render(request, "webapp/sesion_detail.html", context)


@role_required(ROLE_ADMIN)
def pagos_list(request):
    """Paginated payment list filtered by global period and organization."""
    context = _nav_context(request)
    inicio_mes, fin_mes = _periodo(request)
    organizacion = _organizacion_desde_request(request)
    pagos = (
        Pago.objects.select_related("persona", "plan", "sesion")
        .filter(fecha_pago__gte=inicio_mes, fecha_pago__lte=fin_mes)
        .order_by("-fecha_pago")
    )
    if organizacion:
        pagos = pagos.filter(
            Q(plan__organizacion=organizacion)
            | Q(sesion__disciplina__organizacion=organizacion)
            | Q(documento__organizacion=organizacion)
        )
    context["pagos"] = Paginator(pagos, 25).get_page(request.GET.get("page"))
    return render(request, "webapp/pagos_list.html", context)


@role_required(ROLE_ADMIN)
def finanzas_unificadas(request):
    """Unified financial view for the selected month."""
    context = _nav_context(request)
    inicio_mes, fin_mes = _periodo(request)
    organizacion = _organizacion_desde_request(request)
    pagos = Pago.objects.select_related("persona").filter(fecha_pago__gte=inicio_mes, fecha_pago__lte=fin_mes).order_by("-fecha_pago")
    liquidaciones = LiquidacionProfesor.objects.select_related("profesor").filter(periodo_inicio__lte=fin_mes, periodo_fin__gte=inicio_mes).order_by("-periodo_inicio")
    movimientos = MovimientoCaja.objects.filter(fecha__gte=inicio_mes, fecha__lte=fin_mes).order_by("-fecha")
    if organizacion:
        pagos = pagos.filter(
            Q(plan__organizacion=organizacion)
            | Q(sesion__disciplina__organizacion=organizacion)
            | Q(documento__organizacion=organizacion)
        )
        liquidaciones = liquidaciones.filter(organizacion=organizacion)
        movimientos = movimientos.filter(organizacion=organizacion)
    context.update(
        {
            "pagos": pagos[:20],
            "liquidaciones": liquidaciones[:20],
            "movimientos": movimientos[:20],
        }
    )
    return render(request, "webapp/finanzas_unificadas.html", context)


@role_required(ROLE_ADMIN)
def organizaciones_list(request):
    """Organization cards and base data."""
    context = _nav_context(request)
    context["hide_periodo"] = True
    context["organizaciones"] = Organizacion.objects.all().order_by("nombre")
    return render(request, "webapp/organizaciones_list.html", context)

from datetime import timedelta
import calendar

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.formats import date_format

from academia.models import Disciplina, SesionClase
from asistencias.models import Asistencia
from cobros.models import DocumentoVenta, Pago, Suscripcion
from cuentas.models import Persona, PersonaRol, Rol
from finanzas.models import LiquidacionProfesor, MovimientoCaja
from organizaciones.models import Organizacion

from .decorators import role_required
from .forms import AsistenciaMasivaForm, AsistenciaRapidaForm, AsistenciaSesionForm, PagoRapidoForm, PersonaRapidaForm, SesionBasicaForm, SesionRapidaForm
from .utils import ROLE_ADMIN


def _nav_context(request):
    persona = getattr(request.user, "persona", None)
    roles = []
    if persona:
        roles = list(persona.roles.filter(activo=True).values_list("rol__codigo", flat=True))
    return {"persona": persona, "roles_usuario": roles}


def _personas_recientes():
    fecha_limite = timezone.localdate() - timedelta(days=90)
    personas_recientes = Persona.objects.filter(asistencias__sesion__fecha__gte=fecha_limite).distinct()
    if personas_recientes.exists():
        return personas_recientes
    return Persona.objects.filter(activo=True)


@role_required(ROLE_ADMIN)
def dashboard(request):
    context = _nav_context(request)
    hoy = timezone.localdate()
    inicio_mes = hoy.replace(day=1)
    nombre_mes = date_format(hoy, "F")
    sesiones_mes = (
        SesionClase.objects.filter(fecha__gte=inicio_mes)
        .select_related("disciplina")
        .prefetch_related("profesores")
    )
    sesiones_hoy = sesiones_mes.filter(fecha=hoy)
    asistencias_mes = Asistencia.objects.filter(sesion__fecha__gte=inicio_mes).count()
    boletas_pendientes = DocumentoVenta.objects.exclude(estado=DocumentoVenta.Estado.PAGADO).count()
    morosos = []
    for suscripcion in Suscripcion.objects.order_by("-fecha_inicio"):
        saldo = suscripcion.saldo_pendiente()
        if saldo > 0:
            morosos.append({"suscripcion": suscripcion, "saldo": saldo})
        if len(morosos) == 5:
            break
    sesiones_resumen = (
        sesiones_mes.annotate(total_asistentes=Count("asistencias"))
        .order_by("-fecha")[:10]
    )
    pagos_recientes = Pago.objects.select_related("persona").order_by("-fecha_pago")[:5]
    liquidaciones_recientes = LiquidacionProfesor.objects.select_related("profesor").order_by("-periodo_inicio")[:5]
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
    context = _nav_context(request)
    hoy = timezone.localdate()
    year = int(request.GET.get("year", hoy.year))
    month = int(request.GET.get("month", hoy.month))
    cal = calendar.Calendar(firstweekday=calendar.MONDAY)
    semanas_raw = cal.monthdatescalendar(year, month)
    inicio_mes = hoy.replace(day=1)
    inicio_mes = inicio_mes.replace(year=year, month=month, day=1)
    fin_mes = (inicio_mes.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
    sesiones_qs = (
        SesionClase.objects.select_related("disciplina")
        .prefetch_related("profesores")
        .filter(fecha__gte=inicio_mes, fecha__lte=fin_mes)
        .order_by("fecha")
    )
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
            "year": year,
            "month": month,
            "years": list(range(hoy.year - 2, hoy.year + 3)),
            "months": list(range(1, 13)),
        }
    )
    return render(request, "webapp/sesiones_list.html", context)


@role_required(ROLE_ADMIN)
def sesion_rapida(request):
    context = _nav_context(request)
    sesion = None
    asistencia_form = AsistenciaRapidaForm()
    personas_recientes = _personas_recientes()

    sesion_id = request.GET.get("sesion_id") or request.POST.get("sesion_id")
    if sesion_id:
        sesion = get_object_or_404(SesionClase, pk=sesion_id)

    if request.method == "POST":
        if "crear_sesion" in request.POST:
            form = SesionRapidaForm(request.POST)
            if form.is_valid():
                disciplina = form.cleaned_data["disciplina"]
                if not disciplina:
                    messages.error(request, "Debes seleccionar una disciplina.")
                    return redirect("webapp:sesion_rapida")
                fecha = form.cleaned_data["fecha"] or timezone.localdate()
                notas = form.cleaned_data["notas"]
                if not notas:
                    notas = f"{disciplina.nombre} - {fecha}"
                profesores = list(form.cleaned_data["profesores"])
                sesion = SesionClase.objects.create(
                    disciplina=disciplina,
                    fecha=fecha,
                    cupo_maximo=form.cleaned_data["cupo_maximo"],
                    notas=notas,
                )
                if profesores:
                    sesion.profesores.set(profesores)
                messages.success(request, "Sesion creada. Ahora puedes marcar asistencia.")
                return redirect(f"{request.path}?sesion_id={sesion.pk}")
        elif "agregar_asistencia" in request.POST and sesion:
            asistencia_form = AsistenciaRapidaForm(request.POST)
            asistencia_form.fields["persona"].queryset = personas_recientes
            if asistencia_form.is_valid():
                asistencia = asistencia_form.save(commit=False)
                asistencia.sesion = sesion
                asistencia.save()
                suscripcion = asistencia.persona.suscripciones.order_by("-fecha_inicio").first()
                if suscripcion:
                    messages.info(
                        request,
                        f"Plan vigente: {suscripcion.plan}. Clases usadas: {suscripcion.clases_usadas()}",
                    )
                else:
                    messages.warning(request, "El estudiante no tiene plan vigente.")
                return redirect(f"{request.path}?sesion_id={sesion.pk}")

    sesion_form = SesionRapidaForm()
    asistencia_form.fields["persona"].queryset = personas_recientes
    if sesion:
        asistencias = Asistencia.objects.filter(sesion=sesion).select_related("persona")
    else:
        asistencias = []
    context.update(
        {
            "sesion": sesion,
            "sesion_form": sesion_form,
            "asistencia_form": asistencia_form,
            "asistencias": asistencias,
        }
    )
    return render(request, "webapp/sesion_rapida.html", context)


@role_required(ROLE_ADMIN)
def estudiantes_list(request):
    context = _nav_context(request)
    estudiantes = Persona.objects.filter(roles__rol__codigo="ESTUDIANTE").distinct().prefetch_related("roles__organizacion", "roles__rol")
    organizaciones = Organizacion.objects.all()
    org_id = request.GET.get("organizacion")
    if org_id:
        estudiantes = estudiantes.filter(
            Q(roles__organizacion_id=org_id) | Q(suscripciones__plan__organizacion_id=org_id)
        ).distinct()
    if request.GET.get("sin_plan") == "1":
        estudiantes = estudiantes.filter(suscripciones__isnull=True)
    if request.GET.get("morosos") == "1":
        estudiantes = [
            persona
            for persona in estudiantes
            if persona.suscripciones.order_by("-fecha_inicio").first()
            and persona.suscripciones.order_by("-fecha_inicio").first().saldo_pendiente() > 0
        ]
    contexto = []
    for persona in estudiantes:
        suscripcion = persona.suscripciones.order_by("-fecha_inicio").first()
        contexto.append(
            {
                "persona": persona,
                "suscripcion": suscripcion,
                "clases_usadas": suscripcion.clases_usadas() if suscripcion else 0,
                "saldo_pendiente": suscripcion.saldo_pendiente() if suscripcion else 0,
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
    context = _nav_context(request)
    profesores = Persona.objects.filter(roles__rol__codigo="PROFESOR").distinct()
    org_id = request.GET.get("organizacion")
    if org_id:
        profesores = profesores.filter(
            Q(roles__organizacion_id=org_id) | Q(sesiones_en_equipo__disciplina__organizacion_id=org_id)
        ).distinct()
    hoy = timezone.localdate()
    inicio_mes = hoy.replace(day=1)
    profesores_data = []
    for profesor in profesores:
        asistencias_qs = Asistencia.objects.filter(
            sesion__fecha__gte=inicio_mes,
            sesion__profesores=profesor,
        )
        alumnos_unicos_mes = asistencias_qs.values("persona_id").distinct().count()
        asistencias_mes = asistencias_qs.count()
        sesiones_mes = SesionClase.objects.filter(
            fecha__gte=inicio_mes,
            profesores=profesor,
            estado=SesionClase.Estado.COMPLETADA,
        ).distinct().count()
        disciplinas_qs = Disciplina.objects.filter(
            sesiones__profesores=profesor
        ).distinct().order_by("nombre")
        liquidaciones_total = (
            LiquidacionProfesor.objects.filter(profesor=profesor)
            .aggregate(total=Sum("monto_neto"))["total"]
            or 0
        )
        profesores_data.append(
            {
                "persona": profesor,
                "alumnos_unicos_mes": alumnos_unicos_mes,
                "asistencias_mes": asistencias_mes,
                "sesiones_mes": sesiones_mes,
                "disciplinas": disciplinas_qs,
                "ganado_total": liquidaciones_total,
            }
        )
    context["profesores"] = profesores_data
    context["organizaciones"] = Organizacion.objects.all()
    return render(request, "webapp/profesores_list.html", context)


@role_required(ROLE_ADMIN)
def persona_detail(request, pk):
    context = _nav_context(request)
    persona = get_object_or_404(Persona, pk=pk)
    roles_codigos = set(persona.roles.values_list("rol__codigo", flat=True))
    es_estudiante = "ESTUDIANTE" in roles_codigos
    es_profesor = "PROFESOR" in roles_codigos
    hoy = timezone.localdate()
    inicio_mes = hoy.replace(day=1)
    asistencias_qs = persona.asistencias.select_related("sesion", "sesion__disciplina").order_by("-registrada_en")
    suscripciones_qs = persona.suscripciones.select_related("plan")
    pagos_qs = persona.pagos.select_related("sesion").order_by("-fecha_pago")
    disciplinas_asistidas = sorted({a.sesion.disciplina.nombre for a in asistencias_qs})
    planes_persona = sorted({str(s.plan) for s in suscripciones_qs})
    pagos_clase_sesiones = set(
        pagos_qs.filter(tipo=Pago.Tipo.CLASE, sesion__isnull=False).values_list("sesion_id", flat=True)
    )
    asistencias_rows = []
    for asistencia in asistencias_qs:
        asistencias_rows.append(
            {
                "asistencia": asistencia,
                "pagado": asistencia.sesion_id in pagos_clase_sesiones,
            }
        )
    context.update(
        {
            "persona": persona,
            "roles_asignados": persona.roles.select_related("rol"),
            "suscripciones": suscripciones_qs,
            "pagos": pagos_qs,
            "asistencias": asistencias_rows,
            "es_estudiante": es_estudiante,
            "es_profesor": es_profesor,
            "asistencias_mes": asistencias_qs.filter(sesion__fecha__gte=inicio_mes).count(),
            "pagos_mes": pagos_qs.filter(fecha_pago__gte=inicio_mes).count(),
            "pagos_clase_mes": pagos_qs.filter(
                tipo=Pago.Tipo.CLASE, sesion__fecha__gte=inicio_mes
            ).count(),
            "disciplinas_asistidas": disciplinas_asistidas,
            "planes_persona": planes_persona,
            "asistencia_estados": Asistencia.Estado.choices,
            "suscripcion_estados": Suscripcion.Estado.choices,
            "pago_tipos": Pago.Tipo.choices,
            "pago_metodos": Pago.Metodo.choices,
        }
    )
    context["pagos_pendientes_mes"] = max(0, context["asistencias_mes"] - context["pagos_clase_mes"])
    if es_profesor:
        sesiones_realizadas = SesionClase.objects.filter(
            profesores=persona,
            estado=SesionClase.Estado.COMPLETADA,
        ).select_related("disciplina", "disciplina__organizacion").order_by("-fecha")
        asistencias_prof = Asistencia.objects.filter(
            sesion__profesores=persona,
            sesion__estado=SesionClase.Estado.COMPLETADA,
        ).select_related("sesion__disciplina", "sesion__disciplina__organizacion")
        resumen_por_org = []
        for org in Organizacion.objects.all():
            sesiones_org = sesiones_realizadas.filter(disciplina__organizacion=org)
            asistencias_org = asistencias_prof.filter(sesion__disciplina__organizacion=org)
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
    context = _nav_context(request)
    sesion_id = request.GET.get("sesion_id")
    sesion_form = SesionBasicaForm(initial={"fecha": timezone.localdate()})
    asistencia_form = AsistenciaMasivaForm(initial={"sesion_id": sesion_id} if sesion_id else None)
    persona_form = PersonaRapidaForm()
    pago_form = PagoRapidoForm(initial={"sesion": sesion_id, "tipo": Pago.Tipo.CLASE} if sesion_id else None)
    estudiantes_qs = Persona.objects.filter(roles__rol__codigo="ESTUDIANTE").distinct().order_by("apellidos", "nombres")
    asistencia_form.fields["estudiantes"].queryset = estudiantes_qs
    pago_form.fields["persona"].queryset = estudiantes_qs
    pago_form.fields["sesion"].queryset = SesionClase.objects.order_by("-fecha")
    pago_form.fields["tipo"].initial = Pago.Tipo.CLASE

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
        elif "registrar_pago_clase" in request.POST:
            pago_form = PagoRapidoForm(request.POST)
            pago_form.fields["persona"].queryset = estudiantes_qs
            pago_form.fields["sesion"].queryset = SesionClase.objects.order_by("-fecha")
            if pago_form.is_valid():
                pago = pago_form.save(commit=False)
                if pago.tipo != Pago.Tipo.CLASE:
                    pago.tipo = Pago.Tipo.CLASE
                pago.save()
                messages.success(request, "Pago por clase registrado.")
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

    sesiones_qs = (
        SesionClase.objects.select_related("disciplina")
        .prefetch_related("profesores", "asistencias__persona")
        .order_by("-fecha")
    )
    q = request.GET.get("q")
    if q:
        sesiones_qs = sesiones_qs.filter(
            Q(disciplina__nombre__icontains=q)
            | Q(profesores__nombres__icontains=q)
            | Q(profesores__apellidos__icontains=q)
            | Q(fecha__icontains=q)
        ).distinct()
    sesiones_list = []
    for sesion in sesiones_qs:
        total_asistentes = sesion.asistencias.count()
        pagos_persona_ids = set(
            Pago.objects.filter(tipo=Pago.Tipo.CLASE, sesion=sesion)
            .exclude(persona__isnull=True)
            .values_list("persona_id", flat=True)
        )
        pagos = sesion.asistencias.filter(persona_id__in=pagos_persona_ids).count()
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
            "pago_form": pago_form,
            "sesiones": sesiones_page,
            "sesion_seleccionada": SesionClase.objects.filter(pk=sesion_id).first() if sesion_id else None,
            "estudiantes_total": estudiantes_qs.count(),
            "disciplinas": Disciplina.objects.all(),
            "profesores": Persona.objects.filter(roles__rol__codigo="PROFESOR").distinct().order_by("apellidos", "nombres"),
            "organizaciones": Organizacion.objects.all(),
            "q": q or "",
        }
    )
    return render(request, "webapp/asistencias_list.html", context)


@role_required(ROLE_ADMIN)
def sesion_detail(request, pk):
    context = _nav_context(request)
    sesion = get_object_or_404(
        SesionClase.objects.select_related("disciplina").prefetch_related("profesores", "asistencias__persona"),
        pk=pk,
    )
    asistencias = sesion.asistencias.select_related("persona").order_by("-registrada_en")
    pagos_persona_ids = set(
        Pago.objects.filter(tipo=Pago.Tipo.CLASE, sesion=sesion)
        .exclude(persona__isnull=True)
        .values_list("persona_id", flat=True)
    )
    total_asistentes = asistencias.count()
    pagos = asistencias.filter(persona_id__in=pagos_persona_ids).count()
    no_pagos = total_asistentes - pagos
    asistencias_rows = []
    for asistencia in asistencias:
        asistencias_rows.append(
            {
                "asistencia": asistencia,
                "pagado": asistencia.persona_id in pagos_persona_ids,
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
    context = _nav_context(request)
    pagos = Pago.objects.select_related("persona", "suscripcion").order_by("-fecha_pago")
    context["pagos"] = Paginator(pagos, 25).get_page(request.GET.get("page"))
    return render(request, "webapp/pagos_list.html", context)


@role_required(ROLE_ADMIN)
def finanzas_unificadas(request):
    context = _nav_context(request)
    pagos = Pago.objects.select_related("persona").order_by("-fecha_pago")[:20]
    liquidaciones = LiquidacionProfesor.objects.select_related("profesor").order_by("-periodo_inicio")[:20]
    movimientos = MovimientoCaja.objects.order_by("-fecha")[:20]
    context.update(
        {
            "pagos": pagos,
            "liquidaciones": liquidaciones,
            "movimientos": movimientos,
        }
    )
    return render(request, "webapp/finanzas_unificadas.html", context)

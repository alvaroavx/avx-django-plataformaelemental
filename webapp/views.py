from datetime import date, timedelta

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.db.models import Count, F, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from academia.models import BloqueHorario, Disciplina, SesionClase
from asistencias.models import Asistencia
from cobros.models import ConvenioIntercambio, Pago, Plan, Suscripcion
from cuentas.models import Persona, PersonaRol, Rol
from finanzas.models import LiquidacionProfesor, MovimientoCaja
from organizaciones.models import Organizacion

from .decorators import role_required
from .forms import (
    AsistenciaForm,
    BloqueHorarioForm,
    ConvenioForm,
    DisciplinaForm,
    LiquidacionForm,
    MovimientoCajaForm,
    PagoForm,
    PersonaForm,
    PlanForm,
    SesionClaseForm,
    SuscripcionForm,
)
from .utils import (
    ROLE_ADMIN,
    ROLE_ESTUDIANTE,
    ROLE_PROFESOR,
    ROLE_STAFF_ASISTENCIA,
    ROLE_STAFF_FINANZAS,
    get_persona_for_user,
)


def _nav_context(request):
    persona = getattr(request.user, "persona", None)
    roles = []
    if persona:
        roles = list(persona.roles.filter(activo=True).values_list("rol__codigo", flat=True))
    return {"persona": persona, "roles_usuario": roles}


@role_required(ROLE_ADMIN, ROLE_STAFF_ASISTENCIA, ROLE_STAFF_FINANZAS, ROLE_PROFESOR)
def dashboard(request):
    context = _nav_context(request)
    hoy = timezone.localdate()
    sesiones_hoy = SesionClase.objects.filter(fecha=hoy).select_related("disciplina", "profesor")
    context.update(
        {
            "sesiones_hoy": sesiones_hoy,
            "total_estudiantes": Persona.objects.count(),
            "total_planes": Plan.objects.count(),
            "pendientes_liquidacion": LiquidacionProfesor.objects.filter(estado=LiquidacionProfesor.Estado.BORRADOR).count(),
        }
    )
    return render(request, "webapp/dashboard.html", context)


@role_required(ROLE_ADMIN, ROLE_STAFF_ASISTENCIA, ROLE_STAFF_FINANZAS)
def notificaciones(request):
    context = _nav_context(request)
    morosos = []
    for suscripcion in Suscripcion.objects.order_by("-fecha_inicio"):
        saldo = suscripcion.saldo_pendiente()
        if saldo > 0:
            morosos.append({"suscripcion": suscripcion, "saldo": saldo})
        if len(morosos) == 5:
            break
    context["morosos"] = morosos
    context["sesiones_pendientes"] = SesionClase.objects.filter(estado=SesionClase.Estado.PROGRAMADA, fecha__lt=timezone.localdate())
    context["liquidaciones_pendientes"] = LiquidacionProfesor.objects.filter(estado=LiquidacionProfesor.Estado.BORRADOR)
    return render(request, "webapp/notificaciones.html", context)


@role_required(ROLE_ADMIN, ROLE_STAFF_ASISTENCIA, ROLE_STAFF_FINANZAS, ROLE_PROFESOR)
def ayuda(request):
    context = _nav_context(request)
    return render(request, "webapp/ayuda.html", context)


@role_required(ROLE_ADMIN, ROLE_STAFF_ASISTENCIA)
def disciplinas_list(request):
    context = _nav_context(request)
    context["disciplinas"] = Disciplina.objects.select_related("organizacion")
    context["form"] = DisciplinaForm()
    return render(request, "webapp/disciplinas_list.html", context)


@role_required(ROLE_ADMIN)
def disciplina_create(request):
    context = _nav_context(request)
    if request.method == "POST":
        form = DisciplinaForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Disciplina creada correctamente.")
            return redirect("webapp:disciplinas_list")
    else:
        form = DisciplinaForm()
    context["form"] = form
    return render(request, "webapp/disciplinas_form.html", context)


@role_required(ROLE_ADMIN)
def disciplina_edit(request, pk):
    context = _nav_context(request)
    disciplina = get_object_or_404(Disciplina, pk=pk)
    if request.method == "POST":
        form = DisciplinaForm(request.POST, instance=disciplina)
        if form.is_valid():
            form.save()
            messages.success(request, "Disciplina actualizada.")
            return redirect("webapp:disciplinas_list")
    else:
        form = DisciplinaForm(instance=disciplina)
    context.update({"form": form, "disciplina": disciplina})
    return render(request, "webapp/disciplinas_form.html", context)


@role_required(ROLE_ADMIN, ROLE_STAFF_ASISTENCIA)
def horarios(request):
    context = _nav_context(request)
    bloques = BloqueHorario.objects.select_related("organizacion", "disciplina").order_by("dia_semana", "hora_inicio")
    if request.method == "POST":
        form = BloqueHorarioForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Bloque guardado.")
            return redirect("webapp:horarios")
    else:
        form = BloqueHorarioForm()
    context.update({"bloques": bloques, "form": form})
    return render(request, "webapp/horarios.html", context)


@role_required(ROLE_ADMIN, ROLE_STAFF_ASISTENCIA, ROLE_PROFESOR)
def sesiones_list(request):
    context = _nav_context(request)
    sesiones = SesionClase.objects.select_related("disciplina", "profesor").order_by("-fecha")
    filtro_disciplina = request.GET.get("disciplina")
    if filtro_disciplina:
        sesiones = sesiones.filter(disciplina_id=filtro_disciplina)
    context["sesiones"] = Paginator(sesiones, 20).get_page(request.GET.get("page"))
    context["disciplinas"] = Disciplina.objects.all()
    return render(request, "webapp/sesiones_list.html", context)


@role_required(ROLE_ADMIN, ROLE_STAFF_ASISTENCIA)
def sesion_create(request):
    context = _nav_context(request)
    if request.method == "POST":
        form = SesionClaseForm(request.POST)
        if form.is_valid():
            sesion = form.save()
            messages.success(request, "Sesión creada.")
            return redirect("webapp:sesion_detail", pk=sesion.pk)
    else:
        form = SesionClaseForm()
    context["form"] = form
    return render(request, "webapp/sesion_form.html", context)


@role_required(ROLE_ADMIN, ROLE_STAFF_ASISTENCIA, ROLE_PROFESOR)
def sesion_detail(request, pk):
    context = _nav_context(request)
    sesion = get_object_or_404(SesionClase.objects.select_related("disciplina", "profesor"), pk=pk)
    if request.method == "POST":
        form = SesionClaseForm(request.POST, instance=sesion)
        if form.is_valid():
            form.save()
            messages.success(request, "Sesión actualizada.")
            return redirect("webapp:sesion_detail", pk=sesion.pk)
    else:
        form = SesionClaseForm(instance=sesion)
    context.update({"sesion": sesion, "form": form})
    return render(request, "webapp/sesion_detail.html", context)


@role_required(ROLE_ADMIN, ROLE_STAFF_ASISTENCIA, ROLE_PROFESOR)
def sesion_asistencia(request, pk):
    context = _nav_context(request)
    sesion = get_object_or_404(SesionClase.objects.select_related("disciplina"), pk=pk)
    asistencias = Asistencia.objects.filter(sesion=sesion).select_related("persona", "convenio")
    if request.method == "POST":
        form = AsistenciaForm(request.POST)
        form.fields["persona"].queryset = Persona.objects.filter(activo=True)
        if form.is_valid():
            asistencia = form.save(commit=False)
            asistencia.sesion = sesion
            asistencia.save()
            messages.success(request, "Asistencia registrada.")
            return redirect("webapp:sesion_asistencia", pk=pk)
    else:
        form = AsistenciaForm()
        form.fields["persona"].queryset = Persona.objects.filter(activo=True)
    context.update(
        {
            "sesion": sesion,
            "form": form,
            "asistencias": asistencias,
            "contador_asistentes": asistencias.count(),
        }
    )
    return render(request, "webapp/sesion_asistencia.html", context)


@role_required(ROLE_PROFESOR, ROLE_STAFF_ASISTENCIA, ROLE_ADMIN)
def asistencia_hoy(request):
    context = _nav_context(request)
    persona = getattr(request.user, "persona", None)
    hoy = timezone.localdate()
    sesiones = SesionClase.objects.filter(fecha__gte=hoy).select_related("disciplina", "profesor")
    if persona and PersonaRol.objects.filter(persona=persona, rol__codigo=ROLE_PROFESOR, activo=True).exists():
        sesiones = sesiones.filter(profesor=persona)
    context["sesiones"] = sesiones.order_by("fecha")[:10]
    return render(request, "webapp/asistencia_hoy.html", context)


@role_required(ROLE_PROFESOR, ROLE_STAFF_ASISTENCIA, ROLE_ADMIN)
def asistencia_historial(request):
    context = _nav_context(request)
    persona = getattr(request.user, "persona", None)
    asistencias = Asistencia.objects.select_related("sesion", "persona").order_by("-registrada_en")
    if persona and PersonaRol.objects.filter(persona=persona, rol__codigo=ROLE_PROFESOR, activo=True).exists():
        asistencias = asistencias.filter(sesion__profesor=persona)
    context["asistencias"] = Paginator(asistencias, 25).get_page(request.GET.get("page"))
    return render(request, "webapp/asistencia_historial.html", context)


@role_required(ROLE_ADMIN, ROLE_STAFF_ASISTENCIA)
def personas_list(request):
    context = _nav_context(request)
    filtro = request.GET.get("rol")
    personas = Persona.objects.all().order_by("apellidos")
    if filtro:
        personas = personas.filter(roles__rol__codigo=filtro, roles__activo=True)
    context["personas"] = Paginator(personas, 25).get_page(request.GET.get("page"))
    context["roles"] = Rol.objects.all()
    return render(request, "webapp/personas_list.html", context)


@role_required(ROLE_ADMIN)
def persona_create(request):
    context = _nav_context(request)
    if request.method == "POST":
        form = PersonaForm(request.POST)
        if form.is_valid():
            persona = form.save()
            messages.success(request, "Persona creada.")
            return redirect("webapp:persona_detail", pk=persona.pk)
    else:
        form = PersonaForm()
    context["form"] = form
    return render(request, "webapp/persona_form.html", context)


@role_required(ROLE_ADMIN, ROLE_STAFF_ASISTENCIA, ROLE_STAFF_FINANZAS)
def persona_detail(request, pk):
    context = _nav_context(request)
    persona = get_object_or_404(Persona, pk=pk)
    context.update(
        {
            "persona": persona,
            "roles_asignados": persona.roles.select_related("rol"),
            "suscripciones": persona.suscripciones.select_related("plan"),
            "pagos": persona.pagos.order_by("-fecha_pago")[:5],
        }
    )
    return render(request, "webapp/persona_detail.html", context)


@role_required(ROLE_ADMIN)
def persona_roles(request, pk):
    context = _nav_context(request)
    persona = get_object_or_404(Persona, pk=pk)
    roles = Rol.objects.all()
    if request.method == "POST":
        rol_id = request.POST.get("rol_id")
        rol = get_object_or_404(Rol, pk=rol_id)
        PersonaRol.objects.get_or_create(persona=persona, rol=rol)
        messages.success(request, "Rol asignado.")
        return redirect("webapp:persona_roles", pk=pk)
    context.update({"persona": persona, "roles": roles})
    return render(request, "webapp/persona_roles.html", context)


@role_required(ROLE_ADMIN)
def persona_usuario(request, pk):
    context = _nav_context(request)
    persona = get_object_or_404(Persona, pk=pk)
    User = get_user_model()
    if request.method == "POST":
        username = request.POST.get("username")
        email = request.POST.get("email")
        password = request.POST.get("password") or User.objects.make_random_password()
        user = User.objects.create_user(username=username, email=email, password=password)
        persona.user = user
        persona.save()
        messages.success(request, f"Usuario creado: {username}")
        return redirect("webapp:persona_detail", pk=pk)
    context["persona"] = persona
    return render(request, "webapp/persona_usuario.html", context)


@role_required(ROLE_ADMIN)
def planes_list(request):
    context = _nav_context(request)
    planes = Plan.objects.select_related("organizacion")
    if request.method == "POST":
        form = PlanForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Plan guardado.")
            return redirect("webapp:planes_list")
    else:
        form = PlanForm()
    context.update({"planes": planes, "form": form})
    return render(request, "webapp/planes_list.html", context)


@role_required(ROLE_ADMIN, ROLE_STAFF_ASISTENCIA, ROLE_STAFF_FINANZAS)
def estudiantes_list(request):
    context = _nav_context(request)
    estudiantes = Persona.objects.filter(roles__rol__codigo=ROLE_ESTUDIANTE).distinct()
    contexto = []
    for persona in estudiantes:
        suscripcion = persona.suscripciones.order_by("-fecha_inicio").first()
        contexto.append(
            {
                "persona": persona,
                "suscripcion": suscripcion,
                "clases_usadas": suscripcion.clases_usadas() if suscripcion else 0,
            }
        )
    context["estudiantes"] = contexto
    return render(request, "webapp/estudiantes_list.html", context)


@role_required(ROLE_ADMIN, ROLE_STAFF_ASISTENCIA, ROLE_STAFF_FINANZAS)
def estudiante_estado(request, pk):
    context = _nav_context(request)
    persona = get_object_or_404(Persona, pk=pk)
    suscripcion = persona.suscripciones.order_by("-fecha_inicio").first()
    pagos = persona.pagos.order_by("-fecha_pago")[:5]
    context.update(
        {
            "persona": persona,
            "suscripcion": suscripcion,
            "clases_asignadas": suscripcion.clases_asignadas() if suscripcion else 0,
            "clases_usadas": suscripcion.clases_usadas() if suscripcion else 0,
            "clases_sobreconsumo": suscripcion.clases_sobreconsumo() if suscripcion else 0,
            "saldo_pendiente": suscripcion.saldo_pendiente() if suscripcion else 0,
            "pagos": pagos,
        }
    )
    return render(request, "webapp/estudiante_estado.html", context)


@role_required(ROLE_ADMIN, ROLE_STAFF_ASISTENCIA)
def estudiante_suscripciones(request, pk):
    context = _nav_context(request)
    persona = get_object_or_404(Persona, pk=pk)
    if request.method == "POST":
        form = SuscripcionForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Suscripción registrada.")
            return redirect("webapp:estudiante_suscripciones", pk=pk)
    else:
        form = SuscripcionForm(initial={"persona": persona})
    context.update({"persona": persona, "form": form, "suscripciones": persona.suscripciones.order_by("-fecha_inicio")})
    return render(request, "webapp/estudiante_suscripciones.html", context)


@role_required(ROLE_ADMIN)
def convenios_list(request):
    context = _nav_context(request)
    convenios = ConvenioIntercambio.objects.select_related("organizacion")
    if request.method == "POST":
        form = ConvenioForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Convenio guardado.")
            return redirect("webapp:convenios_list")
    else:
        form = ConvenioForm()
    context.update({"convenios": convenios, "form": form})
    return render(request, "webapp/convenios_list.html", context)


@role_required(ROLE_ADMIN, ROLE_STAFF_FINANZAS)
def pagos_list(request):
    context = _nav_context(request)
    pagos = Pago.objects.select_related("persona", "suscripcion").order_by("-fecha_pago")
    context["pagos"] = Paginator(pagos, 25).get_page(request.GET.get("page"))
    return render(request, "webapp/pagos_list.html", context)


@role_required(ROLE_ADMIN, ROLE_STAFF_FINANZAS)
def pago_create(request):
    context = _nav_context(request)
    if request.method == "POST":
        form = PagoForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, "Pago registrado.")
            return redirect("webapp:pagos_list")
    else:
        form = PagoForm()
    context["form"] = form
    return render(request, "webapp/pago_form.html", context)


@role_required(ROLE_ADMIN, ROLE_STAFF_FINANZAS)
def pago_detail(request, pk):
    context = _nav_context(request)
    pago = get_object_or_404(Pago, pk=pk)
    context["pago"] = pago
    return render(request, "webapp/pago_detail.html", context)


@role_required(ROLE_ADMIN, ROLE_STAFF_FINANZAS)
def morosos_list(request):
    context = _nav_context(request)
    morosos = []
    for suscripcion in Suscripcion.objects.all():
        saldo = suscripcion.saldo_pendiente()
        if saldo > 0:
            morosos.append({"suscripcion": suscripcion, "saldo": saldo})
    context["morosos"] = morosos
    return render(request, "webapp/morosos_list.html", context)


@role_required(ROLE_ADMIN, ROLE_STAFF_FINANZAS)
def liquidaciones_list(request):
    context = _nav_context(request)
    context["liquidaciones"] = LiquidacionProfesor.objects.select_related("profesor", "organizacion")
    return render(request, "webapp/liquidaciones_list.html", context)


@role_required(ROLE_ADMIN, ROLE_STAFF_FINANZAS)
def liquidacion_create(request):
    context = _nav_context(request)
    if request.method == "POST":
        form = LiquidacionForm(request.POST)
        if form.is_valid():
            liquidacion = form.save()
            liquidacion.calcular_totales()
            liquidacion.save()
            messages.success(request, "Liquidación generada.")
            return redirect("webapp:liquidacion_detail", pk=liquidacion.pk)
    else:
        form = LiquidacionForm()
    context["form"] = form
    return render(request, "webapp/liquidacion_form.html", context)


@role_required(ROLE_ADMIN, ROLE_STAFF_FINANZAS, ROLE_PROFESOR)
def liquidacion_detail(request, pk):
    context = _nav_context(request)
    liquidacion = get_object_or_404(LiquidacionProfesor, pk=pk)
    if request.method == "POST" and request.user.has_perm("finanzas.change_liquidacionprofesor"):
        liquidacion.estado = request.POST.get("estado", liquidacion.estado)
        liquidacion.save()
        messages.success(request, "Liquidación actualizada.")
        return redirect("webapp:liquidacion_detail", pk=pk)
    context["liquidacion"] = liquidacion
    return render(request, "webapp/liquidacion_detail.html", context)


@role_required(ROLE_ADMIN, ROLE_STAFF_FINANZAS)
def finanzas_dashboard(request):
    context = _nav_context(request)
    hoy = timezone.localdate()
    mes_inicio = hoy.replace(day=1)
    movimientos_mes = MovimientoCaja.objects.filter(fecha__gte=mes_inicio)
    ingresos = movimientos_mes.filter(tipo=MovimientoCaja.Tipo.INGRESO).aggregate(total=Sum("monto_total"))["total"] or 0
    egresos = movimientos_mes.filter(tipo=MovimientoCaja.Tipo.EGRESO).aggregate(total=Sum("monto_total"))["total"] or 0
    context.update({"ingresos": ingresos, "egresos": egresos, "saldo": ingresos - egresos, "movimientos": movimientos_mes[:10]})
    return render(request, "webapp/finanzas_dashboard.html", context)


@role_required(ROLE_ADMIN, ROLE_STAFF_FINANZAS)
def movimientos_list(request):
    context = _nav_context(request)
    movimientos = MovimientoCaja.objects.select_related("organizacion")
    context["movimientos"] = Paginator(movimientos, 25).get_page(request.GET.get("page"))
    return render(request, "webapp/movimientos_list.html", context)


@role_required(ROLE_ADMIN, ROLE_STAFF_FINANZAS)
def movimiento_create(request):
    context = _nav_context(request)
    if request.method == "POST":
        form = MovimientoCajaForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Movimiento registrado.")
            return redirect("webapp:movimientos_list")
    else:
        form = MovimientoCajaForm()
    context["form"] = form
    return render(request, "webapp/movimiento_form.html", context)


@role_required(ROLE_ADMIN, ROLE_STAFF_FINANZAS)
def finanzas_resumen(request):
    context = _nav_context(request)
    resumen_qs = MovimientoCaja.objects.values("fecha__year", "fecha__month").annotate(
        ingresos=Sum("monto_total", filter=Q(tipo=MovimientoCaja.Tipo.INGRESO)),
        egresos=Sum("monto_total", filter=Q(tipo=MovimientoCaja.Tipo.EGRESO)),
    )
    resumen = []
    for item in resumen_qs:
        ingresos = item["ingresos"] or 0
        egresos = item["egresos"] or 0
        item["saldo"] = ingresos - egresos
        resumen.append(item)
    context["resumen"] = resumen
    return render(request, "webapp/finanzas_resumen.html", context)


@role_required(ROLE_ADMIN, ROLE_STAFF_FINANZAS)
def finanzas_categorias(request):
    context = _nav_context(request)
    context["categorias"] = MovimientoCaja.Categoria.choices
    return render(request, "webapp/finanzas_categorias.html", context)


@role_required(ROLE_ADMIN, ROLE_STAFF_ASISTENCIA, ROLE_STAFF_FINANZAS)
def reportes_dashboard(request):
    context = _nav_context(request)
    total_asistencias = Asistencia.objects.count()
    ranking = (
        Asistencia.objects.values("persona__nombres", "persona__apellidos")
        .annotate(total=Count("id"))
        .order_by("-total")[:5]
    )
    context.update(
        {
            "total_asistencias": total_asistencias,
            "ranking": ranking,
            "ingresos_mes": MovimientoCaja.objects.filter(tipo=MovimientoCaja.Tipo.INGRESO).aggregate(total=Sum("monto_total"))["total"] or 0,
        }
    )
    return render(request, "webapp/reportes_dashboard.html", context)


@role_required(ROLE_ADMIN, ROLE_STAFF_ASISTENCIA, ROLE_STAFF_FINANZAS)
def reportes_exportar(request):
    messages.info(request, "La exportación estará disponible próximamente.")
    return redirect("webapp:reportes_dashboard")


@role_required(ROLE_ADMIN)
def importaciones_dashboard(request):
    context = _nav_context(request)
    context["comandos"] = [
        "python manage.py import_inscripciones",
        "python manage.py import_asistencias",
        "python manage.py import_libro_caja",
    ]
    return render(request, "webapp/importaciones.html", context)


@role_required(ROLE_ADMIN)
def importaciones_historial(request):
    context = _nav_context(request)
    context["eventos"] = []
    return render(request, "webapp/importaciones_historial.html", context)


@role_required(ROLE_ADMIN)
def configuracion(request):
    context = _nav_context(request)
    context["organizaciones"] = Organizacion.objects.all()
    return render(request, "webapp/configuracion.html", context)


@role_required(ROLE_ADMIN)
def usuarios_list(request):
    context = _nav_context(request)
    User = get_user_model()
    context["usuarios"] = User.objects.all()
    return render(request, "webapp/usuarios_list.html", context)


@role_required(ROLE_ADMIN)
def auditoria_log(request):
    context = _nav_context(request)
    context["eventos"] = []
    return render(request, "webapp/auditoria.html", context)

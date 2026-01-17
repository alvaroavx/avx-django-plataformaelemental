from datetime import timedelta

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from academia.models import Disciplina, SesionClase
from asistencias.models import Asistencia
from cobros.models import DocumentoVenta, Pago, Suscripcion
from cuentas.models import Persona
from finanzas.models import LiquidacionProfesor, MovimientoCaja
from organizaciones.models import Organizacion

from .decorators import role_required
from .forms import AsistenciaRapidaForm, AsistenciaSesionForm, PagoRapidoForm, SesionRapidaForm
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
    sesiones_mes = (
        SesionClase.objects.filter(fecha__gte=inicio_mes)
        .select_related("disciplina", "profesor")
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
        }
    )
    return render(request, "webapp/dashboard.html", context)


@role_required(ROLE_ADMIN)
def sesiones_list(request):
    context = _nav_context(request)
    sesiones = SesionClase.objects.select_related("disciplina", "profesor").prefetch_related("profesores").order_by("-fecha")
    filtro_disciplina = request.GET.get("disciplina")
    if filtro_disciplina:
        sesiones = sesiones.filter(disciplina_id=filtro_disciplina)
    context["sesiones"] = Paginator(sesiones, 20).get_page(request.GET.get("page"))
    context["disciplinas"] = Disciplina.objects.all()
    return render(request, "webapp/sesiones_list.html", context)


@role_required(ROLE_ADMIN)
def sesion_asistencia(request, pk):
    context = _nav_context(request)
    sesion = get_object_or_404(SesionClase.objects.select_related("disciplina"), pk=pk)
    asistencias = Asistencia.objects.filter(sesion=sesion).select_related("persona", "convenio")
    personas_recientes = _personas_recientes()
    if request.method == "POST":
        form = AsistenciaRapidaForm(request.POST)
        form.fields["persona"].queryset = personas_recientes
        if form.is_valid():
            asistencia = form.save(commit=False)
            asistencia.sesion = sesion
            asistencia.save()
            messages.success(request, "Asistencia registrada.")
            return redirect("webapp:sesion_asistencia", pk=pk)
    else:
        form = AsistenciaRapidaForm()
        form.fields["persona"].queryset = personas_recientes
    context.update(
        {
            "sesion": sesion,
            "form": form,
            "asistencias": asistencias,
            "contador_asistentes": asistencias.count(),
        }
    )
    return render(request, "webapp/sesion_asistencia.html", context)


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
                disciplina_nombre = form.cleaned_data["disciplina_nombre"].strip()
                if not disciplina:
                    if not disciplina_nombre:
                        messages.error(request, "Debes seleccionar o escribir una disciplina.")
                        return redirect("webapp:sesion_rapida")
                    organizacion = Organizacion.objects.first()
                    disciplina, _ = Disciplina.objects.get_or_create(
                        organizacion=organizacion,
                        nombre=disciplina_nombre,
                    )
                fecha = form.cleaned_data["fecha"] or timezone.localdate()
                sesion = SesionClase.objects.create(
                    disciplina=disciplina,
                    profesor=form.cleaned_data["profesor"],
                    fecha=fecha,
                    cupo_maximo=form.cleaned_data["cupo_maximo"],
                    notas=form.cleaned_data["notas"],
                )
                if form.cleaned_data["profesores"]:
                    sesion.profesores.set(form.cleaned_data["profesores"])
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
    estudiantes = Persona.objects.filter(roles__rol__codigo="estudiante").distinct()
    organizaciones = Organizacion.objects.all()
    org_id = request.GET.get("organizacion")
    if org_id:
        estudiantes = estudiantes.filter(suscripciones__plan__organizacion_id=org_id)
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
    profesores = Persona.objects.filter(roles__rol__codigo="profesor").distinct()
    org_id = request.GET.get("organizacion")
    if org_id:
        profesores = profesores.filter(sesiones_impartidas__disciplina__organizacion_id=org_id).distinct()
    context["profesores"] = profesores
    context["organizaciones"] = Organizacion.objects.all()
    return render(request, "webapp/profesores_list.html", context)


@role_required(ROLE_ADMIN)
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
def asistencias_list(request):
    context = _nav_context(request)
    asistencias = Asistencia.objects.select_related("sesion", "persona", "sesion__disciplina").order_by("-registrada_en")
    disciplina_id = request.GET.get("disciplina")
    persona_id = request.GET.get("persona")
    mes = request.GET.get("mes")
    if disciplina_id:
        asistencias = asistencias.filter(sesion__disciplina_id=disciplina_id)
    if persona_id:
        asistencias = asistencias.filter(persona_id=persona_id)
    if mes:
        asistencias = asistencias.filter(sesion__fecha__month=mes)
    asistencia_form = AsistenciaSesionForm()
    personas_recientes = _personas_recientes()
    asistencia_form.fields["persona"].queryset = personas_recientes
    asistencia_form.fields["sesion"].queryset = SesionClase.objects.order_by("-fecha")[:50]
    pago_form = PagoRapidoForm()
    if request.method == "POST":
        if "registrar_asistencia" in request.POST:
            asistencia_form = AsistenciaSesionForm(request.POST)
            asistencia_form.fields["persona"].queryset = personas_recientes
            asistencia_form.fields["sesion"].queryset = SesionClase.objects.order_by("-fecha")[:50]
            if asistencia_form.is_valid():
                asistencia_form.save()
                messages.success(request, "Asistencia registrada.")
                return redirect("webapp:asistencias_list")
        elif "registrar_pago" in request.POST:
            pago_form = PagoRapidoForm(request.POST)
            if pago_form.is_valid():
                pago_form.save()
                messages.success(request, "Pago registrado.")
                return redirect("webapp:asistencias_list")
    context.update(
        {
            "asistencias": Paginator(asistencias, 25).get_page(request.GET.get("page")),
            "disciplinas": Disciplina.objects.all(),
            "personas": Persona.objects.all(),
            "meses": list(range(1, 13)),
            "asistencia_form": asistencia_form,
            "pago_form": pago_form,
        }
    )
    return render(request, "webapp/asistencias_list.html", context)


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

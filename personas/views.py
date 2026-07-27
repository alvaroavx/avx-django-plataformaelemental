from decimal import Decimal

from functools import wraps

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.db.models import Count, DateField, DecimalField, ExpressionWrapper, F, IntegerField, OuterRef, Prefetch, Q, Subquery, Sum, Value
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404, redirect, render
from django.http import Http404
from django.core.exceptions import ValidationError
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.urls import reverse

from auditoria.models import AuditLog
from auditoria.services import registrar_auditoria, registrar_cambio
from asistencias.decorators import role_required
from asistencias.models import Asistencia, Disciplina, SesionClase
from asistencias.utils import ROLE_ADMIN
from finanzas.models import AttendanceConsumption, Payment
from finanzas.services import asociar_asistencia_a_pago, resumen_financiero_estudiante
from plataformaelemental.context import (
    aplicar_periodo,
    descripcion_periodo,
    filtros_periodo,
    nav_context,
    organizacion_desde_request,
    organizaciones_visibles_para_usuario,
    resolver_periodo,
)

from .forms import OrganizacionCRMForm, PersonaCRMForm, PersonaRolCRMForm, ResolverSolicitudAccesoForm
from .models import Organizacion, Persona, PersonaRol, Rol, SolicitudAcceso
from .resolucion_solicitudes import aprobar_solicitud, rechazar_solicitud, reabrir_solicitud
from .solicitudes_acceso import crear_o_recuperar_solicitud, obtener_identidad_pendiente, solicitud_pendiente_o_ultima


MONEY_FIELD = DecimalField(max_digits=12, decimal_places=2)
PERSONA_AUDIT_FIELDS = ["nombres", "apellidos", "rut", "email", "telefono", "activo"]
PERSONA_ROL_AUDIT_FIELDS = ["activo", "valor_clase", "retencion_sii"]


def solicitud_acceso(request):
    from django.conf import settings

    if not settings.ACCESS_REQUESTS_ENABLED:
        raise Http404
    identidad = obtener_identidad_pendiente(request)
    if not identidad:
        return redirect("login")
    solicitud = solicitud_pendiente_o_ultima(identidad)
    creada = None
    if request.method == "POST":
        try:
            solicitud, creada = crear_o_recuperar_solicitud(request, identidad)
        except ValidationError as error:
            messages.error(request, error.messages[0])
    return render(
        request,
        "personas/solicitud_acceso.html",
        {"hide_nav": True, "identidad": identidad, "solicitud": solicitud, "creada": creada},
    )


def _gestionar_solicitudes_requerido(view):
    @login_required
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        from django.conf import settings

        if not settings.ACCESS_REQUESTS_ENABLED:
            raise Http404
        if not request.user.has_perm("personas.gestionar_solicitudes_acceso"):
            registrar_auditoria(
                usuario=request.user,
                accion=AuditLog.ACCION_ASOCIAR,
                dominio="personas",
                modelo="personas.SolicitudAcceso",
                objeto_id=str(kwargs.get("pk", "")),
                resumen="Acceso a gestión de solicitudes denegado",
                metadata={"denegado": True},
            )
            raise PermissionDenied("No tienes permiso para gestionar solicitudes de acceso.")
        return view(request, *args, **kwargs)

    return wrapped


def _termino_busqueda(request, nombre):
    return (request.GET.get(nombre) or "").strip()


def _candidatos_resolucion(request):
    """Busca de forma acotada; el formulario nunca expone directorios completos."""
    termino_usuario = _termino_busqueda(request, "usuario_q")
    termino_persona = _termino_busqueda(request, "persona_q")
    User = get_user_model()
    usuarios = User.objects.none()
    personas = Persona.objects.none()
    if len(termino_usuario) >= 2:
        usuarios = (
            User.objects.filter(is_active=True)
            .filter(
                Q(username__icontains=termino_usuario)
                | Q(email__icontains=termino_usuario)
                | Q(first_name__icontains=termino_usuario)
                | Q(last_name__icontains=termino_usuario)
            )
            .select_related("persona")
            .prefetch_related("persona__roles__rol", "persona__roles__organizacion")
            .order_by("username")[:10]
        )
    if len(termino_persona) >= 2:
        personas = (
            Persona.objects.filter(user__isnull=True, activo=True)
            .filter(Q(nombres__icontains=termino_persona) | Q(apellidos__icontains=termino_persona) | Q(email__icontains=termino_persona))
            .prefetch_related("roles__rol", "roles__organizacion")
            .order_by("apellidos", "nombres")[:10]
        )
    return termino_usuario, termino_persona, usuarios, personas


def _formulario_resolucion(request, *, data=None):
    """En POST se valida solo el id enviado, sin cargar directorios completos."""
    User = get_user_model()
    usuarios = User.objects.none()
    personas = Persona.objects.none()
    if data is not None:
        if data.get("usuario"):
            usuarios = User.objects.filter(pk=data.get("usuario"), is_active=True).select_related("persona")
        if data.get("persona"):
            personas = Persona.objects.filter(pk=data.get("persona"), user__isnull=True, activo=True)
    else:
        _, _, usuarios, personas = _candidatos_resolucion(request)
    return ResolverSolicitudAccesoForm(data, usuarios=usuarios, personas=personas)


def _contexto_detalle_solicitud(request, solicitud, *, form=None, conflicto=None, modificado_por_otro=False):
    termino_usuario, termino_persona, usuarios, personas = _candidatos_resolucion(request)
    if form is None:
        form = ResolverSolicitudAccesoForm(usuarios=usuarios, personas=personas)
    return {
        "solicitud": solicitud,
        "form": form,
        "usuarios_encontrados": usuarios,
        "personas_encontradas": personas,
        "usuario_q": termino_usuario,
        "persona_q": termino_persona,
        "conflicto": conflicto,
        "modificado_por_otro": modificado_por_otro,
        "pendientes_count": SolicitudAcceso.objects.filter(estado=SolicitudAcceso.Estado.PENDIENTE).count(),
    }


@_gestionar_solicitudes_requerido
def solicitudes_acceso_list(request):
    estado = (request.GET.get("estado") or "PENDIENTE").upper()
    termino = (request.GET.get("q") or "").strip()
    solicitudes = SolicitudAcceso.objects.select_related("usuario_resuelto", "organizacion_resuelta", "rol_resuelto", "resuelta_por")
    if estado in dict(SolicitudAcceso.Estado.choices):
        solicitudes = solicitudes.filter(estado=estado)
    else:
        estado = ""
    if termino:
        solicitudes = solicitudes.filter(Q(email__icontains=termino) | Q(nombre__icontains=termino) | Q(provider_subject__icontains=termino))
    paginator = Paginator(solicitudes, 25)
    page_obj = paginator.get_page(request.GET.get("page"))
    parametros = request.GET.copy()
    parametros.pop("page", None)
    return render(
        request,
        "personas/solicitudes_acceso_list.html",
        {
            "page_obj": page_obj,
            "solicitudes": page_obj.object_list,
            "estado": estado,
            "q": termino,
            "querystring_sin_page": parametros.urlencode(),
            "pendientes_count": SolicitudAcceso.objects.filter(estado=SolicitudAcceso.Estado.PENDIENTE).count(),
        },
    )


@_gestionar_solicitudes_requerido
def solicitud_acceso_detail(request, pk):
    solicitud = get_object_or_404(
        SolicitudAcceso.objects.select_related("usuario_resuelto__persona", "organizacion_resuelta", "rol_resuelto", "resuelta_por"), pk=pk
    )
    return render(request, "personas/solicitud_acceso_detail.html", _contexto_detalle_solicitud(request, solicitud))


@_gestionar_solicitudes_requerido
def solicitud_acceso_aprobar(request, pk):
    from django.conf import settings

    if request.method != "POST":
        raise Http404
    if not settings.ACCESS_REQUEST_APPROVAL_ENABLED:
        raise Http404
    form = _formulario_resolucion(request, data=request.POST)
    if not form.is_valid():
        return render(request, "personas/solicitud_acceso_detail.html", _contexto_detalle_solicitud(request, get_object_or_404(SolicitudAcceso, pk=pk), form=form), status=400)
    try:
        aprobar_solicitud(solicitud_id=pk, administrador=request.user, **form.cleaned_data)
    except ValidationError as error:
        form.add_error(None, error)
        solicitud = get_object_or_404(SolicitudAcceso, pk=pk)
        return render(request, "personas/solicitud_acceso_detail.html", _contexto_detalle_solicitud(request, solicitud, form=form, conflicto=error.messages[0], modificado_por_otro=solicitud.estado != SolicitudAcceso.Estado.PENDIENTE), status=409 if solicitud.estado != SolicitudAcceso.Estado.PENDIENTE else 400)
    messages.success(request, "Solicitud aprobada. El vínculo Google se completará en el próximo ingreso validado.")
    return redirect("personas:solicitud_acceso_detail", pk=pk)


@_gestionar_solicitudes_requerido
def solicitud_acceso_rechazar(request, pk):
    from django.conf import settings

    if request.method != "POST" or not settings.ACCESS_REQUEST_APPROVAL_ENABLED:
        raise Http404
    try:
        rechazar_solicitud(solicitud_id=pk, administrador=request.user, motivo_rechazo=request.POST.get("motivo_rechazo", ""))
    except ValidationError as error:
        solicitud = get_object_or_404(SolicitudAcceso, pk=pk)
        return render(request, "personas/solicitud_acceso_detail.html", _contexto_detalle_solicitud(request, solicitud, conflicto=error.messages[0], modificado_por_otro=solicitud.estado != SolicitudAcceso.Estado.PENDIENTE), status=409 if solicitud.estado != SolicitudAcceso.Estado.PENDIENTE else 400)
    messages.success(request, "Solicitud rechazada.")
    return redirect("personas:solicitud_acceso_detail", pk=pk)


@_gestionar_solicitudes_requerido
def solicitud_acceso_reabrir(request, pk):
    from django.conf import settings

    if request.method != "POST" or not settings.ACCESS_REQUEST_APPROVAL_ENABLED:
        raise Http404
    try:
        reabrir_solicitud(solicitud_id=pk, administrador=request.user, nota_interna=request.POST.get("nota_interna", ""))
    except ValidationError as error:
        solicitud = get_object_or_404(SolicitudAcceso, pk=pk)
        return render(request, "personas/solicitud_acceso_detail.html", _contexto_detalle_solicitud(request, solicitud, conflicto=error.messages[0], modificado_por_otro=solicitud.estado != SolicitudAcceso.Estado.RECHAZADA), status=409 if solicitud.estado != SolicitudAcceso.Estado.RECHAZADA else 400)
    messages.success(request, "Solicitud reabierta y devuelta a pendiente.")
    return redirect("personas:solicitud_acceso_detail", pk=pk)


def _base_context(request):
    return nav_context(request)


def _url_con_filtros(request, nombre_url, **kwargs):
    url = reverse(nombre_url, kwargs=kwargs or None)
    query = request.GET.urlencode()
    return f"{url}?{query}" if query else url


def _snapshot_persona(persona):
    return {campo: getattr(persona, campo) for campo in PERSONA_AUDIT_FIELDS}


def _snapshot_persona_rol(persona_rol):
    return {campo: getattr(persona_rol, campo) for campo in PERSONA_ROL_AUDIT_FIELDS}


def _auditar_persona_rol(request, persona_rol, *, created, antes=None):
    metadata = {
        "persona_id": persona_rol.persona_id,
        "rol_id": persona_rol.rol_id,
        "rol_codigo": persona_rol.rol.codigo,
        "organizacion_id": persona_rol.organizacion_id,
    }
    if created:
        registrar_auditoria(
            usuario=request.user,
            accion=AuditLog.ACCION_ASOCIAR,
            dominio="personas",
            objeto=persona_rol,
            organizacion=persona_rol.organizacion,
            resumen="Rol agregado a persona",
            metadata=metadata,
        )
        return
    if antes is not None:
        registrar_cambio(
            usuario=request.user,
            dominio="personas",
            objeto=persona_rol,
            organizacion=persona_rol.organizacion,
            resumen="Rol de persona actualizado",
            antes=antes,
            despues=_snapshot_persona_rol(persona_rol),
            campos=PERSONA_ROL_AUDIT_FIELDS,
            metadata=metadata,
        )


def _guardar_persona_rol_desde_form(persona, rol_form):
    rol = rol_form.cleaned_data["rol"]
    organizacion = rol_form.cleaned_data["organizacion"]
    valor_clase = rol_form.cleaned_data.get("valor_clase")
    retencion_sii = rol_form.cleaned_data.get("retencion_sii")
    persona_rol, created = PersonaRol.objects.get_or_create(
        persona=persona,
        rol=rol,
        organizacion=organizacion,
        defaults={"activo": True, "valor_clase": valor_clase, "retencion_sii": retencion_sii},
    )
    cambios = []
    if not created and not persona_rol.activo:
        persona_rol.activo = True
        cambios.append("activo")
    if rol.codigo == "PROFESOR" and persona_rol.valor_clase != valor_clase:
        persona_rol.valor_clase = valor_clase
        cambios.append("valor_clase")
    if rol.codigo == "PROFESOR" and persona_rol.retencion_sii != retencion_sii:
        persona_rol.retencion_sii = retencion_sii
        cambios.append("retencion_sii")
    if rol.codigo != "PROFESOR" and persona_rol.valor_clase is not None:
        persona_rol.valor_clase = None
        cambios.append("valor_clase")
    if rol.codigo != "PROFESOR" and persona_rol.retencion_sii is not None:
        persona_rol.retencion_sii = None
        cambios.append("retencion_sii")
    if cambios:
        persona_rol.save(update_fields=cambios)
    return persona_rol, created


def _personas_queryset(organizacion=None):
    queryset = Persona.objects.select_related("user").prefetch_related(
        Prefetch(
            "roles",
            queryset=PersonaRol.objects.select_related("rol", "organizacion").order_by(
                "organizacion__nombre",
                "rol__nombre",
            ),
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


def _organizacion_metricas(organizacion, *, mes=None, anio=None):
    roles_qs = PersonaRol.objects.filter(organizacion=organizacion, activo=True)
    sesiones_qs = aplicar_periodo(
        SesionClase.objects.filter(disciplina__organizacion=organizacion),
        "fecha",
        mes=mes,
        anio=anio,
    )
    pagos_qs = aplicar_periodo(
        Payment.objects.filter(organizacion=organizacion, revertido_en__isnull=True),
        "fecha_pago",
        mes=mes,
        anio=anio,
    )
    asistencias_qs = aplicar_periodo(
        Asistencia.objects.filter(sesion__disciplina__organizacion=organizacion),
        "sesion__fecha",
        mes=mes,
        anio=anio,
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


def _annotate_personas_resumen(queryset, *, mes=None, anio=None, organizacion=None):
    asistencias_qs = Asistencia.objects.filter(
        persona=OuterRef("pk"),
        **filtros_periodo("sesion__fecha", mes=mes, anio=anio),
    )
    pagos_qs = Payment.objects.filter(
        persona=OuterRef("pk"),
        revertido_en__isnull=True,
        **filtros_periodo("fecha_pago", mes=mes, anio=anio),
    )
    consumos_qs = AttendanceConsumption.objects.filter(
        persona=OuterRef("pk"),
        **filtros_periodo("clase_fecha", mes=mes, anio=anio),
    )
    sesiones_profesor_qs = SesionClase.objects.filter(
        profesores=OuterRef("pk"),
        **filtros_periodo("fecha", mes=mes, anio=anio),
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
    periodo = resolver_periodo(request)
    organizacion = organizacion_desde_request(request)

    personas_qs = _annotate_personas_resumen(
        _personas_queryset(organizacion),
        mes=periodo["mes"],
        anio=periodo["anio"],
        organizacion=organizacion,
    )
    pagos_qs = aplicar_periodo(
        Payment.objects.filter(revertido_en__isnull=True),
        "fecha_pago",
        request=request,
    )
    consumos_qs = aplicar_periodo(AttendanceConsumption.objects.all(), "clase_fecha", request=request)
    asistencias_qs = aplicar_periodo(Asistencia.objects.all(), "sesion__fecha", request=request)
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
    periodo = resolver_periodo(request)
    organizacion_filtro = organizacion_desde_request(request)
    organizaciones_qs = Organizacion.objects.order_by("nombre")
    if organizacion_filtro:
        organizaciones_qs = organizaciones_qs.filter(pk=organizacion_filtro.pk)

    organizaciones = []
    for organizacion in organizaciones_qs:
        organizaciones.append(
            {
                "organizacion": organizacion,
                "metricas": _organizacion_metricas(organizacion, mes=periodo["mes"], anio=periodo["anio"]),
            }
        )

    context.update(
        {
            "organizaciones": organizaciones,
            "periodo_descripcion_vista": descripcion_periodo(request=request, corta=False),
        }
    )
    return render(request, "personas/organizaciones_list.html", context)


@role_required(ROLE_ADMIN)
def organizacion_detail(request, pk):
    context = _base_context(request)
    periodo = resolver_periodo(request)
    organizaciones_autorizadas = organizaciones_visibles_para_usuario(request.user)
    organizacion = get_object_or_404(organizaciones_autorizadas, pk=pk)
    disciplinas = Disciplina.objects.filter(organizacion=organizacion).order_by("nombre")
    metricas = _organizacion_metricas(organizacion, mes=periodo["mes"], anio=periodo["anio"])
    context.update(
        {
            "organizacion_obj": organizacion,
            "metricas": metricas,
            "disciplinas": disciplinas[:8],
            "pagos_recientes": Payment.objects.filter(
                organizacion=organizacion,
                revertido_en__isnull=True,
            ).select_related("persona").order_by("-fecha_pago", "-id")[:8],
            "periodo_descripcion_vista": descripcion_periodo(request=request, corta=False),
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
    organizacion = get_object_or_404(organizaciones_visibles_para_usuario(request.user), pk=pk)
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
    periodo = resolver_periodo(request)
    organizacion = organizacion_desde_request(request)
    personas_qs = _personas_queryset(organizacion)

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
            | Q(rut__icontains=q)
        )
    if rol:
        personas_qs = personas_qs.filter(roles__rol__codigo=rol)
    if estado == "activas":
        personas_qs = personas_qs.filter(activo=True)
    elif estado == "inactivas":
        personas_qs = personas_qs.filter(activo=False)
    if con_usuario == "si":
        personas_qs = personas_qs.filter(user__isnull=False)
    elif con_usuario == "no":
        personas_qs = personas_qs.filter(user__isnull=True)
    if con_deuda == "si":
        personas_qs = _annotate_personas_resumen(
            personas_qs,
            mes=periodo["mes"],
            anio=periodo["anio"],
            organizacion=organizacion,
        )
        personas_qs = personas_qs.filter(deuda_periodo__gt=0)
    elif con_deuda == "no":
        personas_qs = _annotate_personas_resumen(
            personas_qs,
            mes=periodo["mes"],
            anio=periodo["anio"],
            organizacion=organizacion,
        )
        personas_qs = personas_qs.filter(deuda_periodo=0)

    personas_qs = personas_qs.order_by("apellidos", "nombres", "pk").distinct()
    paginator = Paginator(personas_qs, 25)
    page_obj = paginator.get_page(request.GET.get("page"))
    page_ids = list(page_obj.object_list.values_list("pk", flat=True))
    personas_pagina = []
    if page_ids:
        personas_pagina = list(
            _annotate_personas_resumen(
                _personas_queryset(organizacion).filter(pk__in=page_ids),
                mes=periodo["mes"],
                anio=periodo["anio"],
                organizacion=organizacion,
            ).order_by("apellidos", "nombres", "pk")
        )
    page_obj.object_list = personas_pagina
    query_params = request.GET.copy()
    query_params.pop("page", None)

    context.update(
        {
            "personas": personas_pagina,
            "page_obj": page_obj,
            "paginator": paginator,
            "total_resultados": paginator.count,
            "querystring_sin_page": query_params.urlencode(),
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
    organizaciones_autorizadas = organizaciones_visibles_para_usuario(request.user)
    form = PersonaCRMForm(request.POST or None)
    rol_form = PersonaRolCRMForm(request.POST or None, prefix="rol", organizaciones=organizaciones_autorizadas)
    if request.method == "POST":
        persona_valida = form.is_valid()
        rol_valido = rol_form.is_valid()
        if persona_valida and rol_valido:
            persona = form.save()
            persona_rol = None
            rol_created = False
            if rol_valido and rol_form.cleaned_data.get("rol") and rol_form.cleaned_data.get("organizacion"):
                persona_rol, rol_created = _guardar_persona_rol_desde_form(persona, rol_form)
            registrar_auditoria(
                usuario=request.user,
                accion=AuditLog.ACCION_CREAR,
                dominio="personas",
                objeto=persona,
                organizacion=persona_rol.organizacion if persona_rol else None,
                resumen="Persona creada",
                metadata={
                    "persona_id": persona.pk,
                    "rol_id": persona_rol.rol_id if persona_rol else None,
                    "organizacion_id": persona_rol.organizacion_id if persona_rol else None,
                },
            )
            if persona_rol:
                _auditar_persona_rol(request, persona_rol, created=rol_created)
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
    periodo = resolver_periodo(request)
    organizacion = organizacion_desde_request(request)
    organizaciones_autorizadas = organizaciones_visibles_para_usuario(request.user)
    roles_visibles = PersonaRol.objects.select_related("rol", "organizacion").order_by("organizacion__nombre", "rol__nombre")
    if organizacion:
        roles_visibles = roles_visibles.filter(organizacion=organizacion)
    persona = get_object_or_404(
        Persona.objects.select_related("user").prefetch_related(
            Prefetch(
                "roles",
                queryset=roles_visibles,
            ),
            Prefetch(
                "asistencias",
                queryset=Asistencia.objects.select_related(
                    "sesion__disciplina__organizacion",
                    "consumo_financiero__pago",
                ).order_by("-sesion__fecha"),
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
    if not (request.user.is_superuser or request.user.is_staff) and not persona.roles.filter(organizacion=organizacion).exists():
        raise Http404
    if request.method == "POST":
        accion = request.POST.get("accion")
        if "asociar_pago_asistencia" in request.POST:
            asistencia = get_object_or_404(
                Asistencia.objects.select_related("sesion__disciplina", "consumo_financiero__pago"),
                pk=request.POST.get("asistencia_id"),
                persona=persona,
            )
            pago = get_object_or_404(
                Payment,
                pk=request.POST.get("pago_id"),
                persona=persona,
                revertido_en__isnull=True,
                **filtros_periodo("fecha_pago", request=request),
            )
            if organizacion and asistencia.sesion.disciplina.organizacion_id != organizacion.id:
                messages.error(request, "La asistencia seleccionada no pertenece a la organización filtrada.")
                return redirect(_url_con_filtros(request, "personas:persona_detail", pk=persona.pk))
            if organizacion and pago.organizacion_id != organizacion.id:
                messages.error(request, "El pago seleccionado no pertenece a la organizacion filtrada.")
                return redirect(_url_con_filtros(request, "personas:persona_detail", pk=persona.pk))
            try:
                asociar_asistencia_a_pago(asistencia, pago)
            except ValueError as exc:
                messages.error(request, str(exc))
            else:
                messages.success(request, "Asistencia asociada al pago correctamente.")
            return redirect(_url_con_filtros(request, "personas:persona_detail", pk=persona.pk))
        if accion == "agregar_rol":
            rol_form_post = PersonaRolCRMForm(request.POST, prefix="rol", organizaciones=organizaciones_autorizadas)
            if rol_form_post.is_valid() and rol_form_post.cleaned_data.get("rol") and rol_form_post.cleaned_data.get("organizacion"):
                persona_rol_existente = PersonaRol.objects.filter(
                    persona=persona,
                    rol=rol_form_post.cleaned_data["rol"],
                    organizacion=rol_form_post.cleaned_data["organizacion"],
                ).first()
                antes = _snapshot_persona_rol(persona_rol_existente) if persona_rol_existente else None
                persona_rol, created = _guardar_persona_rol_desde_form(persona, rol_form_post)
                _auditar_persona_rol(request, persona_rol, created=created, antes=antes)
                if not created and not persona_rol.activo:
                    messages.success(request, "Rol reactivado para la persona.")
                elif created:
                    messages.success(request, "Rol agregado a la persona.")
                elif persona_rol.rol.codigo == "PROFESOR":
                    messages.success(request, "Rol de profesor actualizado para la persona.")
                else:
                    messages.info(request, "Ese rol ya estaba activo para la persona.")
                return redirect(_url_con_filtros(request, "personas:persona_detail", pk=persona.pk))
            elif rol_form_post.is_valid():
                messages.warning(request, "Debes seleccionar un rol y una organizacion para agregar la asignacion.")
            else:
                messages.error(request, "No se pudo agregar el rol. Revisa rol y organizacion.")
        elif accion == "guardar_configuracion_profesor":
            persona_rol = get_object_or_404(PersonaRol, pk=request.POST.get("persona_rol_id"), persona=persona, organizacion=organizacion)
            if persona_rol.rol.codigo != "PROFESOR":
                messages.warning(request, "Solo los roles de profesor permiten configurar valor por clase.")
                return redirect(_url_con_filtros(request, "personas:persona_detail", pk=persona.pk))
            valor_clase_raw = (request.POST.get("valor_clase") or "").strip()
            retencion_sii_raw = (request.POST.get("retencion_sii") or "").strip()
            antes = _snapshot_persona_rol(persona_rol)
            persona_rol.valor_clase = Decimal(valor_clase_raw) if valor_clase_raw else None
            persona_rol.retencion_sii = Decimal(retencion_sii_raw) if retencion_sii_raw else None
            persona_rol.save(update_fields=["valor_clase", "retencion_sii"])
            _auditar_persona_rol(request, persona_rol, created=False, antes=antes)
            messages.success(request, "Configuración de honorarios actualizada.")
            return redirect(_url_con_filtros(request, "personas:persona_detail", pk=persona.pk))
        elif accion == "cambiar_estado_sesion":
            estado = request.POST.get("estado")
            if estado not in dict(SesionClase.Estado.choices):
                messages.warning(request, "Estado de sesión inválido.")
                return redirect(_url_con_filtros(request, "personas:persona_detail", pk=persona.pk))
            sesion = get_object_or_404(
                SesionClase.objects.select_related("disciplina__organizacion"),
                pk=request.POST.get("sesion_id"),
                profesores=persona,
            )
            if organizacion and sesion.disciplina.organizacion_id != organizacion.id:
                messages.error(request, "La sesión no pertenece a la organización filtrada.")
                return redirect(_url_con_filtros(request, "personas:persona_detail", pk=persona.pk))
            estado_anterior = sesion.estado
            sesion.estado = estado
            sesion.save(update_fields=["estado"])
            registrar_cambio(
                usuario=request.user,
                dominio="asistencias",
                objeto=sesion,
                organizacion=sesion.disciplina.organizacion,
                resumen="Estado de sesión actualizado desde perfil profesor",
                antes={"estado": estado_anterior},
                despues={"estado": sesion.estado},
                campos=["estado"],
                accion=AuditLog.ACCION_CAMBIAR_ESTADO,
                metadata={"sesion_id": sesion.pk, "profesor_id": persona.pk},
            )
            messages.success(request, "Estado de la sesión actualizado.")
            return redirect(_url_con_filtros(request, "personas:persona_detail", pk=persona.pk))
        elif accion == "toggle_rol":
            persona_rol = get_object_or_404(PersonaRol, pk=request.POST.get("persona_rol_id"), persona=persona, organizacion=organizacion)
            antes = _snapshot_persona_rol(persona_rol)
            persona_rol.activo = not persona_rol.activo
            persona_rol.save(update_fields=["activo"])
            _auditar_persona_rol(request, persona_rol, created=False, antes=antes)
            messages.success(request, "Estado del rol actualizado.")
            return redirect(_url_con_filtros(request, "personas:persona_detail", pk=persona.pk))
    # La pre-carga está acotada al filtro efectivo. Esto evita exponer los
    # roles de otra organización cuando una Persona participa en más de una.
    roles_asignados = list(persona.roles.all())
    asistencias = persona.asistencias.all()
    pagos = persona.pagos_financieros.all()
    consumos = persona.consumos_asistencia.all()
    sesiones_profesor = (
        SesionClase.objects.filter(
            profesores=persona,
        )
        .select_related("disciplina__organizacion")
        .prefetch_related("profesores")
        .order_by("-fecha")
    )
    sesiones_profesor = aplicar_periodo(sesiones_profesor, "fecha", request=request)
    if organizacion:
        asistencias = asistencias.filter(sesion__disciplina__organizacion=organizacion)
        pagos = pagos.filter(organizacion=organizacion)
        consumos = consumos.filter(asistencia__sesion__disciplina__organizacion=organizacion)
        sesiones_profesor = sesiones_profesor.filter(disciplina__organizacion=organizacion)
    asistencias = aplicar_periodo(asistencias, "sesion__fecha", request=request)
    pagos = aplicar_periodo(pagos, "fecha_pago", request=request)
    consumos = aplicar_periodo(consumos, "clase_fecha", request=request)

    roles_codigos = {item.rol.codigo for item in roles_asignados if item.activo}
    es_estudiante = "ESTUDIANTE" in roles_codigos
    es_profesor = "PROFESOR" in roles_codigos
    pagos_vigentes = pagos.filter(revertido_en__isnull=True)
    documentos_tributarios = [pago.documento_tributario for pago in pagos if pago.documento_tributario_id]
    finanzas_resumen = resumen_financiero_estudiante(persona, organizacion) if es_estudiante else None
    if es_estudiante:
        pagos_asociables_periodo = list(
            pagos_vigentes.annotate(
                clases_consumidas_total=Count(
                    "consumos",
                    filter=Q(consumos__estado=AttendanceConsumption.Estado.CONSUMIDO),
                    distinct=True,
                )
            )
            .annotate(
                saldo_clases_total=ExpressionWrapper(
                    F("clases_asignadas") - F("clases_consumidas_total"),
                    output_field=IntegerField(),
                )
            )
            .order_by("-fecha_pago", "-id")
        )
        for asistencia in asistencias:
            consumo = getattr(asistencia, "consumo_financiero", None)
            pago_actual_id = consumo.pago_id if consumo and consumo.pago_id else None
            asistencia.pagos_asociables = [
                pago
                for pago in pagos_asociables_periodo
                if pago.organizacion_id == asistencia.sesion.disciplina.organizacion_id
                and (pago.saldo_clases_total > 0 or pago.pk == pago_actual_id)
            ]
            asistencia.consumo_financiero_actual = consumo
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
    mostrar_bloque_estudiante = es_estudiante or asistencias.exists() or pagos.exists() or consumos.exists() or bool(documentos_tributarios)
    mostrar_bloque_profesor = es_profesor or sesiones_profesor.exists()
    sesiones_profesor_total = sesiones_profesor.count()
    sesiones_profesor_completadas = sesiones_profesor.filter(estado=SesionClase.Estado.COMPLETADA).count()
    asistentes_sesiones_profesor = sum(item.asistencias.count() for item in sesiones_profesor)
    roles_profesor = [item for item in roles_asignados if item.activo and item.rol.codigo == "PROFESOR"]
    if organizacion:
        roles_profesor = [item for item in roles_profesor if item.organizacion_id == organizacion.id]
    valor_clase_por_org = {item.organizacion_id: item.valor_clase for item in roles_profesor}
    retencion_sii_por_org = {item.organizacion_id: item.retencion_sii for item in roles_profesor}
    pago_bruto_profesor = Decimal("0")
    retenciones_configuradas = []
    for sesion in sesiones_profesor:
        valor_clase = valor_clase_por_org.get(sesion.disciplina.organizacion_id)
        if valor_clase is not None:
            pago_bruto_profesor += valor_clase * sesion.asistencias.count()
        retencion_item = retencion_sii_por_org.get(sesion.disciplina.organizacion_id)
        if retencion_item is not None:
            retenciones_configuradas.append(retencion_item)
    retenciones_distintas = sorted({item for item in retenciones_configuradas})
    retencion_sii_profesor = retenciones_distintas[0] if len(retenciones_distintas) == 1 else None
    retencion_sii_mixta = len(retenciones_distintas) > 1
    mostrar_pago_estimado_profesor = any(valor is not None for valor in valor_clase_por_org.values())
    monto_retencion_sii_profesor = None
    monto_neto_profesor = None
    if mostrar_pago_estimado_profesor and retencion_sii_profesor is not None:
        monto_retencion_sii_profesor = (pago_bruto_profesor * retencion_sii_profesor) / Decimal("100")
        monto_neto_profesor = pago_bruto_profesor - monto_retencion_sii_profesor

    context.update(
        {
            "persona_obj": persona,
            "roles_asignados": roles_asignados,
            "rol_form": PersonaRolCRMForm(prefix="rol", organizaciones=organizaciones_autorizadas),
            "asistencias": asistencias,
            "pagos": pagos,
            "consumos": consumos,
            "sesiones_profesor": sesiones_profesor,
            "documentos_tributarios": documentos_tributarios,
            "finanzas_resumen": finanzas_resumen,
            "monto_pagado": pagos_vigentes.aggregate(total=Sum("monto_total")).get("total") or 0,
            "consumos_consumidos": consumos.filter(estado=AttendanceConsumption.Estado.CONSUMIDO).count(),
            "consumos_pendientes": consumos.filter(estado=AttendanceConsumption.Estado.PENDIENTE).count(),
            "consumos_deuda": consumos.filter(estado=AttendanceConsumption.Estado.DEUDA).count(),
            "roles_codigos": roles_codigos,
            "es_estudiante": es_estudiante,
            "es_profesor": es_profesor,
            "mostrar_bloque_estudiante": mostrar_bloque_estudiante,
            "mostrar_bloque_profesor": mostrar_bloque_profesor,
            "sesiones_profesor_total": sesiones_profesor_total,
            "sesiones_profesor_completadas": sesiones_profesor_completadas,
            "asistentes_sesiones_profesor": asistentes_sesiones_profesor,
            "pago_bruto_profesor": pago_bruto_profesor,
            "mostrar_pago_estimado_profesor": mostrar_pago_estimado_profesor,
            "retencion_sii_profesor": retencion_sii_profesor,
            "retencion_sii_mixta": retencion_sii_mixta,
            "monto_retencion_sii_profesor": monto_retencion_sii_profesor,
            "monto_neto_profesor": monto_neto_profesor,
        }
    )
    return render(request, "personas/persona_detail.html", context)


@role_required(ROLE_ADMIN)
def persona_edit(request, pk):
    context = _base_context(request)
    organizaciones_autorizadas = organizaciones_visibles_para_usuario(request.user)
    organizacion = organizacion_desde_request(request)
    roles_visibles = PersonaRol.objects.select_related("rol", "organizacion").order_by("organizacion__nombre", "rol__nombre")
    if organizacion:
        roles_visibles = roles_visibles.filter(organizacion=organizacion)
    persona = get_object_or_404(
        Persona.objects.select_related("user").prefetch_related(
            Prefetch(
                "roles",
                queryset=roles_visibles,
            )
        ),
        pk=pk,
    )
    if not (request.user.is_superuser or request.user.is_staff) and not persona.roles.filter(organizacion=organizacion).exists():
        raise Http404
    form = PersonaCRMForm(request.POST or None, instance=persona)
    rol_form = PersonaRolCRMForm(prefix="rol", organizaciones=organizaciones_autorizadas)

    if request.method == "POST":
        accion = request.POST.get("accion")
        if accion == "guardar_persona":
            antes = _snapshot_persona(persona)
            form = PersonaCRMForm(request.POST, instance=persona)
            if form.is_valid():
                persona = form.save()
                registrar_cambio(
                    usuario=request.user,
                    dominio="personas",
                    objeto=persona,
                    organizacion=organizacion,
                    resumen="Persona actualizada",
                    antes=antes,
                    despues=_snapshot_persona(persona),
                    campos=PERSONA_AUDIT_FIELDS,
                )
                messages.success(request, "Perfil de persona actualizado.")
                return redirect(_url_con_filtros(request, "personas:persona_edit", pk=persona.pk))
        elif accion == "agregar_rol":
            rol_form = PersonaRolCRMForm(request.POST, prefix="rol", organizaciones=organizaciones_autorizadas)
            if rol_form.is_valid() and rol_form.cleaned_data.get("rol") and rol_form.cleaned_data.get("organizacion"):
                persona_rol_existente = PersonaRol.objects.filter(
                    persona=persona,
                    rol=rol_form.cleaned_data["rol"],
                    organizacion=rol_form.cleaned_data["organizacion"],
                ).first()
                antes = _snapshot_persona_rol(persona_rol_existente) if persona_rol_existente else None
                persona_rol, created = _guardar_persona_rol_desde_form(persona, rol_form)
                _auditar_persona_rol(request, persona_rol, created=created, antes=antes)
                if not created and not persona_rol.activo:
                    messages.success(request, "Rol reactivado para la persona.")
                elif created:
                    messages.success(request, "Rol agregado a la persona.")
                elif persona_rol.rol.codigo == "PROFESOR":
                    messages.success(request, "Rol de profesor actualizado para la persona.")
                else:
                    messages.info(request, "Ese rol ya estaba activo para la persona.")
                return redirect(_url_con_filtros(request, "personas:persona_edit", pk=persona.pk))
            elif rol_form.is_valid():
                messages.warning(request, "Debes seleccionar un rol y una organizacion para agregar la asignacion.")
            else:
                messages.error(request, "No se pudo agregar el rol. Revisa rol y organizacion.")
        elif accion == "guardar_configuracion_profesor":
            persona_rol = get_object_or_404(PersonaRol, pk=request.POST.get("persona_rol_id"), persona=persona, organizacion=organizacion)
            if persona_rol.rol.codigo != "PROFESOR":
                messages.warning(request, "Solo los roles de profesor permiten configurar valor por clase.")
                return redirect(_url_con_filtros(request, "personas:persona_edit", pk=persona.pk))
            valor_clase_raw = (request.POST.get("valor_clase") or "").strip()
            retencion_sii_raw = (request.POST.get("retencion_sii") or "").strip()
            antes = _snapshot_persona_rol(persona_rol)
            persona_rol.valor_clase = Decimal(valor_clase_raw) if valor_clase_raw else None
            persona_rol.retencion_sii = Decimal(retencion_sii_raw) if retencion_sii_raw else None
            persona_rol.save(update_fields=["valor_clase", "retencion_sii"])
            _auditar_persona_rol(request, persona_rol, created=False, antes=antes)
            messages.success(request, "Configuración de honorarios actualizada.")
            return redirect(_url_con_filtros(request, "personas:persona_edit", pk=persona.pk))
        elif accion == "toggle_rol":
            persona_rol = get_object_or_404(PersonaRol, pk=request.POST.get("persona_rol_id"), persona=persona, organizacion=organizacion)
            antes = _snapshot_persona_rol(persona_rol)
            persona_rol.activo = not persona_rol.activo
            persona_rol.save(update_fields=["activo"])
            _auditar_persona_rol(request, persona_rol, created=False, antes=antes)
            messages.success(request, "Estado del rol actualizado.")
            return redirect(_url_con_filtros(request, "personas:persona_edit", pk=persona.pk))

    context.update({"form": form, "rol_form": rol_form, "persona_obj": persona, "roles_asignados": persona.roles.all()})
    return render(request, "personas/persona_edit.html", context)

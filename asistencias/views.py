import calendar
import json
from datetime import date
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Count, Prefetch, Q, Sum
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from auditoria.models import AuditLog
from auditoria.services import registrar_auditoria, registrar_cambio
from finanzas.models import AttendanceConsumption, Payment
from personas.models import Organizacion, Persona, PersonaRol, Rol
from personas.search import filtrar_por_fragmentos
from personas.permissions import (
    ACCION_ADMINISTRAR_PERSONAS,
    ACCION_ADMINISTRAR_SESIONES,
    ACCION_EDITAR_ASISTENCIAS,
    ACCION_EXPORTAR_DATOS,
    ACCION_LIBERAR_CLASE,
    ACCION_OPERAR_PAGOS,
    ACCION_VER_SESION,
    ACCION_VER_FINANZAS,
    permiso_requerido,
    usuario_tiene_permiso,
)
from plataformaelemental.context import (
    aplicar_periodo,
    descripcion_periodo,
    filtros_periodo,
    nav_context,
    organizacion_desde_request,
    organizaciones_visibles_para_usuario,
    resolver_periodo,
)
from plataformaelemental.exports import periodo_sufijo_archivo, xlsx_response

from .decorators import role_required
from .forms import (
    AsistenciaMasivaForm,
    DisciplinaForm,
    PersonaRapidaForm,
    SesionBasicaForm,
    SesionesMasivasForm,
)
from .models import (
    AlumnoDisciplina,
    AsignacionProfesorDisciplina,
    Asistencia,
    ClaseLiberada,
    Disciplina,
    SesionClase,
)
from .profesor_contexto import resolver_contexto_profesor
from .selectors import (
    estudiantes_financieros_disciplina,
    asistencias_export_queryset,
    estudiantes_operativos_periodo,
    sesiones_visibles_para_usuario,
)
from .services.exportaciones import ASISTENCIAS_XLSX_HEADERS, filas_export_asistencias
from .services import (
    asegurar_asignaciones_profesores,
    asegurar_matricula_operativa,
    cambiar_estado_asistencia,
    disciplinas_asignadas_profesor,
    liberar_clase,
    liberar_clase_profesor,
    organizaciones_profesor,
    quitar_asistente_profesor,
    rol_profesor_activo,
    revertir_clase_liberada,
    revertir_clase_liberada_profesor,
)
from .utils import ROLE_ADMIN, usuario_tiene_roles
from .utils import disciplinas_vigentes_qs, profesores_vigentes_qs


SESION_AUDIT_FIELDS = ["disciplina_id", "fecha", "estado"]


def _snapshot_sesion(sesion):
    return {
        "disciplina_id": sesion.disciplina_id,
        "fecha": sesion.fecha,
        "estado": sesion.estado,
        "profesor_ids": sorted(sesion.profesores.values_list("id", flat=True)) if sesion.pk else [],
    }


def _metadata_sesion(sesion):
    return {
        "sesion_id": sesion.pk,
        "disciplina_id": sesion.disciplina_id,
        "organizacion_id": sesion.disciplina.organizacion_id,
        "fecha": sesion.fecha,
        "estado": sesion.estado,
    }


def _metadata_asistencia(asistencia):
    return {
        "asistencia_id": asistencia.pk,
        "sesion_id": asistencia.sesion_id,
        "persona_id": asistencia.persona_id,
        "estado": asistencia.estado,
    }


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


def _url_con_filtros_extra(request, nombre_url, **extra_params):
    url = reverse(nombre_url)
    params = request.GET.copy()
    for key, value in extra_params.items():
        params[key] = value
    query = params.urlencode()
    return f"{url}?{query}" if query else url


def _query_profesor(request, *, organizacion_id):
    params = request.GET.copy()
    for key in list(params):
        if key not in {"periodo", "periodo_mes", "periodo_anio", "organizacion"}:
            params.pop(key, None)
    params["organizacion"] = str(organizacion_id)
    return params.urlencode()


def _rol_profesor_solicitado(request):
    return rol_profesor_activo(
        request.user,
        organizacion_id=request.GET.get("organizacion"),
    )


@permiso_requerido(ACCION_EXPORTAR_DATOS, permitir_staff_global=False)
def export_asistencias_xlsx(request):
    periodo = resolver_periodo(request)
    organizacion = organizacion_desde_request(request)
    asistencias = asistencias_export_queryset(request, organizacion=organizacion)
    return xlsx_response(
        filename=f"asistencias_{periodo_sufijo_archivo(periodo)}.xlsx",
        sheet_title="Asistencias",
        headers=ASISTENCIAS_XLSX_HEADERS,
        rows=filas_export_asistencias(
            asistencias,
            periodo_descripcion=descripcion_periodo(request=request, corta=True),
        ),
    )


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
        telefono=persona_form.cleaned_data.get("telefono", ""),
    )
    PersonaRol.objects.get_or_create(
        persona=persona,
        rol=rol_estudiante,
        organizacion=organizacion,
        defaults={"activo": True},
    )
    return persona


def _estudiantes_para_asistencia_qs(organizacion):
    """Lista estudiantes de la organizacion, incluyendo inactivos para reactivacion operativa."""
    queryset = Persona.objects.filter(roles__rol__codigo="ESTUDIANTE")
    if organizacion:
        queryset = queryset.filter(roles__organizacion=organizacion)
    return queryset.distinct().order_by("apellidos", "nombres")


def _estudiantes_sesion_para_usuario(user, sesion):
    queryset = _estudiantes_para_asistencia_qs(sesion.disciplina.organizacion)
    puede_administrar_personas = usuario_tiene_permiso(
        user,
        ACCION_ADMINISTRAR_PERSONAS,
        organizacion=sesion.disciplina.organizacion,
        permitir_staff_global=False,
    )
    if not puede_administrar_personas:
        alumnos_operativos = AlumnoDisciplina.objects.operativas().filter(
            disciplina=sesion.disciplina,
        ).values("alumno_id")
        queryset = queryset.filter(
            pk__in=alumnos_operativos,
            activo=True,
            roles__organizacion=sesion.disciplina.organizacion,
            roles__rol__codigo__iexact="ESTUDIANTE",
            roles__activo=True,
        )
    return queryset.distinct()


def _estudiantes_con_estado_operativo(estudiantes_qs, organizacion):
    estudiantes = list(estudiantes_qs)
    estudiantes_ids = [estudiante.pk for estudiante in estudiantes]
    roles_activos_qs = PersonaRol.objects.filter(
        persona_id__in=estudiantes_ids,
        rol__codigo="ESTUDIANTE",
        activo=True,
    )
    if organizacion:
        roles_activos_qs = roles_activos_qs.filter(organizacion=organizacion)
    roles_activos_ids = set(roles_activos_qs.values_list("persona_id", flat=True))
    for estudiante in estudiantes:
        estudiante.asistencia_inactivo = not estudiante.activo or estudiante.pk not in roles_activos_ids
    return estudiantes


def _reactivar_estudiante_para_asistencia(persona, organizacion):
    if not persona.activo:
        persona.activo = True
        persona.save(update_fields=["activo"])
    PersonaRol.objects.filter(
        persona=persona,
        rol__codigo="ESTUDIANTE",
        organizacion=organizacion,
    ).update(activo=True)


def _usuario_es_profesor_asignado(user, sesion):
    persona = getattr(user, "persona", None)
    if not persona:
        return False
    return (
        sesion.profesores.filter(pk=persona.pk).exists()
        and AsignacionProfesorDisciplina.objects.operativas().filter(
            profesor=persona,
            disciplina=sesion.disciplina,
        ).exists()
        and usuario_tiene_permiso(
            user,
            ACCION_VER_SESION,
            organizacion=sesion.disciplina.organizacion,
            permitir_staff_global=False,
        )
    )


def _usuario_puede_administrar_sesion(user, sesion):
    return usuario_tiene_permiso(
        user,
        ACCION_ADMINISTRAR_SESIONES,
        organizacion=sesion.disciplina.organizacion,
        permitir_staff_global=False,
    )


def _usuario_puede_registrar_asistencia(user, sesion):
    if _usuario_puede_administrar_sesion(user, sesion):
        return True
    return _usuario_es_profesor_asignado(user, sesion) and usuario_tiene_permiso(
        user,
        ACCION_EDITAR_ASISTENCIAS,
        organizacion=sesion.disciplina.organizacion,
        permitir_staff_global=False,
    )


def _usuario_puede_liberar_clase(user, sesion):
    if usuario_tiene_permiso(
        user,
        ACCION_LIBERAR_CLASE,
        organizacion=sesion.disciplina.organizacion,
        permitir_staff_global=False,
    ):
        return True
    return _usuario_es_profesor_asignado(user, sesion)


def _json_error(codigo, mensaje, *, status=400):
    return JsonResponse(
        {
            "ok": False,
            "codigo": codigo,
            "mensaje": mensaje,
        },
        status=status,
    )


def _sesion_para_endpoint_json(pk):
    try:
        return SesionClase.objects.select_related("disciplina", "disciplina__organizacion").get(pk=pk)
    except SesionClase.DoesNotExist:
        return None


def _verificar_acceso_sesion_json(request, pk):
    """
    Returns (sesion, None) on success.
    Returns (None, error_response) on failure.

    - Not authenticated or no qualifying role anywhere → 403 PERMISO_DENEGADO
    - Session not found OR belongs to an org user cannot manage → 404 SESION_NO_ENCONTRADA
      (both cases are intentionally indistinguishable)
    """
    user = request.user
    if not user.is_authenticated:
        return None, _json_error("PERMISO_DENEGADO", "No tienes permisos para operar esta sesión.", status=403)
    if not usuario_tiene_permiso(
        user,
        ACCION_VER_SESION,
        permitir_staff_global=False,
    ):
        return None, _json_error("PERMISO_DENEGADO", "No tienes permisos para operar esta sesión.", status=403)
    sesion = _sesion_para_endpoint_json(pk)
    if not sesion or not _usuario_puede_registrar_asistencia(user, sesion):
        return None, _json_error("SESION_NO_ENCONTRADA", "Sesión no encontrada.", status=404)
    if not _usuario_puede_administrar_sesion(user, sesion):
        rol = _rol_profesor_solicitado(request)
        if not rol or rol.organizacion_id != sesion.disciplina.organizacion_id:
            return None, _json_error("SESION_NO_ENCONTRADA", "Sesión no encontrada.", status=404)
    return sesion, None


def _post_data_json_o_form(request):
    content_type = request.META.get("CONTENT_TYPE", "")
    if content_type.startswith("application/json"):
        try:
            return json.loads(request.body.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            return None
    return request.POST


def _payload_asistencia(asistencia, *, puede_ver_finanzas):
    consumo = getattr(asistencia, "consumo_financiero", None)
    liberacion = getattr(asistencia, "clase_liberada", None)
    liberada = bool(liberacion and liberacion.revertida_en is None)
    if liberada:
        estado_financiero = {
            "codigo": "liberada",
            "label": "Clase liberada",
        }
    elif puede_ver_finanzas and consumo and consumo.estado == AttendanceConsumption.Estado.CONSUMIDO:
        estado_financiero = {"codigo": "consumido", "label": "Pagada"}
    elif puede_ver_finanzas and consumo and consumo.estado == AttendanceConsumption.Estado.DEUDA:
        estado_financiero = {"codigo": "deuda", "label": "Deuda"}
    elif puede_ver_finanzas and consumo and consumo.estado == AttendanceConsumption.Estado.PENDIENTE:
        estado_financiero = {"codigo": "pendiente", "label": "Sin cobro"}
    elif puede_ver_finanzas:
        estado_financiero = {"codigo": "sin_consumo", "label": "Sin consumo"}
    else:
        estado_financiero = None

    return {
        "id": asistencia.pk,
        "persona_id": asistencia.persona_id,
        "nombre": asistencia.persona.nombre_completo,
        "estado": asistencia.estado,
        "estado_label": asistencia.get_estado_display(),
        "hora": timezone.localtime(asistencia.registrada_en).strftime("%H:%M"),
        "clase_liberada": liberada,
        "estado_financiero": estado_financiero,
    }


def _fechas_del_mes_para_dias(year, month, dias_semana, max_sesiones=None):
    _, ultimo_dia = calendar.monthrange(year, month)
    fechas = [
        date(year, month, dia)
        for dia in range(1, ultimo_dia + 1)
        if date(year, month, dia).weekday() in dias_semana
    ]
    if max_sesiones:
        return fechas[:max_sesiones]
    return fechas


@login_required
def sesiones_hoy(request):
    hoy = timezone.localdate()
    ahora = timezone.localtime()
    sesiones_qs = sesiones_visibles_para_usuario(request.user)
    contexto_profesor = None
    organizacion_solicitada = None
    if not request.user.is_superuser:
        organizacion_raw = (request.GET.get("organizacion") or "").strip().lower()
        rol_profesor = _rol_profesor_solicitado(request)
        modo_profesor = bool(rol_profesor) or (
            organizacion_raw == "todos"
            and organizaciones_profesor(request.user).exists()
        )
        if modo_profesor:
            contexto_profesor = resolver_contexto_profesor(request)
            organizacion_solicitada = contexto_profesor["organizacion_activa"]
            sesiones_qs = sesiones_qs.filter(
                disciplina__organizacion_id__in=contexto_profesor["organizacion_ids"],
                disciplina_id__in=contexto_profesor["disciplina_ids"],
                profesores=contexto_profesor["profesor"],
            )
        elif request.GET.get("organizacion"):
            try:
                organizacion_solicitada = Organizacion.objects.filter(
                    pk=request.GET.get("organizacion")
                ).first()
            except (TypeError, ValueError, ValidationError):
                organizacion_solicitada = None
            if not organizacion_solicitada or not usuario_tiene_permiso(
                request.user,
                ACCION_ADMINISTRAR_SESIONES,
                organizacion=organizacion_solicitada,
                permitir_staff_global=False,
            ):
                raise Http404
        elif not usuario_tiene_permiso(
            request.user,
            ACCION_ADMINISTRAR_SESIONES,
            permitir_staff_global=False,
        ):
            raise Http404
        if organizacion_solicitada:
            sesiones_qs = sesiones_qs.filter(
                disciplina__organizacion=organizacion_solicitada,
            )
    sesiones = list(
        sesiones_qs
        .filter(fecha=hoy)
        .order_by("sin_horario", "bloque__hora_inicio", "disciplina__nombre", "pk")
    )
    hora_actual = ahora.time()
    for sesion in sesiones:
        if sesion.estado == SesionClase.Estado.CANCELADA:
            sesion.momento_label = "Cancelada"
            sesion.momento_clase = "secondary"
            sesion.momento_icono = "bi-x-circle"
        elif sesion.estado == SesionClase.Estado.COMPLETADA:
            sesion.momento_label = "Finalizada"
            sesion.momento_clase = "success"
            sesion.momento_icono = "bi-check-circle"
        elif sesion.estado == SesionClase.Estado.ABIERTA:
            sesion.momento_label = "Abierta"
            sesion.momento_clase = "warning"
            sesion.momento_icono = "bi-play-circle"
        elif sesion.bloque and hora_actual < sesion.bloque.hora_inicio:
            sesion.momento_label = "Próxima"
            sesion.momento_clase = "primary"
            sesion.momento_icono = "bi-clock"
        elif sesion.bloque and hora_actual <= sesion.bloque.hora_fin:
            sesion.momento_label = "En curso"
            sesion.momento_clase = "warning"
            sesion.momento_icono = "bi-play-circle"
        elif sesion.bloque:
            sesion.momento_label = "Horario finalizado"
            sesion.momento_clase = "secondary"
            sesion.momento_icono = "bi-clock-history"
        else:
            sesion.momento_label = "Programada · sin horario"
            sesion.momento_clase = "info"
            sesion.momento_icono = "bi-calendar-event"

    context = contexto_profesor or nav_context(request, permitir_staff_global=False)
    context.update(
        {
            "hide_periodo": True,
            "fecha_hoy": hoy,
            "sesiones": sesiones,
            "profesor_mode": bool(contexto_profesor),
            "base_template": (
                "asistencias/profesor/base.html"
                if contexto_profesor
                else "asistencias/base_app.html"
            ),
        }
    )
    return render(request, "asistencias/sesiones_hoy.html", context)


@role_required(ROLE_ADMIN, permitir_staff_global=False)
def dashboard(request):
    """Panel principal con métricas operativas según período y organización."""
    context = nav_context(request, permitir_staff_global=False)
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
        revertido_en__isnull=True,
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


@role_required(ROLE_ADMIN, permitir_staff_global=False)
def sesiones_list(request):
    """Vista calendario mensual de sesiones."""
    context = nav_context(request, permitir_staff_global=False)
    organizacion = organizacion_desde_request(request)
    periodo = resolver_periodo(request)
    year = periodo["referencia_inicio"].year
    month = periodo["referencia_inicio"].month
    sesiones_masivas_form = SesionesMasivasForm(organizacion=organizacion)
    open_sesiones_masivas = False
    sesiones_qs = (
        SesionClase.objects.select_related("disciplina")
        .prefetch_related("profesores")
        .order_by("fecha")
    )
    sesiones_qs = aplicar_periodo(sesiones_qs, "fecha", request=request)
    if organizacion:
        sesiones_qs = sesiones_qs.filter(disciplina__organizacion=organizacion)

    if request.method == "POST" and "crear_sesiones_masivas" in request.POST:
        sesiones_masivas_form = SesionesMasivasForm(request.POST, organizacion=organizacion)
        open_sesiones_masivas = True
        if periodo["mes"] is None or periodo["anio"] is None:
            sesiones_masivas_form.add_error(
                None,
                "Debes seleccionar un mes y año específicos para crear sesiones masivas.",
            )
        elif sesiones_masivas_form.is_valid():
            disciplina = sesiones_masivas_form.cleaned_data["disciplina"]
            profesores = list(sesiones_masivas_form.cleaned_data["profesores"])
            fechas = _fechas_del_mes_para_dias(
                year,
                month,
                sesiones_masivas_form.cleaned_data["dias_semana"],
                sesiones_masivas_form.cleaned_data["max_sesiones"],
            )
            creadas = 0
            omitidas = 0
            for fecha in fechas:
                if SesionClase.objects.filter(disciplina=disciplina, fecha=fecha).exists():
                    omitidas += 1
                    continue
                sesion = SesionClase.objects.create(
                    disciplina=disciplina,
                    fecha=fecha,
                    notas=f"{disciplina.nombre} - {fecha}",
                )
                if profesores:
                    sesion.profesores.set(profesores)
                    asegurar_asignaciones_profesores(
                        disciplina=sesion.disciplina,
                        profesores=profesores,
                        user=request.user,
                    )
                creadas += 1
            messages.success(
                request,
                f"Sesiones creadas: {creadas}. Fechas omitidas por duplicado: {omitidas}.",
            )
            return redirect(request.get_full_path())

    if periodo["mes"] is None or periodo["anio"] is None:
        context.update(
            {
                "mostrar_calendario": False,
                "periodo_descripcion_vista": descripcion_periodo(request=request, corta=False),
                "sesiones_listado": sesiones_qs,
                "sesiones_masivas_form": sesiones_masivas_form,
                "open_sesiones_masivas": open_sesiones_masivas,
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
            "sesiones_masivas_form": sesiones_masivas_form,
            "open_sesiones_masivas": open_sesiones_masivas,
        }
    )
    return render(request, "asistencias/sesiones_list.html", context)


@role_required(ROLE_ADMIN, permitir_staff_global=False)
def sesiones_legacy_redirect(request):
    url = reverse("asistencias:sesiones_list")
    query = request.GET.urlencode()
    return redirect(f"{url}?{query}" if query else url)


@role_required(ROLE_ADMIN, permitir_staff_global=False)
def estudiantes_list(request):
    """Listado de estudiantes con estado de asistencia del período seleccionado."""
    context = nav_context(request, permitir_staff_global=False)
    organizacion = organizacion_desde_request(request)
    org_id = request.GET.get("organizacion")
    contexto = estudiantes_operativos_periodo(request, organizacion=organizacion)
    if request.GET.get("sin_asistencia") == "1":
        contexto = [item for item in contexto if not item["activo_mes"]]
    puede_operar_pagos = usuario_tiene_permiso(
        request.user,
        ACCION_OPERAR_PAGOS,
        organizacion=organizacion,
        permitir_staff_global=False,
    )
    puede_ver_finanzas = usuario_tiene_permiso(
        request.user,
        ACCION_VER_FINANZAS,
        organizacion=organizacion,
        permitir_staff_global=False,
    )
    for item in contexto:
        item["perfil_url"] = _url_con_filtros(request, "personas:persona_detail", pk=item["persona"].pk)
        item["registrar_pago_url"] = _url_con_filtros_extra(
            request,
            "finanzas:pagos_list",
            persona=item["persona"].pk,
            open="registrar_pago",
        )
        item["asistencias_url"] = _url_con_filtros_extra(
            request,
            "asistencias:asistencias_list",
            q=item["persona"].nombre_completo,
        )
    context["estudiantes"] = contexto
    context["puede_operar_pagos"] = puede_operar_pagos
    context["puede_ver_finanzas"] = puede_ver_finanzas
    context["filtros"] = {
        "organizacion": org_id,
        "sin_asistencia": request.GET.get("sin_asistencia"),
    }
    return render(request, "asistencias/estudiantes_list.html", context)


@role_required(ROLE_ADMIN, permitir_staff_global=False)
def profesores_list(request):
    """Listado de profesores agrupado por organización y período seleccionado."""
    context = nav_context(request, permitir_staff_global=False)
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


@role_required(ROLE_ADMIN, permitir_staff_global=False)
def disciplinas_list(request):
    """Resumen de disciplinas con métricas operativas del período."""
    context = nav_context(request, permitir_staff_global=False)
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


@role_required(ROLE_ADMIN, permitir_staff_global=False)
def disciplina_detail(request, pk):
    """Detalle de disciplina con métricas de sesiones y asistencias por período."""
    context = nav_context(request, permitir_staff_global=False)
    organizacion = organizacion_desde_request(request)
    disciplinas_visibles = Disciplina.objects.select_related("organizacion")
    if organizacion:
        disciplinas_visibles = disciplinas_visibles.filter(organizacion=organizacion)
    disciplina = get_object_or_404(disciplinas_visibles, pk=pk)

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
    estudiantes_disciplina = estudiantes_financieros_disciplina(request, disciplina=disciplina)

    context.update(
        {
            "disciplina": disciplina,
            "sesiones": sesiones,
            "resumen": resumen,
            "profesores_periodo": profesores_periodo,
            "estudiantes_disciplina": estudiantes_disciplina,
            "periodo_descripcion_vista": descripcion_periodo(request=request, corta=False),
        }
    )
    return render(request, "asistencias/disciplina_detail.html", context)


@role_required(ROLE_ADMIN, permitir_staff_global=False)
def disciplina_create(request):
    """Crea una disciplina."""
    context = nav_context(request, permitir_staff_global=False)
    initial = {}
    if request.GET.get("organizacion"):
        initial["organizacion"] = request.GET.get("organizacion")

    form = DisciplinaForm(
        request.POST or None,
        initial=initial,
        organizaciones=organizaciones_visibles_para_usuario(
            request.user,
            permitir_staff_global=False,
        ),
    )
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


@role_required(ROLE_ADMIN, permitir_staff_global=False)
def disciplina_edit(request, pk):
    """Edita una disciplina existente."""
    context = nav_context(request, permitir_staff_global=False)
    organizacion = organizacion_desde_request(request)
    disciplinas_visibles = Disciplina.objects.all()
    if organizacion:
        disciplinas_visibles = disciplinas_visibles.filter(organizacion=organizacion)
    disciplina = get_object_or_404(disciplinas_visibles, pk=pk)
    form = DisciplinaForm(
        request.POST or None,
        instance=disciplina,
        organizaciones=organizaciones_visibles_para_usuario(
            request.user,
            permitir_staff_global=False,
        ),
    )

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

@role_required(ROLE_ADMIN, permitir_staff_global=False)
def asistencias_list(request):
    """Pantalla operativa para crear sesiones y registrar asistencias en bloque."""
    context = nav_context(request, permitir_staff_global=False)
    sesion_id = request.GET.get("sesion_id")
    organizacion = organizacion_desde_request(request)
    sesiones_disponibles_qs = SesionClase.objects.select_related(
        "disciplina",
        "disciplina__organizacion",
    ).filter(**filtros_periodo("fecha", request=request))
    if organizacion:
        sesiones_disponibles_qs = sesiones_disponibles_qs.filter(disciplina__organizacion=organizacion)
    sesion_seleccionada = sesiones_disponibles_qs.filter(pk=sesion_id).first() if sesion_id else None
    organizacion_estudiantes = sesion_seleccionada.disciplina.organizacion if sesion_seleccionada else organizacion
    asistentes_ids = set()
    if sesion_seleccionada:
        asistentes_ids = set(
            Asistencia.objects.filter(sesion=sesion_seleccionada).values_list("persona_id", flat=True)
        )
    sesion_form = SesionBasicaForm(initial={"fecha": timezone.localdate()}, organizacion=organizacion)
    asistencia_form = AsistenciaMasivaForm(
        initial={"sesion_id": sesion_seleccionada.pk} if sesion_seleccionada else None,
        sesiones_queryset=sesiones_disponibles_qs,
    )
    persona_form = PersonaRapidaForm()
    open_nueva_sesion = request.GET.get("open") == "nueva_sesion"
    open_nueva_persona = False
    open_agregar_asistentes = request.GET.get("open") == "agregar_asistentes"
    estudiantes_qs = _estudiantes_para_asistencia_qs(organizacion_estudiantes)
    estudiantes = _estudiantes_con_estado_operativo(estudiantes_qs, organizacion_estudiantes)
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
                    asegurar_asignaciones_profesores(
                        disciplina=sesion.disciplina,
                        profesores=profesores,
                        user=request.user,
                    )
                registrar_auditoria(
                    usuario=request.user,
                    accion=AuditLog.ACCION_CREAR,
                    dominio="asistencias",
                    objeto=sesion,
                    organizacion=sesion.disciplina.organizacion,
                    resumen="Sesión creada",
                    metadata={**_metadata_sesion(sesion), "profesor_ids": [profesor.pk for profesor in profesores]},
                )
                messages.success(request, "Sesión creada. Ahora puedes agregar asistentes.")
                return redirect(_url_actual_con_filtros(request, sesion_id=sesion.pk, open="agregar_asistentes"))
            open_nueva_sesion = True
        elif "cambiar_estado" in request.POST:
            sesion_id_post = request.POST.get("sesion_id")
            estado = request.POST.get("estado")
            if sesion_id_post and estado in dict(SesionClase.Estado.choices):
                sesiones_autorizadas = sesiones_visibles_para_usuario(request.user)
                if organizacion:
                    sesiones_autorizadas = sesiones_autorizadas.filter(
                        disciplina__organizacion=organizacion,
                    )
                sesion = get_object_or_404(
                    sesiones_autorizadas,
                    pk=sesion_id_post,
                )
                if not _usuario_puede_administrar_sesion(request.user, sesion):
                    raise Http404
                estado_anterior = sesion.estado
                sesion.estado = estado
                sesion.save(update_fields=["estado"])
                registrar_cambio(
                    usuario=request.user,
                    dominio="asistencias",
                    objeto=sesion,
                    organizacion=sesion.disciplina.organizacion,
                    resumen="Estado de sesión actualizado",
                    antes={"estado": estado_anterior},
                    despues={"estado": sesion.estado},
                    campos=["estado"],
                    accion=AuditLog.ACCION_CAMBIAR_ESTADO,
                    metadata=_metadata_sesion(sesion),
                )
                messages.success(request, "Estado de la sesión actualizado.")
                return redirect(request.get_full_path())
        elif "agregar_persona" in request.POST:
            persona_form = PersonaRapidaForm(request.POST)
            open_nueva_persona = True
            if persona_form.is_valid():
                persona = _crear_persona_estudiante_en_organizacion(persona_form, organizacion)
                if persona:
                    registrar_auditoria(
                        usuario=request.user,
                        accion=AuditLog.ACCION_CREAR,
                        dominio="personas",
                        objeto=persona,
                        organizacion=organizacion,
                        resumen="Persona creada desde asistencias",
                        metadata={"persona_id": persona.pk, "origen": "asistencias_list"},
                    )
                    messages.success(request, "Persona creada y asignada como estudiante.")
                    open_nueva_persona = False
                    return redirect(_url_actual_con_filtros(request))
        elif "agregar_asistentes" in request.POST:
            asistencia_form = AsistenciaMasivaForm(request.POST, sesiones_queryset=sesiones_disponibles_qs)
            sesion = sesiones_disponibles_qs.filter(pk=request.POST.get("sesion_id")).first()
            if sesion:
                sesion_seleccionada = sesion
                estudiantes_qs = _estudiantes_para_asistencia_qs(sesion.disciplina.organizacion)
                estudiantes = _estudiantes_con_estado_operativo(estudiantes_qs, sesion.disciplina.organizacion)
                asistentes_ids = set(
                    Asistencia.objects.filter(sesion=sesion).values_list("persona_id", flat=True)
                )
                asistencia_form.fields["estudiantes"].queryset = estudiantes_qs
            if asistencia_form.is_valid():
                estudiantes_seleccionados = list(asistencia_form.cleaned_data["estudiantes"])
                creados = 0
                asistencia_ids_creadas = []
                for persona in estudiantes_seleccionados:
                    asegurar_matricula_operativa(
                        user=request.user,
                        disciplina=sesion.disciplina,
                        alumno=persona,
                    )
                    _reactivar_estudiante_para_asistencia(persona, sesion.disciplina.organizacion)
                    asistencia, created = Asistencia.objects.get_or_create(
                        sesion=sesion,
                        persona=persona,
                        defaults={"estado": Asistencia.Estado.PRESENTE},
                    )
                    if created:
                        creados += 1
                        asistencia_ids_creadas.append(asistencia.pk)
                estado_anterior = sesion.estado
                if estudiantes_seleccionados and sesion.estado == SesionClase.Estado.PROGRAMADA:
                    sesion.estado = SesionClase.Estado.COMPLETADA
                    sesion.save(update_fields=["estado"])
                registrar_auditoria(
                    usuario=request.user,
                    accion=AuditLog.ACCION_AGREGAR_ASISTENTES,
                    dominio="asistencias",
                    objeto=sesion,
                    organizacion=sesion.disciplina.organizacion,
                    resumen="Asistentes agregados a sesión",
                    metadata={
                        **_metadata_sesion(sesion),
                        "asistencias_creadas": creados,
                        "asistencia_ids_creadas": asistencia_ids_creadas,
                        "persona_ids": [persona.pk for persona in estudiantes_seleccionados],
                        "estado_anterior": estado_anterior,
                        "estado_despues": sesion.estado,
                    },
                )
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
            "sesiones_agregar_asistentes": sesiones_disponibles_qs,
            "asistentes_ids": asistentes_ids,
            "estudiantes": estudiantes,
            "estudiantes_total": estudiantes_qs.count(),
            "estudiantes_total_disciplina_periodo": estudiantes_total_disciplina_periodo,
            "disciplinas": disciplinas_vigentes_qs(organizacion=organizacion),
            "profesores": profesores_vigentes_qs(organizacion=organizacion),
            "organizaciones": organizaciones_visibles_para_usuario(
                request.user,
                permitir_staff_global=False,
            ),
        }
    )
    return render(request, "asistencias/asistencias_list.html", context)


@login_required
def sesion_detail(request, pk):
    """Detalle de la sesión y estado de sus asistentes."""
    context = nav_context(request, permitir_staff_global=False)
    context["hide_periodo"] = True
    sesion = get_object_or_404(
        sesiones_visibles_para_usuario(request.user).prefetch_related(
            "asistencias__persona",
        ),
        pk=pk,
    )
    organizacion_solicitada = (request.GET.get("organizacion") or "").strip()
    if (
        organizacion_solicitada
        and organizacion_solicitada.lower() not in {"todos", "todas"}
        and organizacion_solicitada != str(sesion.disciplina.organizacion_id)
    ):
        raise Http404
    puede_administrar = _usuario_puede_administrar_sesion(request.user, sesion)
    puede_registrar = _usuario_puede_registrar_asistencia(request.user, sesion)
    puede_liberar = _usuario_puede_liberar_clase(request.user, sesion)
    profesor_query = ""
    contexto_profesor = None
    if puede_registrar and not puede_administrar:
        rol_profesor = _rol_profesor_solicitado(request)
        if not rol_profesor or rol_profesor.organizacion_id != sesion.disciplina.organizacion_id:
            raise Http404
        contexto_profesor = resolver_contexto_profesor(request)
        if contexto_profesor["organizacion_todas"]:
            raise Http404
        profesor_query = contexto_profesor["profesor_query"]
    estudiantes_qs = _estudiantes_sesion_para_usuario(request.user, sesion)
    estudiantes = _estudiantes_con_estado_operativo(estudiantes_qs, sesion.disciplina.organizacion)
    persona_form = PersonaRapidaForm()
    open_nueva_persona = False
    if request.method == "POST":
        if "eliminar_sesion" in request.POST:
            if not puede_administrar:
                raise PermissionDenied("No tienes permisos para eliminar esta sesión.")
            sesion_resumen = str(sesion)
            registrar_auditoria(
                usuario=request.user,
                accion=AuditLog.ACCION_ELIMINAR,
                dominio="asistencias",
                objeto=sesion,
                organizacion=sesion.disciplina.organizacion,
                resumen="Sesión eliminada",
                metadata=_metadata_sesion(sesion),
            )
            sesion.delete()
            messages.success(request, f"Sesión eliminada: {sesion_resumen}.")
            return redirect(_url_con_filtros(request, "asistencias:sesiones_list"))
        elif "crear_persona_estudiante" in request.POST:
            if not usuario_tiene_permiso(
                request.user,
                ACCION_ADMINISTRAR_PERSONAS,
                organizacion=sesion.disciplina.organizacion,
                permitir_staff_global=False,
            ):
                raise PermissionDenied("No tienes permisos para crear personas desde esta sesión.")
            persona_form = PersonaRapidaForm(request.POST)
            open_nueva_persona = True
            if persona_form.is_valid():
                persona = _crear_persona_estudiante_en_organizacion(
                    persona_form,
                    sesion.disciplina.organizacion,
                )
                if persona:
                    asegurar_matricula_operativa(
                        user=request.user,
                        disciplina=sesion.disciplina,
                        alumno=persona,
                    )
                    registrar_auditoria(
                        usuario=request.user,
                        accion=AuditLog.ACCION_CREAR,
                        dominio="personas",
                        objeto=persona,
                        organizacion=sesion.disciplina.organizacion,
                        resumen="Persona creada desde sesión",
                        metadata={"persona_id": persona.pk, "sesion_id": sesion.pk, "origen": "sesion_detail"},
                    )
                    agregar_a_sesion = request.POST.get("agregar_a_sesion") == "1"
                    if agregar_a_sesion:
                        asistencia, created = Asistencia.objects.get_or_create(
                            sesion=sesion,
                            persona=persona,
                            defaults={"estado": Asistencia.Estado.PRESENTE},
                        )
                        estado_anterior = sesion.estado
                        if sesion.estado == SesionClase.Estado.PROGRAMADA:
                            sesion.estado = SesionClase.Estado.COMPLETADA
                            sesion.save(update_fields=["estado"])
                        if created:
                            registrar_auditoria(
                                usuario=request.user,
                                accion=AuditLog.ACCION_CREAR,
                                dominio="asistencias",
                                objeto=asistencia,
                                organizacion=sesion.disciplina.organizacion,
                                resumen="Asistencia creada desde alta rápida",
                                metadata={
                                    **_metadata_asistencia(asistencia),
                                    "origen": "alta_rapida_sesion",
                                },
                            )
                        if estado_anterior != sesion.estado:
                            registrar_cambio(
                                usuario=request.user,
                                dominio="asistencias",
                                objeto=sesion,
                                organizacion=sesion.disciplina.organizacion,
                                resumen="Estado de sesión actualizado por alta rápida",
                                antes={"estado": estado_anterior},
                                despues={"estado": sesion.estado},
                                campos=["estado"],
                                accion=AuditLog.ACCION_CAMBIAR_ESTADO,
                                metadata=_metadata_sesion(sesion),
                            )
                        if created:
                            messages.success(request, "Persona creada y agregada a la asistencia.")
                        else:
                            messages.success(request, "Persona creada; la asistencia ya existía para esta sesión.")
                    else:
                        messages.success(request, "Persona creada y asignada como estudiante de la sesión.")
                    return redirect(_url_con_filtros(request, "asistencias:sesion_detail", pk=sesion.pk))
        elif "eliminar_asistente" in request.POST:
            if not puede_registrar:
                raise PermissionDenied("No tienes permisos para quitar asistentes de esta sesión.")
            asistencia = get_object_or_404(Asistencia, pk=request.POST.get("asistencia_id"), sesion=sesion)
            persona_nombre = str(asistencia.persona)
            if puede_administrar:
                registrar_auditoria(
                    usuario=request.user,
                    accion=AuditLog.ACCION_ELIMINAR,
                    dominio="asistencias",
                    objeto=asistencia,
                    organizacion=sesion.disciplina.organizacion,
                    resumen="Asistente eliminado de sesión",
                    metadata=_metadata_asistencia(asistencia),
                )
                asistencia.delete()
            else:
                quitar_asistente_profesor(
                    user=request.user,
                    organizacion_id=sesion.disciplina.organizacion_id,
                    sesion=sesion,
                    asistencia=asistencia,
                )
            messages.success(request, f"Asistente quitado de la sesión: {persona_nombre}.")
            return redirect(_url_con_filtros(request, "asistencias:sesion_detail", pk=sesion.pk))
        elif "cambiar_estado" in request.POST:
            if not puede_administrar:
                raise PermissionDenied("No tienes permisos para cambiar el estado de la sesión.")
            estado = request.POST.get("estado")
            if estado in dict(SesionClase.Estado.choices):
                estado_anterior = sesion.estado
                sesion.estado = estado
                sesion.save(update_fields=["estado"])
                registrar_cambio(
                    usuario=request.user,
                    dominio="asistencias",
                    objeto=sesion,
                    organizacion=sesion.disciplina.organizacion,
                    resumen="Estado de sesión actualizado",
                    antes={"estado": estado_anterior},
                    despues={"estado": sesion.estado},
                    campos=["estado"],
                    accion=AuditLog.ACCION_CAMBIAR_ESTADO,
                    metadata=_metadata_sesion(sesion),
                )
                messages.success(request, "Estado de la sesión actualizado.")
                return redirect(_url_con_filtros(request, "asistencias:sesion_detail", pk=sesion.pk))
        elif "cambiar_estado_asistencia" in request.POST:
            if not puede_registrar:
                raise PermissionDenied("No tienes permisos para corregir asistencias en esta sesión.")
            asistencia = get_object_or_404(
                Asistencia,
                pk=request.POST.get("asistencia_id"),
                sesion=sesion,
            )
            try:
                cambiar_estado_asistencia(
                    asistencia=asistencia,
                    estado=request.POST.get("estado_asistencia"),
                    usuario=request.user,
                )
            except ValidationError as exc:
                messages.error(request, exc.messages[0])
            else:
                messages.success(request, "Estado de asistencia actualizado.")
            return redirect(_url_con_filtros(request, "asistencias:sesion_detail", pk=sesion.pk))
        elif "liberar_clase" in request.POST:
            if not puede_liberar:
                raise PermissionDenied("No tienes permisos para liberar clases.")
            asistencia = get_object_or_404(
                Asistencia,
                pk=request.POST.get("asistencia_id"),
                sesion=sesion,
            )
            try:
                if puede_administrar:
                    liberar_clase(
                        asistencia=asistencia,
                        motivo=request.POST.get("motivo_liberacion"),
                        usuario=request.user,
                    )
                else:
                    liberar_clase_profesor(
                        user=request.user,
                        organizacion_id=sesion.disciplina.organizacion_id,
                        sesion=sesion,
                        asistencia=asistencia,
                        motivo=request.POST.get("motivo_liberacion"),
                    )
            except ValidationError as exc:
                messages.error(request, exc.messages[0])
            else:
                messages.success(request, "Clase liberada correctamente.")
            return redirect(_url_con_filtros(request, "asistencias:sesion_detail", pk=sesion.pk))
        elif "revertir_clase_liberada" in request.POST:
            if not puede_liberar:
                raise PermissionDenied("No tienes permisos para revertir clases liberadas.")
            asistencia = get_object_or_404(
                Asistencia,
                pk=request.POST.get("asistencia_id"),
                sesion=sesion,
            )
            try:
                if puede_administrar:
                    revertir_clase_liberada(
                        asistencia=asistencia,
                        usuario=request.user,
                    )
                else:
                    revertir_clase_liberada_profesor(
                        user=request.user,
                        organizacion_id=sesion.disciplina.organizacion_id,
                        sesion=sesion,
                        asistencia=asistencia,
                    )
            except ValidationError as exc:
                messages.error(request, exc.messages[0])
            else:
                messages.success(request, "Clase liberada revertida.")
            return redirect(_url_con_filtros(request, "asistencias:sesion_detail", pk=sesion.pk))
        elif "agregar_asistentes" in request.POST:
            if not puede_registrar:
                raise PermissionDenied("No tienes permisos para registrar asistencias en esta sesión.")
            estudiantes_ids = request.POST.getlist("estudiantes")
            estudiantes_seleccionados = list(estudiantes_qs.filter(pk__in=estudiantes_ids))
            creados = 0
            asistencia_ids_creadas = []
            for persona in estudiantes_seleccionados:
                if usuario_tiene_permiso(
                    request.user,
                    ACCION_ADMINISTRAR_PERSONAS,
                    organizacion=sesion.disciplina.organizacion,
                    permitir_staff_global=False,
                ):
                    asegurar_matricula_operativa(
                        user=request.user,
                        disciplina=sesion.disciplina,
                        alumno=persona,
                    )
                _reactivar_estudiante_para_asistencia(persona, sesion.disciplina.organizacion)
                asistencia, created = Asistencia.objects.get_or_create(
                    sesion=sesion,
                    persona=persona,
                    defaults={"estado": Asistencia.Estado.PRESENTE},
                )
                if created:
                    creados += 1
                    asistencia_ids_creadas.append(asistencia.pk)
            estado_anterior = sesion.estado
            if estudiantes_seleccionados and sesion.estado == SesionClase.Estado.PROGRAMADA:
                sesion.estado = (
                    SesionClase.Estado.COMPLETADA
                    if puede_administrar
                    else SesionClase.Estado.ABIERTA
                )
                sesion.save(update_fields=["estado"])
            registrar_auditoria(
                usuario=request.user,
                accion=AuditLog.ACCION_AGREGAR_ASISTENTES,
                dominio="asistencias",
                objeto=sesion,
                organizacion=sesion.disciplina.organizacion,
                resumen="Asistentes agregados a sesión",
                metadata={
                    **_metadata_sesion(sesion),
                    "asistencias_creadas": creados,
                    "asistencia_ids_creadas": asistencia_ids_creadas,
                    "persona_ids": [persona.pk for persona in estudiantes_seleccionados],
                    "estado_anterior": estado_anterior,
                    "estado_despues": sesion.estado,
                },
            )
            messages.success(request, f"Asistencias agregadas: {creados}.")
            return redirect(_url_con_filtros(request, "asistencias:sesion_detail", pk=sesion.pk))

    asistencias = sesion.asistencias.select_related(
        "persona",
        "consumo_financiero__pago",
        "clase_liberada",
    ).order_by("-registrada_en")
    for asistencia in asistencias:
        consumo = getattr(asistencia, "consumo_financiero", None)
        liberacion = getattr(asistencia, "clase_liberada", None)
        asistencia.clase_liberada_activa = bool(liberacion and liberacion.revertida_en is None)
        if asistencia.clase_liberada_activa:
            asistencia.estado_financiero_label = "Liberada"
            asistencia.estado_financiero_clase = "info"
        elif consumo and consumo.estado == AttendanceConsumption.Estado.CONSUMIDO:
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
    hay_alumnos_elegibles = estudiantes_qs.exclude(pk__in=asistentes_ids).exists()
    sesion_anterior = None
    sesion_siguiente = None
    if puede_registrar and not puede_administrar:
        alcance = sesiones_visibles_para_usuario(request.user).filter(
            disciplina__organizacion_id=sesion.disciplina.organizacion_id,
        )
        sesion_anterior = alcance.filter(
            Q(fecha__lt=sesion.fecha) | Q(fecha=sesion.fecha, pk__lt=sesion.pk)
        ).order_by("-fecha", "-pk").first()
        sesion_siguiente = alcance.filter(
            Q(fecha__gt=sesion.fecha) | Q(fecha=sesion.fecha, pk__gt=sesion.pk)
        ).order_by("fecha", "pk").first()
    if contexto_profesor:
        context.update(contexto_profesor)
    context.update(
        {
            "sesion": sesion,
            "asistencias": asistencias,
            "total_asistentes": asistencias.count(),
            "estudiantes": estudiantes,
            "asistentes_ids": asistentes_ids,
            "hay_alumnos_elegibles": hay_alumnos_elegibles,
            "persona_form": persona_form,
            "open_nueva_persona": open_nueva_persona,
            "puede_administrar_sesion": puede_administrar,
            "puede_registrar_asistencia": puede_registrar,
            "puede_liberar_clase": puede_liberar,
            "puede_quitar_asistente": puede_registrar,
            "es_jornada_profesora": puede_registrar and not puede_administrar,
            "profesor_mode": puede_registrar and not puede_administrar,
            "profesor_query": profesor_query,
            "base_template": (
                "asistencias/profesor/base.html"
                if puede_registrar and not puede_administrar
                else "asistencias/base_app.html"
            ),
            "sesion_anterior": sesion_anterior,
            "sesion_siguiente": sesion_siguiente,
            "back_url": (
                f"{reverse('profesor:sesiones')}?{profesor_query}"
                if puede_registrar and not puede_administrar
                else request.META.get("HTTP_REFERER")
                or _url_con_filtros(request, "asistencias:sesiones_list")
            ),
        }
    )
    return render(request, "asistencias/sesion_detail.html", context)


@require_GET
def sesion_asistentes_buscar(request, pk):
    sesion, error = _verificar_acceso_sesion_json(request, pk)
    if error:
        return error

    termino = request.GET.get("q", "").strip()
    if len(termino) < 2:
        return JsonResponse({"ok": True, "resultados": []})

    asistentes_ids = Asistencia.objects.filter(sesion=sesion).values_list("persona_id", flat=True)
    estudiantes_qs = filtrar_por_fragmentos(
        _estudiantes_sesion_para_usuario(request.user, sesion)
        .exclude(pk__in=asistentes_ids),
        termino,
        campos=("nombres", "apellidos", "rut", "email"),
        prefijo="asistente_sesion",
    )

    estudiantes = _estudiantes_con_estado_operativo(estudiantes_qs[:10], sesion.disciplina.organizacion)
    return JsonResponse(
        {
            "ok": True,
            "resultados": [
                {
                    "id": estudiante.pk,
                    "nombre": estudiante.nombre_completo,
                    "inactivo": estudiante.asistencia_inactivo,
                }
                for estudiante in estudiantes
            ],
        }
    )


@require_POST
def sesion_asistente_agregar(request, pk):
    sesion, error = _verificar_acceso_sesion_json(request, pk)
    if error:
        return error

    data = _post_data_json_o_form(request)
    if data is None:
        return _json_error("JSON_INVALIDO", "El cuerpo JSON no es válido.", status=400)

    persona_id_raw = data.get("persona_id")
    if not persona_id_raw:
        return _json_error("PERSONA_REQUERIDA", "Debes indicar una persona.", status=400)
    try:
        persona_id = int(persona_id_raw)
    except (TypeError, ValueError):
        return _json_error("PERSONA_INVALIDA", "La persona no es estudiante válido de esta organización.", status=400)

    if Asistencia.objects.filter(sesion=sesion, persona_id=persona_id).exists():
        return _json_error("ASISTENCIA_DUPLICADA", "La persona ya está agregada.", status=409)

    persona = _estudiantes_sesion_para_usuario(request.user, sesion).filter(pk=persona_id).first()
    if not persona:
        return _json_error("PERSONA_INVALIDA", "La persona no es estudiante válido de esta organización.", status=400)

    with transaction.atomic():
        sesion = SesionClase.objects.select_for_update().select_related("disciplina", "disciplina__organizacion").get(
            pk=sesion.pk
        )
        if usuario_tiene_permiso(
            request.user,
            ACCION_ADMINISTRAR_PERSONAS,
            organizacion=sesion.disciplina.organizacion,
            permitir_staff_global=False,
        ):
            asegurar_matricula_operativa(
                user=request.user,
                disciplina=sesion.disciplina,
                alumno=persona,
            )
        asistencia, created = Asistencia.objects.get_or_create(
            sesion=sesion,
            persona=persona,
            defaults={"estado": Asistencia.Estado.PRESENTE},
        )
        if not created:
            return _json_error("ASISTENCIA_DUPLICADA", "La persona ya está agregada.", status=409)

        _reactivar_estudiante_para_asistencia(persona, sesion.disciplina.organizacion)
        estado_anterior = sesion.estado
        if sesion.estado == SesionClase.Estado.PROGRAMADA:
            sesion.estado = (
                SesionClase.Estado.COMPLETADA
                if _usuario_puede_administrar_sesion(request.user, sesion)
                else SesionClase.Estado.ABIERTA
            )
            sesion.save(update_fields=["estado"])

        registrar_auditoria(
            usuario=request.user,
            accion=AuditLog.ACCION_AGREGAR_ASISTENTES,
            dominio="asistencias",
            objeto=sesion,
            organizacion=sesion.disciplina.organizacion,
            resumen="Asistente agregado a sesión desde endpoint móvil",
            metadata={
                **_metadata_sesion(sesion),
                "asistencia_id": asistencia.pk,
                "persona_id": persona.pk,
                "estado_asistencia": asistencia.estado,
                "estado_anterior": estado_anterior,
                "estado_despues": sesion.estado,
                "origen": "sesion_detail_mobile",
            },
        )

    asistencia = Asistencia.objects.select_related(
        "persona",
        "consumo_financiero",
        "clase_liberada",
    ).get(pk=asistencia.pk)
    puede_administrar = _usuario_puede_administrar_sesion(request.user, sesion)
    payload = _payload_asistencia(
        asistencia,
        puede_ver_finanzas=puede_administrar,
    )
    estado_financiero = payload.pop("estado_financiero")
    if puede_administrar:
        payload["persona_url"] = reverse("personas:persona_detail", args=[persona.pk])

    total = sesion.asistencias.count()
    return JsonResponse(
        {
            "ok": True,
            "asistencia": payload,
            "estado_financiero": estado_financiero,
            "total": total,
            "mensaje": "Asistente agregado",
        },
        status=201,
    )


@require_POST
def sesion_asistencia_estado(request, pk, asistencia_pk):
    sesion, error = _verificar_acceso_sesion_json(request, pk)
    if error:
        return error

    data = _post_data_json_o_form(request)
    if data is None:
        return _json_error("JSON_INVALIDO", "El cuerpo JSON no es válido.", status=400)
    estado = data.get("estado")
    if estado not in dict(Asistencia.Estado.choices):
        return _json_error("ESTADO_INVALIDO", "El estado de asistencia no es válido.", status=400)

    asistencia = (
        Asistencia.objects.select_related("persona", "sesion")
        .filter(pk=asistencia_pk, sesion=sesion)
        .first()
    )
    if not asistencia:
        return _json_error("ASISTENCIA_NO_ENCONTRADA", "Asistencia no encontrada.", status=404)

    try:
        asistencia, _ = cambiar_estado_asistencia(
            asistencia=asistencia,
            estado=estado,
            usuario=request.user,
        )
    except ValidationError as exc:
        return _json_error("ESTADO_INVALIDO", exc.messages[0], status=400)

    asistencia = Asistencia.objects.select_related(
        "persona",
        "consumo_financiero",
        "clase_liberada",
    ).get(pk=asistencia.pk)
    payload = _payload_asistencia(
        asistencia,
        puede_ver_finanzas=_usuario_puede_administrar_sesion(request.user, sesion),
    )
    estado_financiero = payload.pop("estado_financiero")
    return JsonResponse(
        {
            "ok": True,
            "asistencia": payload,
            "estado_financiero": estado_financiero,
            "mensaje": f"Asistencia guardada: {payload['estado_label']}.",
        }
    )


@role_required(ROLE_ADMIN, permitir_staff_global=False)
def sesion_edit(request, pk):
    """Edita una sesión existente."""
    context = nav_context(request, permitir_staff_global=False)
    sesion = get_object_or_404(
        sesiones_visibles_para_usuario(request.user),
        pk=pk,
    )
    if not _usuario_puede_administrar_sesion(request.user, sesion):
        raise Http404
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
        antes = _snapshot_sesion(sesion)
        sesion.disciplina = form.cleaned_data["disciplina"]
        sesion.fecha = form.cleaned_data["fecha"] or sesion.fecha
        sesion.save(update_fields=["disciplina", "fecha"])
        sesion.profesores.set(form.cleaned_data["profesores"])
        asegurar_asignaciones_profesores(
            disciplina=sesion.disciplina,
            profesores=form.cleaned_data["profesores"],
            user=request.user,
        )
        despues = _snapshot_sesion(sesion)
        cambios = {
            "disciplina_id": {"antes": antes["disciplina_id"], "despues": despues["disciplina_id"]},
            "fecha": {"antes": antes["fecha"], "despues": despues["fecha"]},
            "profesor_ids": {"antes": antes["profesor_ids"], "despues": despues["profesor_ids"]},
        }
        cambios = {campo: cambio for campo, cambio in cambios.items() if cambio["antes"] != cambio["despues"]}
        if cambios:
            registrar_auditoria(
                usuario=request.user,
                accion=AuditLog.ACCION_EDITAR,
                dominio="asistencias",
                objeto=sesion,
                organizacion=sesion.disciplina.organizacion,
                resumen="Sesión actualizada",
                metadata={"cambios": cambios, **_metadata_sesion(sesion)},
            )
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

import csv
import mimetypes
import uuid

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.clickjacking import xframe_options_sameorigin

from auditoria.models import AuditLog
from auditoria.services import registrar_auditoria, registrar_cambio
from asistencias.forms import PersonaRapidaForm
from plataformaelemental.context import (
    descripcion_periodo,
    organizacion_desde_request,
    organizaciones_visibles_para_usuario,
    resolver_periodo,
)
from plataformaelemental.exports import periodo_sufijo_archivo, xlsx_response
from asistencias.selectors import resumen_profesores_periodo_queryset
from asistencias.services.exportaciones import (
    PAGOS_PROFESORES_XLSX_HEADERS,
    filas_export_pagos_profesores,
)

from .decorators import (
    exportar_finanzas_required,
    finanzas_read_required,
    pagos_required,
    revertir_pago_required,
    transacciones_required,
)
from personas.permissions import (
    ACCION_OPERAR_PAGOS,
    ACCION_OPERAR_TRANSACCIONES,
    ACCION_REVERTIR_PAGO,
    usuario_tiene_permiso,
)
from .forms import (
    CategoryForm,
    PaymentForm,
    PagoMasivoForm,
    PaymentPlanForm,
    ReversaPagoForm,
    TransactionForm,
)
from .forms_helpers import (
    ayuda_finanzas as _ayuda_finanzas,
    base_context as _base_context,
    redirect_with_query as _redirect_with_query,
    url_pago_edit_sin_edicion as _url_pago_edit_sin_edicion,
    tipo_visualizacion_archivo as _tipo_visualizacion_archivo,
    url_pagos_list_con_edicion as _url_pagos_list_con_edicion,
    url_pagos_list_sin_edicion as _url_pagos_list_sin_edicion,
    url_with_query as _url_with_query,
    url_with_query_without as _url_with_query_without,
)
from .models import Category, LotePago, Payment, PaymentPlan, Transaction
from .services.cuadratura_v1 import prepare_month, serialize_contract
from personas.models import Persona
from personas.search import filtrar_por_fragmentos
from .selectors import (
    categorias_queryset,
    consolidado_categorias_queryset,
    dashboard_querysets,
    libro_caja_queryset,
    pago_detail_queryset,
    pagos_export_queryset,
    pagos_queryset,
    planes_queryset,
    resumen_pagos,
    resumen_transacciones,
    transacciones_export_queryset,
    transacciones_queryset,
)
from .services.pagos import (
    confirmar_lote_pagos,
    crear_persona_estudiante_desde_modal,
    crear_pago_operacional,
    enriquecer_pagos_para_listado,
    resumen_consumos_pago,
    sincronizar_transaccion_pago,
)
from .services.reversas import revertir_pago
from .services.reportes import (
    PAGOS_ALUMNOS_XLSX_HEADERS,
    PAGOS_CSV_HEADERS,
    TRANSACCIONES_CSV_HEADERS,
    TRANSACCIONES_XLSX_HEADERS,
    armar_dashboard_financiero,
    armar_reporte_categorias,
    LIBRO_CAJA_CSV_HEADERS,
    filas_export_libro_caja,
    filas_export_pagos,
    filas_export_pagos_alumnos_xlsx,
    filas_export_transacciones,
    filas_export_transacciones_xlsx,
)


PAGO_AUDIT_FIELDS = [
    "persona_id",
    "organizacion_id",
    "plan_id",
    "fecha_pago",
    "metodo_pago",
    "monto_referencia",
    "monto_total",
    "clases_asignadas",
]
TRANSACCION_AUDIT_FIELDS = [
    "organizacion_id",
    "categoria_id",
    "fecha",
    "tipo",
    "monto",
    "descripcion",
]


def _queryset_en_organizacion_activa(queryset, request):
    """Restringe recursos organizacionales a la organización activa del request."""
    organizacion = organizacion_desde_request(request)
    return queryset.filter(organizacion=organizacion) if organizacion is not None else queryset


def _snapshot_pago(pago):
    return {campo: getattr(pago, campo) for campo in PAGO_AUDIT_FIELDS}


def _snapshot_transaccion(transaccion):
    return {campo: getattr(transaccion, campo) for campo in TRANSACCION_AUDIT_FIELDS}


def _url_dashboard_accion(request, nombre_url, **extra_params):
    url = reverse(nombre_url)
    params = request.GET.copy()
    for key, value in extra_params.items():
        params[key] = value
    query = params.urlencode()
    return f"{url}?{query}" if query else url


@finanzas_read_required
def dashboard(request):
    context = _base_context(request)
    organizacion = organizacion_desde_request(request)
    periodo = resolver_periodo(request)
    pagos_qs, trans_qs, consumos_qs = dashboard_querysets(request, organizacion=organizacion)
    context.update(
        armar_dashboard_financiero(
            pagos_qs=pagos_qs,
            transacciones_qs=trans_qs,
            consumos_qs=consumos_qs,
            periodo_descripcion=descripcion_periodo(request=request, corta=False),
            organizacion=organizacion,
            mes=periodo["mes"],
            anio=periodo["anio"],
        )
    )
    context["ayuda_seccion"] = _ayuda_finanzas("dashboard")
    context["puede_operar_pagos"] = usuario_tiene_permiso(
        request.user,
        ACCION_OPERAR_PAGOS,
        organizacion=organizacion,
    )
    context["puede_operar_transacciones"] = usuario_tiene_permiso(
        request.user,
        ACCION_OPERAR_TRANSACCIONES,
        organizacion=organizacion,
    )
    context["agregar_pago_url"] = _url_dashboard_accion(request, "finanzas:pagos_list", open="registrar_pago")
    context["agregar_transaccion_url"] = _url_dashboard_accion(
        request,
        "finanzas:transacciones_list",
        open="nueva_transaccion",
    )
    return render(request, "finanzas/dashboard.html", context)


@pagos_required
def planes_list(request):
    context = _base_context(request)
    organizacion = organizacion_desde_request(request)
    planes_qs = planes_queryset(organizacion=organizacion)

    form = PaymentPlanForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Plan de pago creado.")
        return _redirect_with_query(request, "finanzas:planes_list")

    context.update(
        {
            "planes": planes_qs,
            "form": form,
            "edit_form": None,
            "editing_plan_id": None,
            "ayuda_seccion": _ayuda_finanzas("planes"),
        }
    )
    return render(request, "finanzas/planes_list.html", context)


@pagos_required
def plan_edit(request, pk):
    context = _base_context(request)
    organizacion = organizacion_desde_request(request)
    plan = get_object_or_404(_queryset_en_organizacion_activa(PaymentPlan.objects.all(), request), pk=pk)
    planes_qs = planes_queryset(organizacion=organizacion)

    form_creacion = PaymentPlanForm()
    form_edicion = PaymentPlanForm(request.POST or None, instance=plan)
    if request.method == "POST" and form_edicion.is_valid():
        form_edicion.save()
        messages.success(request, "Plan actualizado.")
        return _redirect_with_query(request, "finanzas:planes_list")

    context.update(
        {
            "planes": planes_qs,
            "form": form_creacion,
            "edit_form": form_edicion,
            "editing_plan_id": plan.pk,
            "ayuda_seccion": _ayuda_finanzas("planes"),
        }
    )
    return render(request, "finanzas/planes_list.html", context)


@pagos_required
def plan_delete(request, pk):
    plan = get_object_or_404(_queryset_en_organizacion_activa(PaymentPlan.objects.all(), request), pk=pk)
    if request.method == "POST":
        plan.delete()
        messages.success(request, "Plan eliminado.")
        return _redirect_with_query(request, "finanzas:planes_list")
    return render(
        request,
        "finanzas/confirm_delete.html",
        {"obj": plan, "title": "Eliminar plan", "back_url": _url_with_query(request, "finanzas:planes_list")},
    )


def _contexto_pagos_list(request, *, form=None, edit_form=None, edit_pago=None, persona_form=None, open_nueva_persona=False):
    context = _base_context(request)
    periodo = resolver_periodo(request)
    organizacion = organizacion_desde_request(request)
    pagos_qs = pagos_queryset(request, organizacion=organizacion, mes=periodo["mes"], anio=periodo["anio"])
    q = request.GET.get("q")
    metodo = request.GET.get("metodo")
    persona_id = request.GET.get("persona")
    persona_filtrada = None
    if persona_id and persona_id.isdigit():
        personas_visibles = Persona.objects.filter(pk=persona_id)
        if organizacion:
            personas_visibles = personas_visibles.filter(
                roles__activo=True,
                roles__organizacion=organizacion,
            )
        persona_filtrada = personas_visibles.distinct().first()
    query_sin_persona = request.GET.copy()
    query_sin_persona.pop("persona", None)

    resumen_pagos_data = resumen_pagos(pagos_qs)
    pagos = enriquecer_pagos_para_listado(list(pagos_qs))
    for pago in pagos:
        pago.url_edicion = _url_pagos_list_con_edicion(request, pago.pk)
    if form is None:
        form_initial = {"organizacion": organizacion.pk} if organizacion else {}
        if persona_id:
            form_initial["persona"] = persona_id
        form = PaymentForm(
            initial=form_initial or None,
            periodo_mes=periodo["mes"],
            periodo_anio=periodo["anio"],
            organizacion=organizacion,
        )
    if persona_form is None:
        persona_form = PersonaRapidaForm()

    editar_pago_id = request.GET.get("editar_pago")
    if not edit_form and editar_pago_id:
        edit_pago = get_object_or_404(
            _queryset_en_organizacion_activa(
                Payment.objects.select_related("persona", "organizacion", "plan"), request
            ),
            revertido_en__isnull=True,
            pk=editar_pago_id,
        )
        edit_form = PaymentForm(
            instance=edit_pago,
            prefix="edit_pago",
            periodo_mes=periodo["mes"],
            periodo_anio=periodo["anio"],
            organizacion=organizacion,
        )

    context.update(
        {
            "pagos": pagos,
            "form": form,
            "metodos_pago": Payment.Metodo.choices,
            "q": q or "",
            "metodo": metodo or "",
            "persona_filtrada": persona_filtrada,
            "query_sin_persona": query_sin_persona.urlencode(),
            "total_pagos_monto": resumen_pagos_data["total_pagos_monto"] or 0,
            "total_iva_monto": resumen_pagos_data["total_iva_monto"] or 0,
            "total_clases_pagadas": resumen_pagos_data["total_clases_pagadas"] or 0,
            "total_saldo_clases": resumen_pagos_data["total_saldo_clases"] or 0,
            "edit_form": edit_form,
            "edit_pago": edit_pago,
            "edit_pago_action_url": _url_pago_edit_sin_edicion(request, edit_pago.pk) if edit_pago else "",
            "pagos_list_url_sin_edicion": _url_pagos_list_sin_edicion(request),
            "persona_form": persona_form,
            "open_nueva_persona": open_nueva_persona,
            "open_registrar_pago": request.GET.get("open") == "registrar_pago",
            "puede_revertir_pago": usuario_tiene_permiso(
                request.user,
                ACCION_REVERTIR_PAGO,
                organizacion=organizacion,
            ),
            "ayuda_seccion": _ayuda_finanzas("pagos"),
        }
    )
    return context


@pagos_required
def pagos_list(request):
    organizacion = organizacion_desde_request(request)
    periodo = resolver_periodo(request)
    form_initial = {"organizacion": organizacion.pk} if organizacion else {}
    if request.GET.get("persona"):
        form_initial["persona"] = request.GET.get("persona")
    form = PaymentForm(
        request.POST if request.method == "POST" and "guardar_pago" in request.POST else None,
        initial=form_initial or None,
        periodo_mes=periodo["mes"],
        periodo_anio=periodo["anio"],
        organizacion=organizacion,
    )
    persona_form = PersonaRapidaForm(
        request.POST if request.method == "POST" and "agregar_persona" in request.POST else None
    )
    open_nueva_persona = False

    if request.method == "POST":
        if "agregar_persona" in request.POST:
            open_nueva_persona = True
            if persona_form.is_valid():
                persona = crear_persona_estudiante_desde_modal(form=persona_form, organizacion=organizacion)
                if persona:
                    registrar_auditoria(
                        usuario=request.user,
                        accion=AuditLog.ACCION_CREAR,
                        dominio="personas",
                        objeto=persona,
                        organizacion=organizacion,
                        resumen="Persona creada desde finanzas",
                        metadata={"persona_id": persona.pk, "origen": "pagos_list"},
                    )
                    messages.success(request, "Persona creada y asignada como estudiante.")
                    return _redirect_with_query(request, "finanzas:pagos_list")
        elif form.is_valid():
            crear_pago_operacional(pago=form.save(commit=False), usuario=request.user)
            messages.success(request, "Pago registrado.")
            return redirect(
                _url_with_query_without(
                    request,
                    "finanzas:pagos_list",
                    remove_params=["open"],
                )
            )

    context = _contexto_pagos_list(request, form=form, persona_form=persona_form, open_nueva_persona=open_nueva_persona)
    return render(request, "finanzas/pagos_list.html", context)


def _organizaciones_pago_masivo(user):
    organizaciones = organizaciones_visibles_para_usuario(user, permitir_staff_global=False)
    if getattr(user, "is_superuser", False):
        return organizaciones
    ids = [
        organizacion.pk
        for organizacion in organizaciones
        if usuario_tiene_permiso(
            user,
            ACCION_OPERAR_PAGOS,
            organizacion=organizacion,
            permitir_staff_global=False,
        )
    ]
    return organizaciones.filter(pk__in=ids)


def _organizacion_pago_masivo(request):
    raw = request.POST.get("organizacion") or request.GET.get("organizacion")
    try:
        organizacion_id = int(raw)
    except (TypeError, ValueError):
        return None
    return _organizaciones_pago_masivo(request.user).filter(pk=organizacion_id).first()


def _pago_masivo_form(request, *, organizacion, data=None, initial=None):
    organizaciones = _organizaciones_pago_masivo(request.user)
    personas = Persona.objects.filter(
        roles__organizacion=organizacion,
        roles__rol__codigo__iexact="ESTUDIANTE",
        roles__activo=True,
    ).distinct().order_by("apellidos", "nombres") if organizacion else Persona.objects.none()
    planes = PaymentPlan.objects.filter(organizacion=organizacion, activo=True).order_by("-es_por_defecto", "nombre") if organizacion else PaymentPlan.objects.none()
    initial = dict(initial or {})
    if organizacion and data is None:
        plan_defecto = planes.filter(es_por_defecto=True).first()
        if plan_defecto:
            initial.setdefault("plan", plan_defecto.pk)
        initial.setdefault("aplica_iva", not organizacion.es_exenta_iva)
        initial.setdefault("fecha_pago", timezone.localdate())
    return PagoMasivoForm(
        data=data,
        initial=initial,
        organizaciones=organizaciones,
        personas=personas,
        planes=planes,
    )


def _filas_pago_masivo(request, form):
    organizacion = form.cleaned_data["organizacion"]
    comunes = form.cleaned_data
    overrides = form.cleaned_data.get("filas_json") or {}
    filas = []
    errores = {}
    for persona_id in form.cleaned_data["personas_seleccionadas"]:
        override = overrides.get(str(persona_id), {})
        if not isinstance(override, dict):
            override = {}
        datos = {
            "organizacion": organizacion.pk,
            "persona": persona_id,
            "plan": override.get("plan", comunes["plan"].pk if comunes.get("plan") else ""),
            "fecha_pago": override.get("fecha_pago", comunes["fecha_pago"].isoformat()),
            "metodo_pago": override.get("metodo_pago", comunes["metodo_pago"]),
            "numero_comprobante": override.get("numero_comprobante", comunes.get("numero_comprobante", "")),
            "aplica_iva": override.get("aplica_iva", comunes.get("aplica_iva", True)),
            "monto_incluye_iva": override.get("monto_incluye_iva", comunes.get("monto_incluye_iva", False)),
            "monto_referencia": override.get("monto_referencia", str(comunes["monto_referencia"])),
            "clases_asignadas": override.get("clases_asignadas", comunes.get("clases_asignadas") or 0),
            "observaciones": override.get("observaciones", comunes.get("observaciones", "")),
        }
        fila_form = PaymentForm(
            data=datos,
            periodo_mes=resolver_periodo(request)["mes"],
            periodo_anio=resolver_periodo(request)["anio"],
            organizacion=organizacion,
        )
        if fila_form.is_valid():
            cleaned = fila_form.cleaned_data
            plan = cleaned.get("plan")
            clases_asignadas = cleaned.get("clases_asignadas") or (plan.num_clases if plan else 0)
            monto_referencia = cleaned["monto_referencia"]
            pago_preview = Payment(
                persona=cleaned["persona"],
                organizacion=organizacion,
                plan=plan,
                aplica_iva=cleaned.get("aplica_iva", True),
                monto_incluye_iva=cleaned.get("monto_incluye_iva", False),
                monto_referencia=monto_referencia,
            )
            monto_neto, monto_iva, monto_total = pago_preview.calcular_montos()
            filas.append({
                "persona_id": cleaned["persona"].pk,
                "plan_id": cleaned["plan"].pk if cleaned.get("plan") else None,
                "fecha_pago": cleaned["fecha_pago"],
                "metodo_pago": cleaned["metodo_pago"],
                "numero_comprobante": cleaned.get("numero_comprobante", ""),
                "aplica_iva": cleaned.get("aplica_iva", True),
                "monto_incluye_iva": cleaned.get("monto_incluye_iva", False),
                "monto_referencia": cleaned["monto_referencia"],
                "observaciones": cleaned.get("observaciones", ""),
                "persona": cleaned["persona"],
                "plan": plan,
                "monto_neto": monto_neto,
                "monto_iva": monto_iva,
                "monto_total": monto_total,
                "clases_asignadas": clases_asignadas,
            })
        else:
            persona = getattr(form, "personas_seleccionadas_obj", {}).get(persona_id)
            filas.append(
                {
                    "persona": persona,
                    "plan": comunes.get("plan"),
                    "metodo_pago": comunes.get("metodo_pago", ""),
                    "monto_neto": 0,
                    "monto_iva": 0,
                    "monto_total": 0,
                    "clases_asignadas": comunes.get("clases_asignadas") or 0,
                    "aplica_iva": comunes.get("aplica_iva", True),
                }
            )
            errores[persona_id] = fila_form.errors.get_json_data()
    return filas, errores


@login_required
def pago_masivo_personas(request):
    organizacion = _organizacion_pago_masivo(request)
    if not organizacion:
        return JsonResponse({"ok": False, "codigo": "PERMISO_DENEGADO", "mensaje": "Organización no autorizada."}, status=404)
    query = " ".join((request.GET.get("q") or "").split())
    personas = Persona.objects.filter(
        roles__organizacion=organizacion,
        roles__rol__codigo__iexact="ESTUDIANTE",
        roles__activo=True,
    ).distinct()
    if query:
        personas = filtrar_por_fragmentos(
            personas,
            query,
            campos=("nombres", "apellidos", "email", "rut"),
            prefijo="persona_pago_masivo",
        )
    resultados = personas.order_by("apellidos", "nombres")[:20]
    return JsonResponse({"ok": True, "resultados": [{"id": p.pk, "nombre": p.nombre_completo} for p in resultados]})


@login_required
def pago_masivo(request):
    organizacion = _organizacion_pago_masivo(request)
    if request.method == "GET" and not organizacion:
        form = _pago_masivo_form(request, organizacion=None, initial={"clave_idempotencia": uuid.uuid4().hex})
        return render(request, "finanzas/pago_masivo.html", {"form": form, "organizaciones": _organizaciones_pago_masivo(request.user)})
    if not organizacion or not usuario_tiene_permiso(
        request.user, ACCION_OPERAR_PAGOS, organizacion=organizacion, permitir_staff_global=False
    ):
        return HttpResponse("No autorizado.", status=404)

    data = request.POST or None
    if request.method == "GET":
        data = None
    form = _pago_masivo_form(
        request,
        organizacion=organizacion,
        data=data,
        initial={"organizacion": organizacion.pk, "clave_idempotencia": uuid.uuid4().hex},
    )
    filas = []
    errores_filas = {}
    preview = False
    if request.method == "POST" and form.is_valid():
        filas, errores_filas = _filas_pago_masivo(request, form)
        preview = request.POST.get("accion") == "preview"
        if request.POST.get("accion") == "confirmar" and not errores_filas:
            lote, creado = confirmar_lote_pagos(
                usuario=request.user,
                organizacion_id=organizacion.pk,
                clave_idempotencia=form.cleaned_data["clave_idempotencia"],
                filas=filas,
                metadatos={"personas": form.cleaned_data["personas_seleccionadas"]},
            )
            if not creado:
                messages.info(request, "Esta clave ya fue procesada; se muestra el lote existente.")
            return redirect("finanzas:pago_masivo_resultado", pk=lote.pk)
    contexto = {
        "form": form,
        "organizaciones": _organizaciones_pago_masivo(request.user),
        "organizacion": organizacion,
        "filas": filas,
        "errores_filas": errores_filas,
        "preview": preview,
        "plan_options": form.fields["plan"].queryset,
        "personas_iniciales": [
            {"id": persona.pk, "nombre": persona.nombre_completo}
            for persona in getattr(form, "personas_queryset", Persona.objects.none()).filter(
                pk__in=[value for value in (request.POST.get("personas_seleccionadas", "").split(",")) if value.isdigit()]
            )
        ],
    }
    return render(request, "finanzas/pago_masivo.html", contexto)


@login_required
def pago_masivo_resultado(request, pk):
    lote = get_object_or_404(
        LotePago.objects.prefetch_related("pagos__persona"),
        pk=pk,
    )
    if not usuario_tiene_permiso(
        request.user, ACCION_OPERAR_PAGOS, organizacion=lote.organizacion, permitir_staff_global=False
    ):
        raise Http404
    return render(request, "finanzas/pago_masivo_resultado.html", {"lote": lote})


@pagos_required
def pago_edit(request, pk):
    pago = get_object_or_404(
        _queryset_en_organizacion_activa(Payment.objects.filter(revertido_en__isnull=True), request),
        pk=pk,
    )
    if request.method == "GET":
        return redirect(_url_pagos_list_con_edicion(request, pago.pk))

    periodo = resolver_periodo(request)
    organizacion = organizacion_desde_request(request)
    antes = _snapshot_pago(pago) if request.method == "POST" else None
    form = PaymentForm(
        request.POST or None,
        instance=pago,
        prefix="edit_pago",
        periodo_mes=periodo["mes"],
        periodo_anio=periodo["anio"],
        organizacion=organizacion,
    )
    if request.method == "POST" and form.is_valid():
        pago = form.save()
        sincronizar_transaccion_pago(pago=pago, usuario=request.user)
        registrar_cambio(
            usuario=request.user,
            dominio="finanzas",
            objeto=pago,
            organizacion=pago.organizacion,
            resumen="Pago actualizado",
            antes=antes,
            despues=_snapshot_pago(pago),
            campos=PAGO_AUDIT_FIELDS,
        )
        messages.success(request, "Pago actualizado.")
        return redirect(_url_pagos_list_sin_edicion(request))
    context = _contexto_pagos_list(request, edit_form=form, edit_pago=pago)
    return render(request, "finanzas/pagos_list.html", context)


@finanzas_read_required
def pago_detail(request, pk):
    context = _base_context(request)
    pago = get_object_or_404(_queryset_en_organizacion_activa(pago_detail_queryset(), request), pk=pk)
    resumen_consumos = resumen_consumos_pago(pago)
    context.update(
        {
            "pago": pago,
            "consumos": resumen_consumos["consumos"],
            "consumos_consumidos": resumen_consumos["consumos_consumidos"],
            "consumos_pendientes": resumen_consumos["consumos_pendientes"],
            "consumos_deuda": resumen_consumos["consumos_deuda"],
            "saldo_clases": resumen_consumos["saldo_clases"],
            "back_url": request.META.get("HTTP_REFERER") or _url_with_query(request, "finanzas:pagos_list"),
        }
    )
    return render(request, "finanzas/pago_detail.html", context)


@revertir_pago_required
def pago_revertir(request, pk):
    pago = get_object_or_404(_queryset_en_organizacion_activa(Payment.objects.all(), request), pk=pk)
    form = ReversaPagoForm(request.POST or None)
    if request.method == "POST":
        if form.is_valid():
            try:
                revertir_pago(
                    pago=pago,
                    motivo=form.cleaned_data["motivo"],
                    usuario=request.user,
                )
            except ValidationError as exc:
                form.add_error(None, exc.messages[0])
            else:
                messages.success(request, "Pago revertido.")
                return _redirect_with_query(request, "finanzas:pagos_list")
    return render(
        request,
        "finanzas/pago_revertir.html",
        {
            "pago": pago,
            "form": form,
            "back_url": _url_with_query(request, "finanzas:pagos_list"),
        },
    )


@transacciones_required
def categorias_list(request):
    context = _base_context(request)
    categorias_qs = categorias_queryset()
    form = CategoryForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Categoria creada.")
        return _redirect_with_query(request, "finanzas:categorias_list")
    context.update({"categorias": categorias_qs, "form": form, "ayuda_seccion": _ayuda_finanzas("categorias")})
    return render(request, "finanzas/categorias_list.html", context)


@transacciones_required
def categoria_edit(request, pk):
    categoria = get_object_or_404(Category, pk=pk)
    form = CategoryForm(request.POST or None, instance=categoria)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Categoria actualizada.")
        return _redirect_with_query(request, "finanzas:categorias_list")
    return render(
        request,
        "finanzas/form_page.html",
        {"form": form, "title": "Editar categoria", "back_url": _url_with_query(request, "finanzas:categorias_list")},
    )


@transacciones_required
def categoria_delete(request, pk):
    categoria = get_object_or_404(Category, pk=pk)
    if request.method == "POST":
        categoria.delete()
        messages.success(request, "Categoria eliminada.")
        return _redirect_with_query(request, "finanzas:categorias_list")
    return render(
        request,
        "finanzas/confirm_delete.html",
        {"obj": categoria, "title": "Eliminar categoria", "back_url": _url_with_query(request, "finanzas:categorias_list")},
    )


@transacciones_required
def transacciones_list(request):
    context = _base_context(request)
    organizacion = organizacion_desde_request(request)
    periodo = resolver_periodo(request)
    trans_qs = transacciones_queryset(request, organizacion=organizacion)
    resumen_transacciones_data = resumen_transacciones(trans_qs)
    total_ingresos = resumen_transacciones_data["total_ingresos"] or 0
    total_egresos = resumen_transacciones_data["total_egresos"] or 0

    form = TransactionForm(
        request.POST or None,
        request.FILES or None,
        initial={"organizacion": organizacion.pk} if organizacion else None,
        periodo_mes=periodo["mes"],
        periodo_anio=periodo["anio"],
        organizacion=organizacion,
    )
    if request.method == "POST" and form.is_valid():
        transaccion = form.save()
        registrar_auditoria(
            usuario=request.user,
            accion=AuditLog.ACCION_CREAR,
            dominio="finanzas",
            objeto=transaccion,
            organizacion=transaccion.organizacion,
            resumen="Transacción creada",
            metadata=_snapshot_transaccion(transaccion),
        )
        messages.success(request, "Transaccion registrada.")
        return _redirect_with_query(request, "finanzas:transacciones_list")

    context.update(
        {
            "transacciones": trans_qs,
            "form": form,
            "total_transacciones": resumen_transacciones_data["total_transacciones"] or 0,
            "total_ingresos": total_ingresos,
            "total_egresos": total_egresos,
            "balance_transacciones": total_ingresos - total_egresos,
            "open_nueva_transaccion": request.GET.get("open") == "nueva_transaccion",
            "ayuda_seccion": _ayuda_finanzas("transacciones"),
        }
    )
    return render(request, "finanzas/transacciones_list.html", context)


@finanzas_read_required
def transaccion_detail(request, pk):
    context = _base_context(request)
    transaccion = get_object_or_404(
        _queryset_en_organizacion_activa(
            Transaction.objects.select_related("organizacion", "categoria"),
            request,
        ),
        pk=pk,
    )
    tipo_archivo = _tipo_visualizacion_archivo(transaccion.archivo.name if transaccion.archivo else "")
    context.update(
        {
            "transaccion": transaccion,
            "archivo_es_pdf": tipo_archivo["es_pdf"],
            "archivo_es_imagen": tipo_archivo["es_imagen"],
            "ayuda_seccion": _ayuda_finanzas("transacciones"),
            "back_url": request.META.get("HTTP_REFERER") or _url_with_query(request, "finanzas:transacciones_list"),
        }
    )
    return render(request, "finanzas/transaccion_detail.html", context)


@finanzas_read_required
@xframe_options_sameorigin
def transaccion_archivo(request, pk):
    transaccion = get_object_or_404(_queryset_en_organizacion_activa(Transaction.objects.all(), request), pk=pk)
    if not transaccion.archivo:
        raise Http404("La transaccion no tiene archivo adjunto.")

    content_type, _ = mimetypes.guess_type(transaccion.archivo.name)
    response = FileResponse(
        transaccion.archivo.open("rb"),
        as_attachment=False,
        filename=transaccion.archivo.name.rsplit("/", 1)[-1],
        content_type=content_type or "application/octet-stream",
    )
    response["Content-Disposition"] = f'inline; filename="{transaccion.archivo.name.rsplit("/", 1)[-1]}"'
    return response


@transacciones_required
def transaccion_edit(request, pk):
    transaccion = get_object_or_404(_queryset_en_organizacion_activa(Transaction.objects.all(), request), pk=pk)
    periodo = resolver_periodo(request)
    organizacion = organizacion_desde_request(request)
    antes = _snapshot_transaccion(transaccion) if request.method == "POST" else None
    form = TransactionForm(
        request.POST or None,
        request.FILES or None,
        instance=transaccion,
        periodo_mes=periodo["mes"],
        periodo_anio=periodo["anio"],
        organizacion=organizacion,
    )
    if request.method == "POST" and form.is_valid():
        transaccion = form.save()
        registrar_cambio(
            usuario=request.user,
            dominio="finanzas",
            objeto=transaccion,
            organizacion=transaccion.organizacion,
            resumen="Transacción actualizada",
            antes=antes,
            despues=_snapshot_transaccion(transaccion),
            campos=TRANSACCION_AUDIT_FIELDS,
        )
        messages.success(request, "Transaccion actualizada.")
        return _redirect_with_query(request, "finanzas:transacciones_list")
    return render(
        request,
        "finanzas/form_page.html",
        {"form": form, "title": "Editar transaccion", "back_url": _url_with_query(request, "finanzas:transacciones_list")},
    )


@transacciones_required
def transaccion_delete(request, pk):
    transaccion = get_object_or_404(_queryset_en_organizacion_activa(Transaction.objects.all(), request), pk=pk)
    if request.method == "POST":
        registrar_auditoria(
            usuario=request.user,
            accion=AuditLog.ACCION_ELIMINAR,
            dominio="finanzas",
            objeto=transaccion,
            organizacion=transaccion.organizacion,
            resumen="Transacción eliminada",
            metadata=_snapshot_transaccion(transaccion),
        )
        transaccion.delete()
        messages.success(request, "Transaccion eliminada.")
        return _redirect_with_query(request, "finanzas:transacciones_list")
    return render(
        request,
        "finanzas/confirm_delete.html",
        {"obj": transaccion, "title": "Eliminar transaccion", "back_url": _url_with_query(request, "finanzas:transacciones_list")},
    )


@finanzas_read_required
def reporte_categorias(request):
    context = _base_context(request)
    organizacion = organizacion_desde_request(request)
    context.update(
        armar_reporte_categorias(
            consolidado_qs=consolidado_categorias_queryset(request, organizacion=organizacion),
            periodo_descripcion=descripcion_periodo(request=request, corta=False),
        )
    )
    context["ayuda_seccion"] = _ayuda_finanzas("reporte_categorias")
    return render(request, "finanzas/reporte_categorias.html", context)


@exportar_finanzas_required
def preparar_mes(request):
    periodo = resolver_periodo(request)
    organizacion = organizacion_desde_request(request)
    context = _base_context(request)
    context["preparacion"] = None
    if organizacion and periodo["mes"] and periodo["anio"]:
        context["preparacion"] = prepare_month(
            organization=organizacion, year=periodo["anio"], month=periodo["mes"]
        )
    context["organizacion"] = organizacion
    return render(request, "finanzas/preparar_mes.html", context)


@exportar_finanzas_required
def descargar_cuadratura(request):
    periodo = resolver_periodo(request)
    organizacion = organizacion_desde_request(request)
    if not organizacion or not periodo["mes"] or not periodo["anio"]:
        return HttpResponse(
            "Selecciona una organización, un mes y un año específicos.",
            status=400,
            content_type="text/plain; charset=utf-8",
        )
    payload = prepare_month(
        organization=organizacion, year=periodo["anio"], month=periodo["mes"]
    )
    response = HttpResponse(serialize_contract(payload), content_type="application/json; charset=utf-8")
    response["Content-Disposition"] = (
        f'attachment; filename="elemental_cuadratura_{periodo["anio"]:04d}-{periodo["mes"]:02d}.json"'
    )
    return response


@exportar_finanzas_required
def export_pagos_csv(request):
    organizacion = organizacion_desde_request(request)
    pagos = pagos_export_queryset(request, organizacion=organizacion)

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="pagos_finanzas.csv"'
    writer = csv.writer(response)
    writer.writerow(PAGOS_CSV_HEADERS)
    writer.writerows(filas_export_pagos(pagos))
    return response


@exportar_finanzas_required
def export_pagos_alumnos_xlsx(request):
    periodo = resolver_periodo(request)
    organizacion = organizacion_desde_request(request)
    pagos = pagos_export_queryset(request, organizacion=organizacion)
    return xlsx_response(
        filename=f"pagos_alumnos_{periodo_sufijo_archivo(periodo)}.xlsx",
        sheet_title="Pagos alumnos",
        headers=PAGOS_ALUMNOS_XLSX_HEADERS,
        rows=filas_export_pagos_alumnos_xlsx(pagos),
    )


@exportar_finanzas_required
def export_transacciones_csv(request):
    organizacion = organizacion_desde_request(request)
    transacciones = transacciones_export_queryset(request, organizacion=organizacion)

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="transacciones_finanzas.csv"'
    writer = csv.writer(response)
    writer.writerow(TRANSACCIONES_CSV_HEADERS)
    writer.writerows(filas_export_transacciones(transacciones))
    return response


@exportar_finanzas_required
def export_transacciones_xlsx(request):
    periodo = resolver_periodo(request)
    organizacion = organizacion_desde_request(request)
    transacciones = transacciones_export_queryset(request, organizacion=organizacion)
    return xlsx_response(
        filename=f"transacciones_{periodo_sufijo_archivo(periodo)}.xlsx",
        sheet_title="Transacciones",
        headers=TRANSACCIONES_XLSX_HEADERS,
        rows=filas_export_transacciones_xlsx(transacciones),
    )


@exportar_finanzas_required
def export_pagos_profesores_xlsx(request):
    periodo = resolver_periodo(request)
    organizacion = organizacion_desde_request(request)
    roles, asistencias_por_profesor, sesiones_por_profesor, disciplinas_por_profesor = (
        resumen_profesores_periodo_queryset(request, organizacion=organizacion)
    )
    return xlsx_response(
        filename=f"estimacion_pagos_profesores_{periodo_sufijo_archivo(periodo)}.xlsx",
        sheet_title="Estimacion profesores",
        headers=PAGOS_PROFESORES_XLSX_HEADERS,
        rows=filas_export_pagos_profesores(
            roles,
            asistencias_por_profesor=asistencias_por_profesor,
            sesiones_por_profesor=sesiones_por_profesor,
            disciplinas_por_profesor=disciplinas_por_profesor,
            periodo_descripcion=descripcion_periodo(request=request, corta=True),
        ),
    )


@exportar_finanzas_required
def export_libro_caja_csv(request):
    periodo = resolver_periodo(request)
    if periodo["mes"] is None or periodo["anio"] is None:
        return HttpResponse(
            "El libro de caja requiere seleccionar un mes y un año especificos.",
            status=400,
            content_type="text/plain; charset=utf-8",
        )
    organizacion = organizacion_desde_request(request)
    transacciones = libro_caja_queryset(request, organizacion=organizacion)

    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="libro_caja.csv"'
    response.write("\ufeff")
    writer = csv.writer(response)
    writer.writerow(LIBRO_CAJA_CSV_HEADERS)
    writer.writerows(filas_export_libro_caja(transacciones))
    return response

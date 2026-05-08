import csv
import json
import mimetypes
from pathlib import Path
from decimal import Decimal

from django.contrib import messages
from django.core.files import File
from django.db import IntegrityError
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.clickjacking import xframe_options_sameorigin

from asistencias.forms import PersonaRapidaForm
from personas.models import Persona, PersonaRol, Rol
from plataformaelemental.context import (
    descripcion_periodo,
    organizacion_desde_request,
    resolver_periodo,
)

from .documentos.dtos import NormalizedTaxDocument
from .documentos.services import build_review_payload, parse_tax_document
from .documentos.temp_storage import (
    actualizar_payload_importacion,
    cargar_archivo_importacion_temporal,
    cargar_importacion_temporal,
    eliminar_importacion_temporal,
    guardar_importacion_temporal,
)
from .decorators import admin_finanzas_required
from .forms import (
    CategoryForm,
    DocumentoTributarioForm,
    DocumentoTributarioImportConfirmForm,
    DocumentoTributarioImportUploadForm,
    PaymentForm,
    PaymentPlanForm,
    TransactionForm,
)
from .forms_helpers import (
    agregar_error_conflicto_documento as _agregar_error_conflicto_documento,
    ayuda_finanzas as _ayuda_finanzas,
    base_context as _base_context,
    redirect_with_query as _redirect_with_query,
    tipo_visualizacion_archivo as _tipo_visualizacion_archivo,
    url_pagos_list_con_edicion as _url_pagos_list_con_edicion,
    url_with_query as _url_with_query,
)
from .models import AttendanceConsumption, Category, DocumentoTributario, Payment, PaymentPlan, Transaction
from .selectors import (
    categorias_queryset,
    consolidado_categorias_queryset,
    dashboard_querysets,
    documentos_tributarios_queryset,
    pago_detail_queryset,
    pagos_export_queryset,
    pagos_queryset,
    planes_queryset,
    resumen_dashboard,
    resumen_documentos_tributarios,
    resumen_pagos,
    resumen_transacciones,
    transacciones_export_queryset,
    transacciones_queryset,
)


def _crear_persona_estudiante_desde_filtro(*, form, organizacion):
    rol_estudiante = Rol.objects.filter(codigo="ESTUDIANTE").first()
    if not organizacion:
        form.add_error(
            None,
            "Debes seleccionar una organizacion en el filtro superior antes de crear a la persona.",
        )
        return None
    if not rol_estudiante:
        form.add_error(
            None,
            "No existe el rol ESTUDIANTE configurado para asignar a la nueva persona.",
        )
        return None

    persona = Persona.objects.create(
        nombres=form.cleaned_data["nombres"].strip(),
        apellidos=form.cleaned_data.get("apellidos", "").strip(),
        telefono=form.cleaned_data.get("telefono", "").strip(),
    )
    PersonaRol.objects.get_or_create(
        persona=persona,
        rol=rol_estudiante,
        organizacion=organizacion,
        defaults={"activo": True},
    )
    return persona


def _documento_revision_form(*, data=None, initial=None):
    form = DocumentoTributarioForm(data=data, initial=initial)
    for field_name in ("archivo_pdf", "archivo_xml", "metadata_extra"):
        form.fields[field_name].widget.attrs["class"] = "d-none"
        form.fields[field_name].widget = form.fields[field_name].hidden_widget()
    return form


def _leer_xml_temporal(path):
    try:
        content = Path(path).read_text(encoding="utf-8")
    except UnicodeDecodeError:
        content = Path(path).read_text(encoding="latin-1")
    return content


def _clasificar_archivo_tributario(archivo_subido):
    if not archivo_subido:
        return None, None

    nombre = (archivo_subido.name or "").lower()
    content_type = (getattr(archivo_subido, "content_type", "") or "").lower()

    if nombre.endswith(".xml") or "xml" in content_type:
        return archivo_subido, None
    if nombre.endswith(".pdf") or content_type == "application/pdf":
        return None, archivo_subido

    posicion = archivo_subido.tell()
    encabezado = archivo_subido.read(128)
    archivo_subido.seek(posicion)
    encabezado_limpio = encabezado.lstrip()
    if encabezado.startswith(b"%PDF"):
        return None, archivo_subido
    if encabezado_limpio.startswith(b"<"):
        return archivo_subido, None
    return None, None


def _review_context_from_payload(request, payload, *, token_importacion=None, documento_data=None, pago_data=None):
    organizacion = organizacion_desde_request(request)
    documento_form = _documento_revision_form(
        data=documento_data,
        initial=payload.get("documento_initial"),
    )
    pago_inicial = payload.get("pago_initial")
    pago_form = None
    if pago_inicial:
        pago_form = PaymentForm(
            data=pago_data,
            initial=pago_inicial,
            prefix="pago",
        )
    archivo_pdf_url = ""
    archivo_xml_url = ""
    archivo_xml_preview = ""
    if token_importacion:
        archivo_pdf = cargar_archivo_importacion_temporal(request, token_importacion, "pdf")
        if archivo_pdf:
            archivo_pdf_url = reverse(
                "finanzas:documento_tributario_importacion_archivo",
                kwargs={"token": token_importacion, "tipo_archivo": "pdf"},
            )
        archivo_xml = cargar_archivo_importacion_temporal(request, token_importacion, "xml")
        if archivo_xml:
            archivo_xml_url = reverse(
                "finanzas:documento_tributario_importacion_archivo",
                kwargs={"token": token_importacion, "tipo_archivo": "xml"},
            )
            archivo_xml_preview = _leer_xml_temporal(archivo_xml["path"])
    return {
        "upload_form": DocumentoTributarioImportUploadForm(),
        "confirm_form": DocumentoTributarioImportConfirmForm(
            initial={
                "guardar_pago_sugerido": bool(pago_inicial),
                "token_importacion": token_importacion or "",
            }
        ),
        "documento_form": documento_form,
        "pago_form": pago_form,
        "review_payload": payload,
        "documento_normalizado": NormalizedTaxDocument.from_dict(payload.get("normalized", {})),
        "archivo_importacion_pdf_url": archivo_pdf_url,
        "archivo_importacion_xml_url": archivo_xml_url,
        "archivo_importacion_xml_preview": archivo_xml_preview,
        "ayuda_seccion": {
            "titulo": "Carga asistida",
            "texto": (
                "Sube XML y/o PDF, revisa los formularios precargados y confirma manualmente. "
                "Nada se guarda de forma definitiva hasta el ultimo paso."
            ),
        },
        "organizacion_sugerida_id": organizacion.pk if organizacion else "",
    }


def _metadata_extra_como_dict(value):
    if not value:
        return {}
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    try:
        parsed = json.loads(str(value))
    except (TypeError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _normalizar_rut_basico(value):
    return (value or "").replace(".", "").replace("-", "").replace(" ", "").upper().strip()


def _normalizar_texto_basico(value):
    return " ".join((value or "").upper().split())


def _documento_match_organizacion(documento, lado):
    if lado not in {"emisor", "receptor"}:
        return False
    organizacion = getattr(documento, "organizacion", None)
    if not organizacion:
        return False

    rut_documento = _normalizar_rut_basico(getattr(documento, f"rut_{lado}", ""))
    rut_organizacion = _normalizar_rut_basico(getattr(organizacion, "rut", ""))
    if rut_documento and rut_organizacion and rut_documento == rut_organizacion:
        return True

    nombre_documento = _normalizar_texto_basico(getattr(documento, f"nombre_{lado}", ""))
    nombres_organizacion = {
        _normalizar_texto_basico(getattr(organizacion, "nombre", "")),
        _normalizar_texto_basico(getattr(organizacion, "razon_social", "")),
    }
    nombres_organizacion.discard("")
    return bool(nombre_documento and nombre_documento in nombres_organizacion)


def _rol_financiero_documento(documento):
    es_emisor = _documento_match_organizacion(documento, "emisor")
    es_receptor = _documento_match_organizacion(documento, "receptor")
    if es_emisor and not es_receptor:
        return "ingreso"
    if es_receptor and not es_emisor:
        return "egreso"
    return "sin_clasificar"


@admin_finanzas_required
def dashboard(request):
    context = _base_context(request)
    organizacion = organizacion_desde_request(request)
    pagos_qs, trans_qs = dashboard_querysets(request, organizacion=organizacion)
    resumen = resumen_dashboard(pagos_qs, trans_qs)

    context.update(
        {
            **resumen,
            "pagos_recientes": pagos_qs.select_related("persona", "organizacion")[:10],
            "transacciones_recientes": trans_qs.select_related("categoria", "organizacion")[:10],
            "periodo_descripcion_vista": descripcion_periodo(request=request, corta=False),
            "organizacion_filtro": organizacion,
            "ayuda_seccion": _ayuda_finanzas("dashboard"),
        }
    )
    return render(request, "finanzas/dashboard.html", context)


@admin_finanzas_required
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


@admin_finanzas_required
def plan_edit(request, pk):
    context = _base_context(request)
    organizacion = organizacion_desde_request(request)
    plan = get_object_or_404(PaymentPlan, pk=pk)
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


@admin_finanzas_required
def plan_delete(request, pk):
    plan = get_object_or_404(PaymentPlan, pk=pk)
    if request.method == "POST":
        plan.delete()
        messages.success(request, "Plan eliminado.")
        return _redirect_with_query(request, "finanzas:planes_list")
    return render(
        request,
        "finanzas/confirm_delete.html",
        {"obj": plan, "title": "Eliminar plan", "back_url": _url_with_query(request, "finanzas:planes_list")},
    )


@admin_finanzas_required
def _contexto_pagos_list(request, *, form=None, edit_form=None, edit_pago=None, persona_form=None, open_nueva_persona=False):
    context = _base_context(request)
    periodo = resolver_periodo(request)
    organizacion = organizacion_desde_request(request)
    pagos_qs = pagos_queryset(request, organizacion=organizacion, mes=periodo["mes"], anio=periodo["anio"])
    q = request.GET.get("q")
    metodo = request.GET.get("metodo")

    resumen_pagos_data = resumen_pagos(pagos_qs)
    pagos = list(pagos_qs)
    for pago in pagos:
        disciplina = pago.disciplina_principal_nombre or "Sin disciplina"
        nombre_plan = pago.plan.nombre if pago.plan_id else "Sin plan"
        pago.estado_fiscal_label = "Afecta" if pago.monto_iva else "Exenta"
        pago.estado_fiscal_badge_class = "text-bg-primary" if pago.monto_iva else "text-bg-secondary"
        pago.texto_copia = f"Taller de {disciplina} - {nombre_plan} ({pago.persona.nombre_completo})"
        pago.monto_neto_copia = str(int(pago.monto_neto or 0))
        pago.monto_iva_copia = str(int(pago.monto_iva or 0))
        pago.monto_total_copia = str(int(pago.monto_total or 0))
    if form is None:
        form = PaymentForm(initial={"organizacion": organizacion.pk} if organizacion else None)
    if persona_form is None:
        persona_form = PersonaRapidaForm()

    editar_pago_id = request.GET.get("editar_pago")
    if not edit_form and editar_pago_id:
        edit_pago = get_object_or_404(
            Payment.objects.select_related("persona", "organizacion", "plan", "documento_tributario"),
            pk=editar_pago_id,
        )
        edit_form = PaymentForm(instance=edit_pago, prefix="edit_pago")

    context.update(
        {
            "pagos": pagos,
            "form": form,
            "metodos_pago": Payment.Metodo.choices,
            "q": q or "",
            "metodo": metodo or "",
            "total_pagos_monto": resumen_pagos_data["total_pagos_monto"] or 0,
            "total_iva_monto": resumen_pagos_data["total_iva_monto"] or 0,
            "total_clases_pagadas": resumen_pagos_data["total_clases_pagadas"] or 0,
            "total_saldo_clases": resumen_pagos_data["total_saldo_clases"] or 0,
            "edit_form": edit_form,
            "edit_pago": edit_pago,
            "persona_form": persona_form,
            "open_nueva_persona": open_nueva_persona,
            "ayuda_seccion": _ayuda_finanzas("pagos"),
        }
    )
    return context


@admin_finanzas_required
def pagos_list(request):
    organizacion = organizacion_desde_request(request)
    form = PaymentForm(
        request.POST if request.method == "POST" and "guardar_pago" in request.POST else None,
        initial={"organizacion": organizacion.pk} if organizacion else None,
    )
    persona_form = PersonaRapidaForm(
        request.POST if request.method == "POST" and "agregar_persona" in request.POST else None
    )
    open_nueva_persona = False

    if request.method == "POST":
        if "agregar_persona" in request.POST:
            open_nueva_persona = True
            if persona_form.is_valid():
                persona = _crear_persona_estudiante_desde_filtro(form=persona_form, organizacion=organizacion)
                if persona:
                    messages.success(request, "Persona creada y asignada como estudiante.")
                    return _redirect_with_query(request, "finanzas:pagos_list")
        elif form.is_valid():
            form.save()
            messages.success(request, "Pago registrado.")
            return _redirect_with_query(request, "finanzas:pagos_list")

    context = _contexto_pagos_list(request, form=form, persona_form=persona_form, open_nueva_persona=open_nueva_persona)
    return render(request, "finanzas/pagos_list.html", context)


@admin_finanzas_required
def pago_edit(request, pk):
    pago = get_object_or_404(Payment, pk=pk)
    if request.method == "GET":
        return redirect(_url_pagos_list_con_edicion(request, pago.pk))

    form = PaymentForm(request.POST or None, instance=pago, prefix="edit_pago")
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Pago actualizado.")
        return _redirect_with_query(request, "finanzas:pagos_list")
    context = _contexto_pagos_list(request, edit_form=form, edit_pago=pago)
    return render(request, "finanzas/pagos_list.html", context)


@admin_finanzas_required
def pago_detail(request, pk):
    context = _base_context(request)
    pago = get_object_or_404(pago_detail_queryset(), pk=pk)
    consumos = list(pago.consumos.all())
    consumos_consumidos = sum(1 for item in consumos if item.estado == AttendanceConsumption.Estado.CONSUMIDO)
    consumos_pendientes = sum(1 for item in consumos if item.estado == AttendanceConsumption.Estado.PENDIENTE)
    consumos_deuda = sum(1 for item in consumos if item.estado == AttendanceConsumption.Estado.DEUDA)
    saldo_clases = pago.clases_asignadas - consumos_consumidos
    context.update(
        {
            "pago": pago,
            "consumos": consumos,
            "consumos_consumidos": consumos_consumidos,
            "consumos_pendientes": consumos_pendientes,
            "consumos_deuda": consumos_deuda,
            "saldo_clases": saldo_clases,
            "back_url": request.META.get("HTTP_REFERER") or _url_with_query(request, "finanzas:pagos_list"),
        }
    )
    return render(request, "finanzas/pago_detail.html", context)


@admin_finanzas_required
def pago_delete(request, pk):
    pago = get_object_or_404(Payment, pk=pk)
    if request.method == "POST":
        pago.delete()
        messages.success(request, "Pago eliminado.")
        return _redirect_with_query(request, "finanzas:pagos_list")
    return render(
        request,
        "finanzas/confirm_delete.html",
        {"obj": pago, "title": "Eliminar pago", "back_url": _url_with_query(request, "finanzas:pagos_list")},
    )


@admin_finanzas_required
def documentos_tributarios_list(request):
    context = _base_context(request)
    organizacion = organizacion_desde_request(request)
    documentos_qs = documentos_tributarios_queryset(request, organizacion=organizacion)
    resumen_documentos = resumen_documentos_tributarios(documentos_qs)
    documentos = list(documentos_qs)
    monto_total_ingresos_documentales = Decimal("0")
    monto_total_egresos_documentales = Decimal("0")
    for item in documentos:
        item.rol_financiero = _rol_financiero_documento(item)
        if item.rol_financiero == "ingreso":
            monto_total_ingresos_documentales += item.monto_total or Decimal("0")
        elif item.rol_financiero == "egreso":
            monto_total_egresos_documentales += item.monto_total or Decimal("0")

    form = DocumentoTributarioForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        try:
            form.save()
        except IntegrityError:
            _agregar_error_conflicto_documento(form)
        else:
            messages.success(request, "Documento tributario registrado.")
            return _redirect_with_query(request, "finanzas:documentos_tributarios_list")

    context.update(
        {
            "documentos": documentos,
            "form": form,
            "total_documentos": resumen_documentos["total_documentos"] or 0,
            "monto_total_documentos": resumen_documentos["monto_total_documentos"] or 0,
            "monto_total_ingresos_documentales": monto_total_ingresos_documentales,
            "monto_total_egresos_documentales": monto_total_egresos_documentales,
            "monto_total_iva": resumen_documentos["monto_total_iva"] or 0,
            "monto_total_retencion": resumen_documentos["monto_total_retencion"] or 0,
            "total_pagos_asociados": resumen_documentos["total_pagos_asociados"] or 0,
            "total_transacciones_asociadas": resumen_documentos["total_transacciones_asociadas"] or 0,
            "ayuda_seccion": _ayuda_finanzas("documentos"),
        }
    )
    return render(request, "finanzas/documentos_tributarios_list.html", context)


@admin_finanzas_required
def documento_tributario_importar(request):
    context = _base_context(request)
    if request.method == "POST" and request.POST.get("accion") == "confirmar":
        confirm_form = DocumentoTributarioImportConfirmForm(request.POST)
        token = request.POST.get("token_importacion")
        temporal = cargar_importacion_temporal(request, token) if token else None
        if not temporal:
            messages.error(request, "La importacion temporal ya no existe. Vuelve a subir el archivo.")
            return redirect(_url_with_query(request, "finanzas:documento_tributario_importar"))
        payload = temporal.get("payload", {})
        documento_form = _documento_revision_form(data=request.POST)
        pago_form = None
        guardar_pago = bool(request.POST.get("guardar_pago_sugerido")) and bool(payload.get("pago_initial"))
        if guardar_pago:
            pago_form = PaymentForm(data=request.POST, prefix="pago")
        formularios_validos = confirm_form.is_valid() and documento_form.is_valid() and (
            not guardar_pago or (pago_form is not None and pago_form.is_valid())
        )
        if formularios_validos:
            documento = documento_form.save(commit=False)
            metadata_extra = _metadata_extra_como_dict(documento.metadata_extra)
            metadata_extra["importacion_normalizada"] = payload.get("normalized", {})
            metadata_extra["warnings_importacion"] = payload.get("warnings", [])
            metadata_extra["duplicates_detected"] = payload.get("duplicates", [])
            documento.metadata_extra = metadata_extra

            xml_info = temporal.get("files", {}).get("xml")
            if xml_info:
                with open(xml_info["path"], "rb") as xml_handler:
                    documento.archivo_xml.save(xml_info["name"], File(xml_handler), save=False)
            pdf_info = temporal.get("files", {}).get("pdf")
            if pdf_info:
                with open(pdf_info["path"], "rb") as pdf_handler:
                    documento.archivo_pdf.save(pdf_info["name"], File(pdf_handler), save=False)
            try:
                documento.save()
            except IntegrityError:
                _agregar_error_conflicto_documento(documento_form)
                context.update(
                    _review_context_from_payload(
                        request,
                        payload,
                        token_importacion=token,
                        documento_data=request.POST,
                        pago_data=request.POST,
                    )
                )
                context["confirm_form"] = confirm_form
                return render(request, "finanzas/documento_tributario_importar.html", context)

            if guardar_pago and pago_form is not None:
                pago = pago_form.save(commit=False)
                pago.documento_tributario = documento
                pago.save()

            eliminar_importacion_temporal(request, token)
            messages.success(request, "Documento tributario importado y revisado correctamente.")
            return redirect(_url_with_query(request, "finanzas:documento_tributario_detail", pk=documento.pk))

        context.update(
            _review_context_from_payload(
                request,
                payload,
                token_importacion=token,
                documento_data=request.POST,
                pago_data=request.POST,
            )
        )
        context["confirm_form"] = confirm_form
        return render(request, "finanzas/documento_tributario_importar.html", context)

    upload_form = DocumentoTributarioImportUploadForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and request.POST.get("accion") == "parsear" and upload_form.is_valid():
        archivo_subido = upload_form.cleaned_data.get("archivo")
        xml_file, pdf_file = _clasificar_archivo_tributario(archivo_subido)
        if not xml_file and not pdf_file:
            upload_form.add_error("archivo", "No se pudo reconocer el archivo como XML o PDF.")
        else:
            xml_bytes = xml_file.read() if xml_file else None
            pdf_bytes = pdf_file.read() if pdf_file else None
            organizacion = organizacion_desde_request(request)
            normalized = parse_tax_document(
                xml_bytes=xml_bytes,
                xml_name=xml_file.name if xml_file else None,
                pdf_bytes=pdf_bytes,
                pdf_name=pdf_file.name if pdf_file else None,
                organizacion_id=organizacion.pk if organizacion else None,
            )
            payload = build_review_payload(normalized, organizacion_id=organizacion.pk if organizacion else None)
            if xml_file:
                xml_file.seek(0)
            if pdf_file:
                pdf_file.seek(0)
            token = guardar_importacion_temporal(request, xml_file=xml_file, pdf_file=pdf_file, payload=payload)
            context.update(_review_context_from_payload(request, payload, token_importacion=token))
            context["confirm_form"] = DocumentoTributarioImportConfirmForm(
                initial={"token_importacion": token, "guardar_pago_sugerido": bool(payload.get("pago_initial"))}
            )
            return render(request, "finanzas/documento_tributario_importar.html", context)

    context.update(
        {
            "upload_form": upload_form if request.method == "POST" else DocumentoTributarioImportUploadForm(),
            "ayuda_seccion": {
                "titulo": "Carga asistida",
                "texto": (
                    "Sube un XML o un PDF en un solo campo. El sistema detecta el tipo de archivo, "
                    "lo parsea y luego muestra formularios precargados para revision humana."
                ),
            },
        }
    )
    return render(request, "finanzas/documento_tributario_importar.html", context)


@admin_finanzas_required
def documento_tributario_parse_preview(request):
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "Metodo no permitido."}, status=405)

    form = DocumentoTributarioImportUploadForm(request.POST, request.FILES)
    if not form.is_valid():
        return JsonResponse({"ok": False, "errors": form.errors}, status=400)

    archivo_subido = form.cleaned_data.get("archivo")
    xml_file, pdf_file = _clasificar_archivo_tributario(archivo_subido)
    if not xml_file and not pdf_file:
        return JsonResponse(
            {"ok": False, "errors": {"archivo": ["No se pudo reconocer el archivo como XML o PDF."]}},
            status=400,
        )
    xml_bytes = xml_file.read() if xml_file else None
    pdf_bytes = pdf_file.read() if pdf_file else None
    organizacion = organizacion_desde_request(request)
    normalized = parse_tax_document(
        xml_bytes=xml_bytes,
        xml_name=xml_file.name if xml_file else None,
        pdf_bytes=pdf_bytes,
        pdf_name=pdf_file.name if pdf_file else None,
        organizacion_id=organizacion.pk if organizacion else None,
    )
    payload = build_review_payload(normalized, organizacion_id=organizacion.pk if organizacion else None)
    if xml_file:
        xml_file.seek(0)
    if pdf_file:
        pdf_file.seek(0)
    token = guardar_importacion_temporal(request, xml_file=xml_file, pdf_file=pdf_file, payload=payload)
    actualizar_payload_importacion(request, token, payload)
    response_payload = json.loads(json.dumps({"ok": True, "token": token, **payload}, default=str))
    return JsonResponse(response_payload)


@admin_finanzas_required
@xframe_options_sameorigin
def documento_tributario_importacion_archivo(request, token, tipo_archivo):
    if tipo_archivo not in {"pdf", "xml"}:
        raise Http404("Tipo de archivo no soportado.")
    archivo_info = cargar_archivo_importacion_temporal(request, token, tipo_archivo)
    if not archivo_info:
        raise Http404("La importacion temporal ya no existe o no contiene ese archivo.")

    path = archivo_info["path"]
    content_type, _ = mimetypes.guess_type(path.name)
    response = FileResponse(
        path.open("rb"),
        as_attachment=False,
        filename=archivo_info["name"],
        content_type=content_type or "application/octet-stream",
    )
    response["Content-Disposition"] = f'inline; filename="{archivo_info["name"]}"'
    return response


@admin_finanzas_required
def documento_tributario_detail(request, pk):
    context = _base_context(request)
    documento = get_object_or_404(
        DocumentoTributario.objects.select_related(
            "organizacion",
            "documento_relacionado",
            "persona_relacionada",
            "organizacion_relacionada",
        ).prefetch_related(
            "pagos_asociados",
            "transacciones_asociadas",
            "documentos_hijos",
        ),
        pk=pk,
    )
    archivo_es_pdf = documento.tiene_archivo_pdf
    context.update(
        {
            "documento": documento,
            "archivo_es_pdf": archivo_es_pdf,
            "ayuda_seccion": _ayuda_finanzas("documentos"),
            "back_url": request.META.get("HTTP_REFERER")
            or _url_with_query(request, "finanzas:documentos_tributarios_list"),
        }
    )
    return render(request, "finanzas/documento_tributario_detail.html", context)


@admin_finanzas_required
@xframe_options_sameorigin
def documento_tributario_archivo(request, pk, tipo_archivo):
    documento = get_object_or_404(DocumentoTributario, pk=pk)
    archivo = documento.archivo_pdf if tipo_archivo == "pdf" else documento.archivo_xml
    if not archivo:
        raise Http404("El documento no tiene ese archivo adjunto.")

    content_type, _ = mimetypes.guess_type(archivo.name)
    response = FileResponse(
        archivo.open("rb"),
        as_attachment=False,
        filename=archivo.name.rsplit("/", 1)[-1],
        content_type=content_type or "application/octet-stream",
    )
    response["Content-Disposition"] = f'inline; filename="{archivo.name.rsplit("/", 1)[-1]}"'
    return response


@admin_finanzas_required
def documento_tributario_edit(request, pk):
    documento = get_object_or_404(DocumentoTributario, pk=pk)
    form = DocumentoTributarioForm(request.POST or None, request.FILES or None, instance=documento)
    if request.method == "POST" and form.is_valid():
        try:
            form.save()
        except IntegrityError:
            _agregar_error_conflicto_documento(form)
        else:
            messages.success(request, "Documento tributario actualizado.")
            return _redirect_with_query(request, "finanzas:documentos_tributarios_list")
    return render(
        request,
        "finanzas/form_page.html",
        {
            "form": form,
            "title": "Editar documento tributario",
            "back_url": _url_with_query(request, "finanzas:documentos_tributarios_list"),
        },
    )


@admin_finanzas_required
def documento_tributario_delete(request, pk):
    documento = get_object_or_404(DocumentoTributario, pk=pk)
    if request.method == "POST":
        documento.delete()
        messages.success(request, "Documento tributario eliminado.")
        return _redirect_with_query(request, "finanzas:documentos_tributarios_list")
    return render(
        request,
        "finanzas/confirm_delete.html",
        {
            "obj": documento,
            "title": "Eliminar documento tributario",
            "back_url": _url_with_query(request, "finanzas:documentos_tributarios_list"),
        },
    )


@admin_finanzas_required
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


@admin_finanzas_required
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


@admin_finanzas_required
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


@admin_finanzas_required
def transacciones_list(request):
    context = _base_context(request)
    organizacion = organizacion_desde_request(request)
    trans_qs = transacciones_queryset(request, organizacion=organizacion)
    resumen_transacciones_data = resumen_transacciones(trans_qs)
    total_ingresos = resumen_transacciones_data["total_ingresos"] or 0
    total_egresos = resumen_transacciones_data["total_egresos"] or 0

    form = TransactionForm(
        request.POST or None,
        request.FILES or None,
        initial={"organizacion": organizacion.pk} if organizacion else None,
    )
    if request.method == "POST" and form.is_valid():
        form.save()
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
            "ayuda_seccion": _ayuda_finanzas("transacciones"),
        }
    )
    return render(request, "finanzas/transacciones_list.html", context)


@admin_finanzas_required
def transaccion_detail(request, pk):
    context = _base_context(request)
    transaccion = get_object_or_404(
        Transaction.objects.select_related("organizacion", "categoria").prefetch_related("documentos_tributarios"),
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


@admin_finanzas_required
@xframe_options_sameorigin
def transaccion_archivo(request, pk):
    transaccion = get_object_or_404(Transaction, pk=pk)
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


@admin_finanzas_required
def transaccion_edit(request, pk):
    transaccion = get_object_or_404(Transaction, pk=pk)
    form = TransactionForm(request.POST or None, request.FILES or None, instance=transaccion)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Transaccion actualizada.")
        return _redirect_with_query(request, "finanzas:transacciones_list")
    return render(
        request,
        "finanzas/form_page.html",
        {"form": form, "title": "Editar transaccion", "back_url": _url_with_query(request, "finanzas:transacciones_list")},
    )


@admin_finanzas_required
def transaccion_delete(request, pk):
    transaccion = get_object_or_404(Transaction, pk=pk)
    if request.method == "POST":
        transaccion.delete()
        messages.success(request, "Transaccion eliminada.")
        return _redirect_with_query(request, "finanzas:transacciones_list")
    return render(
        request,
        "finanzas/confirm_delete.html",
        {"obj": transaccion, "title": "Eliminar transaccion", "back_url": _url_with_query(request, "finanzas:transacciones_list")},
    )


@admin_finanzas_required
def reporte_categorias(request):
    context = _base_context(request)
    organizacion = organizacion_desde_request(request)
    consolidado = list(consolidado_categorias_queryset(request, organizacion=organizacion))
    context.update(
        {
            "consolidado": consolidado,
            "periodo_descripcion_vista": descripcion_periodo(request=request, corta=False),
            "ayuda_seccion": _ayuda_finanzas("reporte_categorias"),
        }
    )
    return render(request, "finanzas/reporte_categorias.html", context)


@admin_finanzas_required
def export_pagos_csv(request):
    organizacion = organizacion_desde_request(request)
    pagos = pagos_export_queryset(request, organizacion=organizacion)

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="pagos_finanzas.csv"'
    writer = csv.writer(response)
    writer.writerow(["Fecha", "Organizacion", "Persona", "Metodo", "Neto", "IVA", "Total", "Clases"])
    for pago in pagos:
        writer.writerow(
            [
                pago.fecha_pago,
                pago.organizacion.nombre,
                pago.persona.nombre_completo,
                pago.get_metodo_pago_display(),
                pago.monto_neto,
                pago.monto_iva,
                pago.monto_total,
                pago.clases_asignadas,
            ]
        )
    return response


@admin_finanzas_required
def export_transacciones_csv(request):
    organizacion = organizacion_desde_request(request)
    transacciones = transacciones_export_queryset(request, organizacion=organizacion)

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="transacciones_finanzas.csv"'
    writer = csv.writer(response)
    writer.writerow(["Fecha", "Organizacion", "Tipo", "Categoria", "Monto", "Descripcion"])
    for item in transacciones:
        writer.writerow(
            [
                item.fecha,
                item.organizacion.nombre,
                item.get_tipo_display(),
                item.categoria.nombre,
                item.monto,
                item.descripcion,
            ]
        )
    return response

# Create your views here.

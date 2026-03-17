import csv
import json
import mimetypes

from django.contrib import messages
from django.core.files import File
from django.db.models import Count, ExpressionWrapper, F, IntegerField, Prefetch, Q, Sum
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.clickjacking import xframe_options_sameorigin

from database.models import (
    AttendanceConsumption,
    Category,
    DocumentoTributario,
    Organizacion,
    Payment,
    PaymentPlan,
    Transaction,
)
from asistencias.views import _nav_context, _organizacion_desde_request, _periodo

from .documentos.dtos import NormalizedTaxDocument
from .documentos.services import build_review_payload, parse_tax_document
from .documentos.temp_storage import (
    actualizar_payload_importacion,
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


def _base_context(request):
    context = _nav_context(request)
    context["organizaciones"] = Organizacion.objects.all().order_by("nombre")
    return context


def _ayuda_finanzas(clave):
    ayudas = {
        "dashboard": {
            "titulo": "Que ves aqui",
            "texto": (
                "Este tablero mezcla pagos de alumnos con transacciones de caja del periodo filtrado. "
                "Sirve para revisar ingresos, egresos y balance general sin reemplazar tu contabilidad tributaria."
            ),
        },
        "planes": {
            "titulo": "Que es un plan",
            "texto": (
                "Un plan define clases y precio para cobrar a estudiantes. No representa un documento tributario ni un movimiento bancario."
            ),
        },
        "pagos": {
            "titulo": "Que registrar aqui",
            "texto": (
                "Un pago representa lo que un estudiante paga por sus clases. Puedes asociarlo manualmente al documento tributario emitido al cliente."
            ),
        },
        "documentos": {
            "titulo": "Que registrar aqui",
            "texto": (
                "Aqui se guardan documentos tributarios extraidos del SII o cargados manualmente: facturas, boletas de venta, boletas de honorarios y otros."
            ),
        },
        "categorias": {
            "titulo": "Que es una categoria",
            "texto": (
                "Las categorias ordenan ingresos y egresos para reportes. No guardan documentos ni comprobantes; solo clasifican transacciones."
            ),
        },
        "transacciones": {
            "titulo": "Que registrar aqui",
            "texto": (
                "Una transaccion representa un movimiento real de caja, banco o tarjeta. El archivo adjunto debe ser el respaldo del movimiento, "
                "como transferencia, cartola o comprobante."
            ),
        },
        "reporte_categorias": {
            "titulo": "Como leer este reporte",
            "texto": (
                "Este consolidado agrupa transacciones por categoria dentro del periodo filtrado. Te sirve para analizar caja, no para reemplazar libros tributarios."
            ),
        },
    }
    return ayudas.get(clave)


def _url_with_query(request, route_name, **kwargs):
    query = request.GET.urlencode()
    url = reverse(route_name, kwargs=kwargs or None)
    if query:
        url = f"{url}?{query}"
    return url


def _redirect_with_query(request, route_name, **kwargs):
    url = _url_with_query(request, route_name, **kwargs)
    return redirect(url)


def _documento_revision_form(*, data=None, initial=None):
    form = DocumentoTributarioForm(data=data, initial=initial)
    for field_name in ("archivo_pdf", "archivo_xml", "metadata_extra"):
        form.fields[field_name].widget.attrs["class"] = "d-none"
        form.fields[field_name].widget = form.fields[field_name].hidden_widget()
    return form


def _review_context_from_payload(request, payload, *, documento_data=None, pago_data=None):
    organizacion = _organizacion_desde_request(request)
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
    return {
        "upload_form": DocumentoTributarioImportUploadForm(),
        "confirm_form": DocumentoTributarioImportConfirmForm(
            initial={"guardar_pago_sugerido": bool(pago_inicial)}
        ),
        "documento_form": documento_form,
        "pago_form": pago_form,
        "review_payload": payload,
        "documento_normalizado": NormalizedTaxDocument.from_dict(payload.get("normalized", {})),
        "ayuda_seccion": {
            "titulo": "Carga asistida",
            "texto": (
                "Sube XML y/o PDF, revisa los formularios precargados y confirma manualmente. "
                "Nada se guarda de forma definitiva hasta el ultimo paso."
            ),
        },
        "organizacion_sugerida_id": organizacion.pk if organizacion else "",
    }


@admin_finanzas_required
def dashboard(request):
    context = _base_context(request)
    inicio_mes, fin_mes = _periodo(request)
    organizacion = _organizacion_desde_request(request)

    pagos_qs = Payment.objects.filter(fecha_pago__gte=inicio_mes, fecha_pago__lte=fin_mes)
    trans_qs = Transaction.objects.filter(fecha__gte=inicio_mes, fecha__lte=fin_mes)
    if organizacion:
        pagos_qs = pagos_qs.filter(organizacion=organizacion)
        trans_qs = trans_qs.filter(organizacion=organizacion)

    ingresos_pagos = pagos_qs.aggregate(total=Sum("monto_total")).get("total") or 0
    ingresos_trans = (
        trans_qs.filter(tipo=Transaction.Tipo.INGRESO).aggregate(total=Sum("monto")).get("total") or 0
    )
    egresos = (
        trans_qs.filter(tipo=Transaction.Tipo.EGRESO).aggregate(total=Sum("monto")).get("total") or 0
    )
    iva_debito = pagos_qs.aggregate(total=Sum("monto_iva")).get("total") or 0
    ingresos_exentos = pagos_qs.filter(monto_iva=0).aggregate(total=Sum("monto_total")).get("total") or 0
    categorias_totales = (
        trans_qs.values("categoria__nombre", "categoria__tipo").annotate(total=Sum("monto")).order_by("-total")
    )

    context.update(
        {
            "ingresos_totales": ingresos_pagos + ingresos_trans,
            "egresos_totales": egresos,
            "balance": (ingresos_pagos + ingresos_trans) - egresos,
            "iva_debito": iva_debito,
            "ingresos_exentos": ingresos_exentos,
            "pagos_recientes": pagos_qs.select_related("persona", "organizacion")[:10],
            "transacciones_recientes": trans_qs.select_related("categoria", "organizacion")[:10],
            "categorias_totales": categorias_totales,
            "inicio_mes": inicio_mes,
            "fin_mes": fin_mes,
            "organizacion_filtro": organizacion,
            "ayuda_seccion": _ayuda_finanzas("dashboard"),
        }
    )
    return render(request, "finanzas/dashboard.html", context)


@admin_finanzas_required
def planes_list(request):
    context = _base_context(request)
    organizacion = _organizacion_desde_request(request)
    planes_qs = PaymentPlan.objects.select_related("organizacion").order_by("organizacion__nombre", "nombre")
    if organizacion:
        planes_qs = planes_qs.filter(organizacion=organizacion)

    form = PaymentPlanForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Plan de pago creado.")
        return _redirect_with_query(request, "finanzas:planes_list")

    context.update({"planes": planes_qs, "form": form, "ayuda_seccion": _ayuda_finanzas("planes")})
    return render(request, "finanzas/planes_list.html", context)


@admin_finanzas_required
def plan_edit(request, pk):
    plan = get_object_or_404(PaymentPlan, pk=pk)
    form = PaymentPlanForm(request.POST or None, instance=plan)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Plan actualizado.")
        return _redirect_with_query(request, "finanzas:planes_list")
    return render(
        request,
        "finanzas/form_page.html",
        {"form": form, "title": "Editar plan", "back_url": _url_with_query(request, "finanzas:planes_list")},
    )


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
def pagos_list(request):
    context = _base_context(request)
    inicio_mes, fin_mes = _periodo(request)
    organizacion = _organizacion_desde_request(request)

    pagos_qs = (
        Payment.objects.select_related("persona", "organizacion", "plan", "documento_tributario")
        .filter(fecha_pago__gte=inicio_mes, fecha_pago__lte=fin_mes)
        .annotate(
            clases_consumidas_calculadas=Count(
                "consumos",
                filter=Q(consumos__estado=AttendanceConsumption.Estado.CONSUMIDO),
                distinct=True,
            )
        )
        .annotate(
            saldo_clases_calculado=ExpressionWrapper(
                F("clases_asignadas") - F("clases_consumidas_calculadas"),
                output_field=IntegerField(),
            )
        )
        .order_by("-fecha_pago", "-id")
    )
    if organizacion:
        pagos_qs = pagos_qs.filter(organizacion=organizacion)

    q = request.GET.get("q")
    metodo = request.GET.get("metodo")
    if q:
        pagos_qs = pagos_qs.filter(Q(persona__nombres__icontains=q) | Q(persona__apellidos__icontains=q))
    if metodo:
        pagos_qs = pagos_qs.filter(metodo_pago=metodo)

    resumen_pagos = pagos_qs.aggregate(
        total_pagos_monto=Sum("monto_total"),
        total_clases_pagadas=Sum("clases_asignadas"),
        total_saldo_clases=Sum("saldo_clases_calculado"),
    )

    form = PaymentForm(
        request.POST or None,
        initial={"organizacion": organizacion.pk} if organizacion else None,
    )
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Pago registrado.")
        return _redirect_with_query(request, "finanzas:pagos_list")

    context.update(
        {
            "pagos": pagos_qs,
            "form": form,
            "metodos_pago": Payment.Metodo.choices,
            "q": q or "",
            "metodo": metodo or "",
            "total_pagos_monto": resumen_pagos["total_pagos_monto"] or 0,
            "total_clases_pagadas": resumen_pagos["total_clases_pagadas"] or 0,
            "total_saldo_clases": resumen_pagos["total_saldo_clases"] or 0,
            "ayuda_seccion": _ayuda_finanzas("pagos"),
        }
    )
    return render(request, "finanzas/pagos_list.html", context)


@admin_finanzas_required
def pago_edit(request, pk):
    pago = get_object_or_404(Payment, pk=pk)
    form = PaymentForm(request.POST or None, instance=pago)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Pago actualizado.")
        return _redirect_with_query(request, "finanzas:pagos_list")
    back_url = request.META.get("HTTP_REFERER") or _url_with_query(request, "finanzas:pagos_list")
    return render(
        request,
        "finanzas/form_page.html",
        {"form": form, "title": "Editar pago", "back_url": back_url},
    )


@admin_finanzas_required
def pago_detail(request, pk):
    context = _base_context(request)
    pago = get_object_or_404(
        Payment.objects.select_related("persona", "organizacion", "plan", "documento_tributario").prefetch_related(
            Prefetch(
                "consumos",
                queryset=AttendanceConsumption.objects.select_related(
                    "asistencia__sesion__disciplina",
                    "asistencia__sesion__disciplina__organizacion",
                ).order_by("-clase_fecha", "-id"),
            )
        ),
        pk=pk,
    )
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
    inicio_mes, fin_mes = _periodo(request)
    organizacion = _organizacion_desde_request(request)
    documentos_qs = DocumentoTributario.objects.select_related("organizacion", "documento_relacionado").order_by(
        "-fecha_emision", "-id"
    )
    documentos_qs = documentos_qs.filter(fecha_emision__gte=inicio_mes, fecha_emision__lte=fin_mes)
    if organizacion:
        documentos_qs = documentos_qs.filter(organizacion=organizacion)

    form = DocumentoTributarioForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Documento tributario registrado.")
        return _redirect_with_query(request, "finanzas:documentos_tributarios_list")

    context.update(
        {
            "documentos": documentos_qs,
            "form": form,
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
            metadata_extra = documento.metadata_extra or {}
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
            documento.save()

            if guardar_pago and pago_form is not None:
                pago = pago_form.save(commit=False)
                pago.documento_tributario = documento
                pago.save()

            eliminar_importacion_temporal(request, token)
            messages.success(request, "Documento tributario importado y revisado correctamente.")
            return redirect(_url_with_query(request, "finanzas:documento_tributario_detail", pk=documento.pk))

        context.update(_review_context_from_payload(request, payload, documento_data=request.POST, pago_data=request.POST))
        context["confirm_form"] = confirm_form
        return render(request, "finanzas/documento_tributario_importar.html", context)

    upload_form = DocumentoTributarioImportUploadForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and request.POST.get("accion") == "parsear" and upload_form.is_valid():
        xml_file = upload_form.cleaned_data.get("archivo_xml")
        pdf_file = upload_form.cleaned_data.get("archivo_pdf")
        xml_bytes = xml_file.read() if xml_file else None
        pdf_bytes = pdf_file.read() if pdf_file else None
        organizacion = _organizacion_desde_request(request)
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
        context.update(_review_context_from_payload(request, payload))
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
                    "El archivo se parsea primero y luego se muestran formularios precargados para revision humana. "
                    "Si subes XML y PDF, prevalece el XML."
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

    xml_file = form.cleaned_data.get("archivo_xml")
    pdf_file = form.cleaned_data.get("archivo_pdf")
    xml_bytes = xml_file.read() if xml_file else None
    pdf_bytes = pdf_file.read() if pdf_file else None
    organizacion = _organizacion_desde_request(request)
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
def documento_tributario_detail(request, pk):
    context = _base_context(request)
    documento = get_object_or_404(
        DocumentoTributario.objects.select_related("organizacion", "documento_relacionado").prefetch_related(
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
        form.save()
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
    categorias_qs = Category.objects.order_by("tipo", "nombre")
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
    inicio_mes, fin_mes = _periodo(request)
    organizacion = _organizacion_desde_request(request)

    trans_qs = (
        Transaction.objects.select_related("organizacion", "categoria").prefetch_related("documentos_tributarios")
        .filter(fecha__gte=inicio_mes, fecha__lte=fin_mes)
        .order_by("-fecha", "-id")
    )
    if organizacion:
        trans_qs = trans_qs.filter(organizacion=organizacion)

    form = TransactionForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Transaccion registrada.")
        return _redirect_with_query(request, "finanzas:transacciones_list")

    context.update({"transacciones": trans_qs, "form": form, "ayuda_seccion": _ayuda_finanzas("transacciones")})
    return render(request, "finanzas/transacciones_list.html", context)


@admin_finanzas_required
def transaccion_detail(request, pk):
    context = _base_context(request)
    transaccion = get_object_or_404(
        Transaction.objects.select_related("organizacion", "categoria").prefetch_related("documentos_tributarios"),
        pk=pk,
    )
    archivo_es_pdf = bool(transaccion.archivo and transaccion.archivo.name.lower().endswith(".pdf"))
    context.update(
        {
            "transaccion": transaccion,
            "archivo_es_pdf": archivo_es_pdf,
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
    inicio_mes, fin_mes = _periodo(request)
    organizacion = _organizacion_desde_request(request)
    trans_qs = Transaction.objects.filter(fecha__gte=inicio_mes, fecha__lte=fin_mes)
    if organizacion:
        trans_qs = trans_qs.filter(organizacion=organizacion)
    consolidado = (
        trans_qs.values("categoria__nombre", "categoria__tipo")
        .annotate(total=Sum("monto"))
        .order_by("categoria__tipo", "-total")
    )
    context.update(
        {
            "consolidado": consolidado,
            "inicio_mes": inicio_mes,
            "fin_mes": fin_mes,
            "ayuda_seccion": _ayuda_finanzas("reporte_categorias"),
        }
    )
    return render(request, "finanzas/reporte_categorias.html", context)


@admin_finanzas_required
def export_pagos_csv(request):
    inicio_mes, fin_mes = _periodo(request)
    organizacion = _organizacion_desde_request(request)
    pagos = Payment.objects.select_related("persona", "organizacion").filter(
        fecha_pago__gte=inicio_mes,
        fecha_pago__lte=fin_mes,
    )
    if organizacion:
        pagos = pagos.filter(organizacion=organizacion)

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
    inicio_mes, fin_mes = _periodo(request)
    organizacion = _organizacion_desde_request(request)
    transacciones = Transaction.objects.select_related("categoria", "organizacion").filter(
        fecha__gte=inicio_mes,
        fecha__lte=fin_mes,
    )
    if organizacion:
        transacciones = transacciones.filter(organizacion=organizacion)

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

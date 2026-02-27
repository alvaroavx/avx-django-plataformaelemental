import csv

from django.contrib import messages
from django.db.models import Q, Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from database.models import Category, Invoice, Organizacion, Payment, PaymentPlan, Transaction
from webapp.views import _nav_context, _organizacion_desde_request, _periodo

from .decorators import admin_finanzas_required
from .forms import CategoryForm, InvoiceForm, PaymentForm, PaymentPlanForm, TransactionForm


def _base_context(request):
    context = _nav_context(request)
    context["organizaciones"] = Organizacion.objects.all().order_by("nombre")
    return context


def _url_with_query(request, route_name):
    query = request.GET.urlencode()
    url = reverse(route_name)
    if query:
        url = f"{url}?{query}"
    return url


def _redirect_with_query(request, route_name):
    url = _url_with_query(request, route_name)
    return redirect(url)


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

    context.update({"planes": planes_qs, "form": form})
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
        {"form": form, "title": "Editar plan", "back_url": reverse("finanzas:planes_list")},
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
        {"obj": plan, "title": "Eliminar plan", "back_url": reverse("finanzas:planes_list")},
    )


@admin_finanzas_required
def pagos_list(request):
    context = _base_context(request)
    inicio_mes, fin_mes = _periodo(request)
    organizacion = _organizacion_desde_request(request)

    pagos_qs = (
        Payment.objects.select_related("persona", "organizacion", "plan", "boleta")
        .filter(fecha_pago__gte=inicio_mes, fecha_pago__lte=fin_mes)
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
    return render(
        request,
        "finanzas/form_page.html",
        {"form": form, "title": "Editar pago", "back_url": _url_with_query(request, "finanzas:pagos_list")},
    )


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
        {"obj": pago, "title": "Eliminar pago", "back_url": reverse("finanzas:pagos_list")},
    )


@admin_finanzas_required
def boletas_list(request):
    context = _base_context(request)
    organizacion = _organizacion_desde_request(request)
    boletas_qs = Invoice.objects.select_related("organizacion").order_by("-fecha_emision", "-id")
    if organizacion:
        boletas_qs = boletas_qs.filter(organizacion=organizacion)

    form = InvoiceForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Boleta/factura registrada.")
        return _redirect_with_query(request, "finanzas:boletas_list")

    context.update({"boletas": boletas_qs, "form": form})
    return render(request, "finanzas/boletas_list.html", context)


@admin_finanzas_required
def boleta_edit(request, pk):
    boleta = get_object_or_404(Invoice, pk=pk)
    form = InvoiceForm(request.POST or None, request.FILES or None, instance=boleta)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Boleta/factura actualizada.")
        return _redirect_with_query(request, "finanzas:boletas_list")
    return render(
        request,
        "finanzas/form_page.html",
        {"form": form, "title": "Editar boleta/factura", "back_url": reverse("finanzas:boletas_list")},
    )


@admin_finanzas_required
def boleta_delete(request, pk):
    boleta = get_object_or_404(Invoice, pk=pk)
    if request.method == "POST":
        boleta.delete()
        messages.success(request, "Boleta/factura eliminada.")
        return _redirect_with_query(request, "finanzas:boletas_list")
    return render(
        request,
        "finanzas/confirm_delete.html",
        {"obj": boleta, "title": "Eliminar boleta/factura", "back_url": reverse("finanzas:boletas_list")},
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
    context.update({"categorias": categorias_qs, "form": form})
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
        {"form": form, "title": "Editar categoria", "back_url": reverse("finanzas:categorias_list")},
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
        {"obj": categoria, "title": "Eliminar categoria", "back_url": reverse("finanzas:categorias_list")},
    )


@admin_finanzas_required
def transacciones_list(request):
    context = _base_context(request)
    inicio_mes, fin_mes = _periodo(request)
    organizacion = _organizacion_desde_request(request)

    trans_qs = (
        Transaction.objects.select_related("organizacion", "categoria")
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

    context.update({"transacciones": trans_qs, "form": form})
    return render(request, "finanzas/transacciones_list.html", context)


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
        {"form": form, "title": "Editar transaccion", "back_url": reverse("finanzas:transacciones_list")},
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
        {"obj": transaccion, "title": "Eliminar transaccion", "back_url": reverse("finanzas:transacciones_list")},
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
    context.update({"consolidado": consolidado, "inicio_mes": inicio_mes, "fin_mes": fin_mes})
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

from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from .forms import ConfiguracionMonitorForm, ConfiguracionSitioForm, SitioCreateForm
from .models import ConfiguracionMonitor, ConfiguracionSitio, Sitio
from .services.discovery import ejecutar_discovery_inicial


FILTROS_GLOBALES = ("periodo_mes", "periodo_anio", "organizacion")


def _url_con_filtros(request, viewname, *args, **kwargs):
    url = reverse(viewname, args=args, kwargs=kwargs)
    filtros = {
        key: request.GET[key]
        for key in FILTROS_GLOBALES
        if request.GET.get(key)
    }
    if not filtros:
        return url
    from urllib.parse import urlencode

    return f"{url}?{urlencode(filtros)}"


@login_required
def dashboard(request):
    sitios = (
        Sitio.objects.select_related("proyecto")
        .annotate(total_discoveries=Count("discoveries"))
        .order_by("-actualizado_en")
    )
    resumen = {
        "total_sitios": sitios.count(),
        "sitios_activos": sitios.filter(ultimo_estado=Sitio.ESTADO_ACTIVO).count(),
        "sitios_error": sitios.filter(ultimo_estado=Sitio.ESTADO_ERROR).count(),
        "sitios_pendientes": sitios.filter(ultimo_estado=Sitio.ESTADO_PENDIENTE).count(),
    }
    return render(
        request,
        "monitor/dashboard.html",
        {
            "resumen": resumen,
            "sitios": sitios[:12],
        },
    )


@login_required
def sitio_create(request):
    if request.method == "POST":
        form = SitioCreateForm(request.POST)
        if form.is_valid():
            try:
                sitio = form.crear_sitio()
            except ValidationError as exc:
                form.add_error(None, exc)
            else:
                ejecutar_discovery_inicial(sitio)
                messages.success(request, "Sitio agregado y discovery inicial ejecutado.")
                return redirect(_url_con_filtros(request, "monitor:sitio_detail", pk=sitio.pk))
    else:
        form = SitioCreateForm()

    return render(request, "monitor/sitio_form.html", {"form": form})


@login_required
def sitio_detail(request, pk):
    sitio = get_object_or_404(
        Sitio.objects.select_related("proyecto", "proyecto__organizacion"),
        pk=pk,
    )
    configuracion_global = ConfiguracionMonitor.actual()
    configuracion_sitio = getattr(sitio, "configuracion", None)
    discoveries = sitio.discoveries.all()[:10]
    timeout_segundos = (
        configuracion_sitio.timeout_resuelto(configuracion_global)
        if configuracion_sitio
        else configuracion_global.timeout_segundos
    )
    frecuencia_minutos = (
        configuracion_sitio.frecuencia_resuelta(configuracion_global)
        if configuracion_sitio
        else configuracion_global.frecuencia_minutos
    )
    seguir_redirecciones = (
        configuracion_sitio.seguir_redirecciones_resuelto(configuracion_global)
        if configuracion_sitio
        else configuracion_global.seguir_redirecciones
    )
    configuracion_efectiva = {
        "timeout_segundos": timeout_segundos,
        "frecuencia_minutos": frecuencia_minutos,
        "seguir_redirecciones": seguir_redirecciones,
    }
    return render(
        request,
        "monitor/sitio_detail.html",
        {
            "sitio": sitio,
            "configuracion_global": configuracion_global,
            "configuracion_sitio": configuracion_sitio,
            "configuracion_efectiva": configuracion_efectiva,
            "discoveries": discoveries,
        },
    )


@login_required
def configuracion(request):
    configuracion_global = ConfiguracionMonitor.actual()
    if request.method == "POST":
        form = ConfiguracionMonitorForm(request.POST, instance=configuracion_global)
        if form.is_valid():
            form.save()
            messages.success(request, "Configuracion global actualizada.")
            return redirect(_url_con_filtros(request, "monitor:configuracion"))
    else:
        form = ConfiguracionMonitorForm(instance=configuracion_global)

    return render(request, "monitor/configuracion_form.html", {"form": form})


@login_required
def sitio_configuracion(request, pk):
    sitio = get_object_or_404(Sitio, pk=pk)
    configuracion_sitio, _ = ConfiguracionSitio.objects.get_or_create(sitio=sitio)
    if request.method == "POST":
        form = ConfiguracionSitioForm(request.POST, instance=configuracion_sitio)
        if form.is_valid():
            form.save()
            messages.success(request, "Configuracion del sitio actualizada.")
            return redirect(_url_con_filtros(request, "monitor:sitio_detail", pk=sitio.pk))
    else:
        form = ConfiguracionSitioForm(instance=configuracion_sitio)

    return render(
        request,
        "monitor/sitio_configuracion_form.html",
        {
            "form": form,
            "sitio": sitio,
        },
    )

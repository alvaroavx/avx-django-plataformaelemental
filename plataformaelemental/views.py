from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from .context import nav_context, organizacion_desde_request
from .dashboard import construir_dashboard_general, construir_detalle_metrica


@login_required
def elemental_apps(request):
    context = nav_context(request)
    organizacion = organizacion_desde_request(request)
    context.update(construir_dashboard_general(request, organizacion=organizacion))
    return render(request, "plataformaelemental/elemental_apps.html", context)


@login_required
def detalle_metrica(request, metrica):
    context = nav_context(request)
    organizacion = organizacion_desde_request(request)
    context.update(construir_detalle_metrica(request, metrica=metrica, organizacion=organizacion))
    return render(request, "plataformaelemental/detalle_metrica.html", context)

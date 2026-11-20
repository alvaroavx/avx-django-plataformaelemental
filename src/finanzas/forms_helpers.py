import mimetypes

from django.shortcuts import redirect
from django.urls import reverse

from personas.models import Organizacion
from plataformaelemental.context import nav_context


def base_context(request):
    context = nav_context(request)
    context["organizaciones"] = Organizacion.objects.all().order_by("nombre")
    return context


def ayuda_finanzas(clave):
    ayudas = {
        "dashboard": {
            "titulo": "Que ves aqui",
            "texto": (
                "Este tablero mezcla pagos de alumnos con transacciones de caja del periodo filtrado. "
                "Sirve para revisar ingresos, egresos y balance general de la operación."
            ),
        },
        "planes": {
            "titulo": "Que es un plan",
            "texto": (
                "Un plan define clases y precio para cobrar a estudiantes. No representa por sí solo un movimiento de caja."
            ),
        },
        "pagos": {
            "titulo": "Que registrar aqui",
            "texto": (
                "Un pago representa lo que un estudiante paga por sus clases y mantiene su consumo y saldo operacional."
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
                "Este consolidado agrupa transacciones por categoría dentro del período filtrado para analizar caja."
            ),
        },
    }
    return ayudas.get(clave)


def url_with_query(request, route_name, **kwargs):
    query = request.GET.urlencode()
    url = reverse(route_name, kwargs=kwargs or None)
    if query:
        url = f"{url}?{query}"
    return url


def url_with_query_without(request, route_name, *, remove_params=None, **kwargs):
    params = request.GET.copy()
    for param in remove_params or []:
        params.pop(param, None)
    query = params.urlencode()
    url = reverse(route_name, kwargs=kwargs or None)
    if query:
        url = f"{url}?{query}"
    return url


def redirect_with_query(request, route_name, **kwargs):
    url = url_with_query(request, route_name, **kwargs)
    return redirect(url)


def url_pagos_list_con_edicion(request, pago_id):
    params = request.GET.copy()
    params.pop("editar_pago", None)
    params["editar_pago"] = str(pago_id)
    query = params.urlencode()
    url = reverse("finanzas:pagos_list")
    if query:
        url = f"{url}?{query}"
    return url


def url_pagos_list_sin_edicion(request):
    return url_with_query_without(request, "finanzas:pagos_list", remove_params=["editar_pago"])


def url_pago_edit_sin_edicion(request, pago_id):
    return url_with_query_without(
        request,
        "finanzas:pago_edit",
        remove_params=["editar_pago"],
        pk=pago_id,
    )


def tipo_visualizacion_archivo(nombre_archivo):
    if not nombre_archivo:
        return {"es_pdf": False, "es_imagen": False}
    content_type, _ = mimetypes.guess_type(nombre_archivo)
    nombre = nombre_archivo.lower()
    es_pdf = bool(content_type == "application/pdf" or nombre.endswith(".pdf"))
    es_imagen = bool(
        (content_type and content_type.startswith("image/"))
        or nombre.endswith((".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg"))
    )
    return {"es_pdf": es_pdf, "es_imagen": es_imagen}

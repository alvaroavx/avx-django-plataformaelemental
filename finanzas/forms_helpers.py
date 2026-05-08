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


def url_with_query(request, route_name, **kwargs):
    query = request.GET.urlencode()
    url = reverse(route_name, kwargs=kwargs or None)
    if query:
        url = f"{url}?{query}"
    return url


def redirect_with_query(request, route_name, **kwargs):
    url = url_with_query(request, route_name, **kwargs)
    return redirect(url)


def url_pagos_list_con_edicion(request, pago_id):
    params = request.GET.copy()
    params["editar_pago"] = str(pago_id)
    query = params.urlencode()
    url = reverse("finanzas:pagos_list")
    if query:
        url = f"{url}?{query}"
    return url


def agregar_error_conflicto_documento(form):
    form.add_error(
        None,
        "No se pudo guardar el documento por un conflicto de unicidad. Revisa organizacion, tipo, folio y RUT emisor.",
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

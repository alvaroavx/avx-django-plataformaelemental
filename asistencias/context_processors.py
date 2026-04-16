from django.utils import timezone

from personas.models import Organizacion
from .periodo import descripcion_periodo, resolver_periodo


def periodo_context(request):
    hoy = timezone.localdate()
    periodo = resolver_periodo(request)
    anio = str(periodo["anio"]) if periodo["anio"] is not None else "todos"
    mes = str(periodo["mes"]) if periodo["mes"] is not None else "todos"

    organizacion_id = request.GET.get("organizacion") or ""

    return {
        "periodo_anio": anio,
        "periodo_mes": mes,
        "periodo_anios": [("todos", "Todos")] + [(str(y), str(y)) for y in range(hoy.year - 2, hoy.year + 3)],
        "periodo_meses": [
            ("todos", "Todos"),
            ("1", "Enero"),
            ("2", "Febrero"),
            ("3", "Marzo"),
            ("4", "Abril"),
            ("5", "Mayo"),
            ("6", "Junio"),
            ("7", "Julio"),
            ("8", "Agosto"),
            ("9", "Septiembre"),
            ("10", "Octubre"),
            ("11", "Noviembre"),
            ("12", "Diciembre"),
        ],
        "periodo_descripcion": descripcion_periodo(request=request, corta=False),
        "periodo_descripcion_corta": descripcion_periodo(request=request, corta=True),
        "organizaciones_global": Organizacion.objects.all().order_by("nombre"),
        "organizacion_id": str(organizacion_id),
    }

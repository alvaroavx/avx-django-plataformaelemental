from django.utils import timezone

from personas.models import Organizacion


def periodo_context(request):
    hoy = timezone.localdate()
    try:
        anio = int(request.GET.get("periodo_anio", hoy.year))
    except (TypeError, ValueError):
        anio = hoy.year
    try:
        mes = int(request.GET.get("periodo_mes", hoy.month))
    except (TypeError, ValueError):
        mes = hoy.month

    if mes < 1 or mes > 12:
        mes = hoy.month
    if anio < 2000 or anio > 2100:
        anio = hoy.year

    organizacion_id = request.GET.get("organizacion") or ""

    return {
        "periodo_anio": anio,
        "periodo_mes": mes,
        "periodo_anios": list(range(hoy.year - 2, hoy.year + 3)),
        "periodo_meses": [
            (1, "Enero"),
            (2, "Febrero"),
            (3, "Marzo"),
            (4, "Abril"),
            (5, "Mayo"),
            (6, "Junio"),
            (7, "Julio"),
            (8, "Agosto"),
            (9, "Septiembre"),
            (10, "Octubre"),
            (11, "Noviembre"),
            (12, "Diciembre"),
        ],
        "organizaciones_global": Organizacion.objects.all().order_by("nombre"),
        "organizacion_id": str(organizacion_id),
    }

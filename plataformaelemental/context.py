from datetime import date, timedelta

from django.utils import timezone
from django.utils.formats import date_format

from personas.models import Organizacion


MESES_PERIODO = [
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
]


def _fin_de_mes(fecha):
    return (fecha.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)


def _normalizar_mes(raw_mes, hoy):
    if raw_mes is None or str(raw_mes).strip() == "":
        return hoy.month
    valor = (raw_mes or "").strip().lower()
    if valor == "todos":
        return None
    try:
        mes = int(valor)
    except (TypeError, ValueError):
        return hoy.month
    return mes if 1 <= mes <= 12 else hoy.month


def _normalizar_anio(raw_anio, hoy):
    if raw_anio is None or str(raw_anio).strip() == "":
        return hoy.year
    valor = (raw_anio or "").strip().lower()
    if valor == "todos":
        return None
    try:
        anio = int(valor)
    except (TypeError, ValueError):
        return hoy.year
    return anio if 2000 <= anio <= 2100 else hoy.year


def resolver_periodo(request):
    hoy = timezone.localdate()
    mes = _normalizar_mes(request.GET.get("periodo_mes"), hoy)
    anio = _normalizar_anio(request.GET.get("periodo_anio"), hoy)
    referencia = hoy.replace(year=anio or hoy.year, month=mes or hoy.month, day=1)
    return {
        "mes": mes,
        "anio": anio,
        "referencia_inicio": referencia,
        "referencia_fin": _fin_de_mes(referencia),
    }


def filtros_periodo(campo, *, request=None, mes=None, anio=None):
    if request is not None:
        periodo = resolver_periodo(request)
        mes = periodo["mes"]
        anio = periodo["anio"]
    filtros = {}
    if anio is not None:
        filtros[f"{campo}__year"] = anio
    if mes is not None:
        filtros[f"{campo}__month"] = mes
    return filtros


def aplicar_periodo(queryset, campo, *, request=None, mes=None, anio=None):
    filtros = filtros_periodo(campo, request=request, mes=mes, anio=anio)
    if not filtros:
        return queryset
    return queryset.filter(**filtros)


def descripcion_periodo(*, request=None, mes=None, anio=None, corta=False):
    if request is not None:
        periodo = resolver_periodo(request)
        mes = periodo["mes"]
        anio = periodo["anio"]
    if mes is None and anio is None:
        return "Todo el periodo" if corta else "Todos los meses y todos los años"
    if mes is None:
        return f"Año {anio}" if corta else f"Todos los meses de {anio}"
    nombre_mes = date_format(date((anio or 2000), mes, 1), "F")
    if anio is None:
        return nombre_mes if corta else f"{nombre_mes} de todos los años"
    return f"{nombre_mes} {anio}" if corta else f"{nombre_mes} de {anio}"


def nav_context(request):
    persona = getattr(request.user, "persona", None)
    roles = []
    if persona:
        roles = list(persona.roles.filter(activo=True).values_list("rol__codigo", flat=True))
    return {"persona": persona, "roles_usuario": roles}


def organizacion_desde_request(request):
    org_id = request.GET.get("organizacion")
    if not org_id:
        return None
    return Organizacion.objects.filter(pk=org_id).first()


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
        "periodo_meses": MESES_PERIODO,
        "periodo_descripcion": descripcion_periodo(request=request, corta=False),
        "periodo_descripcion_corta": descripcion_periodo(request=request, corta=True),
        "organizaciones_global": Organizacion.objects.all().order_by("nombre"),
        "organizacion_id": str(organizacion_id),
    }

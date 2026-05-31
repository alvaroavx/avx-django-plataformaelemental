from urllib.parse import urlencode

from django.urls import reverse

from personas.permissions import (
    ACCION_ADMINISTRAR_PERSONAS,
    ACCION_ADMINISTRAR_SESIONES,
    ACCION_VER_FINANZAS,
    usuario_tiene_permiso,
)


FILTROS_GLOBALES = ("periodo_mes", "periodo_anio", "organizacion")


def _query_filtros(request):
    params = {}
    for key in FILTROS_GLOBALES:
        value = request.GET.get(key)
        if value not in (None, ""):
            params[key] = value
    query = urlencode(params)
    return f"?{query}" if query else ""


def _url(request, view_name):
    return f"{reverse(view_name)}{_query_filtros(request)}"


def _item(request, *, label, icon, url_name=None, url=None, children=None, active_prefixes=None):
    href = url or (_url(request, url_name) if url_name else "#")
    path = request.path
    active = any(path.startswith(prefix) for prefix in (active_prefixes or []))
    return {
        "label": label,
        "icon": icon,
        "url": href,
        "children": children or [],
        "active": active,
    }


def build_navigation(request):
    user = request.user
    if not user.is_authenticated:
        return []

    organizacion = None
    try:
        from plataformaelemental.context import organizacion_desde_request

        organizacion = organizacion_desde_request(request)
    except Exception:
        organizacion = None

    can_personas = usuario_tiene_permiso(user, ACCION_ADMINISTRAR_PERSONAS, organizacion=organizacion)
    can_asistencias = usuario_tiene_permiso(user, ACCION_ADMINISTRAR_SESIONES, organizacion=organizacion)
    can_finanzas = usuario_tiene_permiso(user, ACCION_VER_FINANZAS, organizacion=organizacion)

    items = [
        _item(
            request,
            label="Elemental Apps",
            icon="bi-grid",
            url_name="elemental_apps",
            active_prefixes=["/"],
        )
    ]
    items[0]["active"] = request.path == "/"

    if can_asistencias:
        items.append(
            _item(
                request,
                label="Asistencias",
                icon="bi-clipboard-check",
                url_name="asistencias:dashboard",
                active_prefixes=["/asistencias/"],
                children=[
                    _item(request, label="Dashboard", icon="bi-grid", url_name="asistencias:dashboard"),
                    _item(request, label="Calendario", icon="bi-calendar3", url_name="asistencias:sesiones_list"),
                    _item(request, label="Asistencias", icon="bi-clipboard-check", url_name="asistencias:asistencias_list"),
                    _item(request, label="Estudiantes", icon="bi-people", url_name="asistencias:estudiantes_list"),
                    _item(request, label="Profesores", icon="bi-person-workspace", url_name="asistencias:profesores_list"),
                    _item(request, label="Disciplinas", icon="bi-tags", url_name="asistencias:disciplinas_list"),
                ],
            )
        )

    if can_finanzas:
        items.append(
            _item(
                request,
                label="Finanzas",
                icon="bi-cash-coin",
                url_name="finanzas:dashboard",
                active_prefixes=["/finanzas/"],
                children=[
                    _item(request, label="Dashboard", icon="bi-grid", url_name="finanzas:dashboard"),
                    _item(request, label="Pagos", icon="bi-cash-stack", url_name="finanzas:pagos_list"),
                    _item(
                        request,
                        label="Documentos",
                        icon="bi-file-earmark-text",
                        url_name="finanzas:documentos_tributarios_list",
                    ),
                    _item(
                        request,
                        label="Transacciones",
                        icon="bi-arrow-left-right",
                        url_name="finanzas:transacciones_list",
                    ),
                    _item(request, label="Planes", icon="bi-card-list", url_name="finanzas:planes_list"),
                    _item(request, label="Categorias", icon="bi-folder2-open", url_name="finanzas:categorias_list"),
                ],
            )
        )

    if can_personas:
        items.append(
            _item(
                request,
                label="Personas",
                icon="bi-people",
                url_name="personas:dashboard",
                active_prefixes=["/personas/"],
                children=[
                    _item(request, label="Dashboard", icon="bi-grid", url_name="personas:dashboard"),
                    _item(request, label="Personas", icon="bi-people", url_name="personas:personas_list"),
                    _item(
                        request,
                        label="Organizaciones",
                        icon="bi-building",
                        url_name="personas:organizaciones_list",
                    ),
                ],
            )
        )

    if user.is_staff or user.is_superuser:
        items.append(
            _item(
                request,
                label="Admin",
                icon="bi-shield-lock",
                url="/admin/",
                active_prefixes=["/admin/"],
            )
        )

    return items


def build_dashboard_cards(request):
    return [item for item in build_navigation(request) if item["label"] not in {"Elemental Apps"}]


def navigation_context(request):
    return {
        "elemental_nav_items": build_navigation(request),
        "elemental_dashboard_cards": build_dashboard_cards(request),
    }

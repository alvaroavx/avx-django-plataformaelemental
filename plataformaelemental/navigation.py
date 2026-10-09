from urllib.parse import urlencode

from django.conf import settings
from django.urls import reverse

from personas.models import SolicitudAcceso
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


def _item(
    request,
    *,
    label,
    icon,
    url_name=None,
    url=None,
    children=None,
    active_prefixes=None,
    badge=None,
    collapsible=False,
):
    href = url or (_url(request, url_name) if url_name else "#")
    path = request.path
    active = any(path.startswith(prefix) for prefix in (active_prefixes or []))
    current = path == href.split("?", 1)[0]
    return {
        "label": label,
        "icon": icon,
        "url": href,
        "children": children or [],
        "active": active,
        "current": current,
        "badge": badge,
        "collapsible": collapsible,
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

    contexto_operable = organizacion is not None or user.is_staff or user.is_superuser
    can_personas = contexto_operable and usuario_tiene_permiso(
        user, ACCION_ADMINISTRAR_PERSONAS, organizacion=organizacion
    )
    can_asistencias = contexto_operable and usuario_tiene_permiso(
        user, ACCION_ADMINISTRAR_SESIONES, organizacion=organizacion
    )
    can_finanzas = contexto_operable and usuario_tiene_permiso(
        user, ACCION_VER_FINANZAS, organizacion=organizacion
    )
    can_gestionar_solicitudes = settings.ACCESS_REQUESTS_ENABLED and user.has_perm(
        "personas.gestionar_solicitudes_acceso"
    )
    pendientes_solicitudes = (
        SolicitudAcceso.objects.filter(estado=SolicitudAcceso.Estado.PENDIENTE).count()
        if can_gestionar_solicitudes
        else 0
    )

    items = [
        _item(
            request,
            label="Panel",
            icon="bi-grid",
            url_name="elemental_apps",
            active_prefixes=["/"],
        )
    ]
    items[0]["active"] = request.path == "/"
    configuracion = []

    if can_asistencias:
        disciplinas_path = reverse("asistencias:disciplinas_list")
        items.extend(
            [
                _item(request, label="Calendario", icon="bi-calendar3", url_name="asistencias:sesiones_list"),
                _item(request, label="Asistencias", icon="bi-clipboard-check", url_name="asistencias:asistencias_list"),
                _item(request, label="Estudiantes", icon="bi-people", url_name="asistencias:estudiantes_list"),
                _item(request, label="Profesores", icon="bi-person-workspace", url_name="asistencias:profesores_list"),
            ]
        )
        configuracion.append(
            _item(
                request,
                label="Disciplinas",
                icon="bi-tags",
                url_name="asistencias:disciplinas_list",
                active_prefixes=[disciplinas_path],
            )
        )
    if can_finanzas:
        planes_path = reverse("finanzas:planes_list")
        categorias_path = reverse("finanzas:categorias_list")
        items.extend(
            [
                _item(request, label="Resumen financiero", icon="bi-cash-coin", url_name="finanzas:dashboard"),
                _item(request, label="Pagos", icon="bi-cash-stack", url_name="finanzas:pagos_list"),
                _item(
                    request,
                    label="Transacciones",
                    icon="bi-arrow-left-right",
                    url_name="finanzas:transacciones_list",
                ),
            ]
        )
        configuracion.extend(
            [
                _item(
                    request,
                    label="Planes",
                    icon="bi-card-list",
                    url_name="finanzas:planes_list",
                    active_prefixes=[planes_path],
                ),
                _item(
                    request,
                    label="Categorías",
                    icon="bi-folder2-open",
                    url_name="finanzas:categorias_list",
                    active_prefixes=[categorias_path],
                ),
            ]
        )

    if can_personas or can_gestionar_solicitudes:
        if can_personas:
            configuracion.append(
                _item(
                    request,
                    label="Organizaciones",
                    icon="bi-building",
                    url_name="personas:organizaciones_list",
                    active_prefixes=[reverse("personas:organizaciones_list")],
                )
            )
        if can_gestionar_solicitudes:
            configuracion.append(
                _item(
                    request,
                    label="Solicitudes de acceso",
                    icon="bi-person-lock",
                    url_name="personas:solicitudes_acceso_list",
                    active_prefixes=[reverse("personas:solicitudes_acceso_list")],
                    badge=pendientes_solicitudes or None,
                )
            )
        if can_personas:
            items.append(
                _item(
                    request,
                    label="Personas",
                    icon="bi-people",
                    url_name="personas:personas_list",
                    active_prefixes=["/personas/"],
                )
            )

    if user.is_staff or user.is_superuser:
        configuracion.append(
            _item(
                request,
                label="Administración avanzada",
                icon="bi-shield-lock",
                url="/admin/",
                active_prefixes=["/admin/"],
            )
        )

    if configuracion:
        item_configuracion = _item(
            request,
            label="Configuración",
            icon="bi-gear",
            url=configuracion[0]["url"],
            children=configuracion,
            collapsible=True,
        )
        item_configuracion["active"] = any(child["active"] or child["current"] for child in configuracion)
        if item_configuracion["active"]:
            for item in items:
                if item["label"] == "Personas":
                    item["active"] = False
        items.append(item_configuracion)

    return items


def build_dashboard_cards(request):
    return [
        item
        for item in build_navigation(request)
        if item["label"] not in {"Panel", "Configuración"}
    ]


def navigation_context(request):
    return {
        "elemental_nav_items": build_navigation(request),
        "elemental_dashboard_cards": build_dashboard_cards(request),
    }

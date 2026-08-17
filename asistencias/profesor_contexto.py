from urllib.parse import urlencode

from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.utils import timezone
from django.utils.formats import date_format

from .models import AsignacionProfesorDisciplina, Disciplina
from .services.profesor import organizaciones_profesor, rol_profesor_activo


ORGANIZACION_TODAS = "todos"
PERIODO_TODOS = "todos"
MESES = (
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
)


def _resolver_periodo_profesor(request):
    hoy = timezone.localdate()
    periodo_raw = (request.GET.get("periodo") or "").strip().lower()
    mes_raw = request.GET.get("periodo_mes")
    anio_raw = request.GET.get("periodo_anio")

    if periodo_raw:
        if periodo_raw != PERIODO_TODOS or mes_raw not in (None, "") or anio_raw not in (None, ""):
            raise Http404
        return {
            "periodo_todos": True,
            "periodo_mes": None,
            "periodo_anio": None,
            "periodo_mes_sugerido": hoy.month,
            "periodo_anio_sugerido": hoy.year,
            "periodo_label": "Todos los períodos",
            "periodo_parametros": {"periodo": PERIODO_TODOS},
        }

    if (mes_raw in (None, "")) != (anio_raw in (None, "")):
        raise Http404
    if mes_raw in (None, ""):
        mes, anio = hoy.month, hoy.year
    else:
        try:
            mes, anio = int(mes_raw), int(anio_raw)
        except (TypeError, ValueError) as exc:
            raise Http404 from exc
        if mes not in range(1, 13) or anio not in range(2000, 2200):
            raise Http404

    referencia = timezone.datetime(anio, mes, 1).date()
    return {
        "periodo_todos": False,
        "periodo_mes": mes,
        "periodo_anio": anio,
        "periodo_mes_sugerido": mes,
        "periodo_anio_sugerido": anio,
        "periodo_label": f"{date_format(referencia, 'F').capitalize()} {anio}",
        "periodo_parametros": {
            "periodo_mes": str(mes),
            "periodo_anio": str(anio),
        },
    }


def contexto_seleccion_profesor(request):
    persona = getattr(request.user, "persona", None)
    if not request.user.is_authenticated or not request.user.is_active or not persona or not persona.activo:
        raise PermissionDenied("El espacio Profesor requiere una identidad activa.")
    organizaciones = list(organizaciones_profesor(request.user))
    periodo = _resolver_periodo_profesor(request)
    return {
        "profesor_mode": True,
        "profesor": persona,
        "organizaciones_profesor": organizaciones,
        "organizacion_activa": None,
        "organizacion_todas": False,
        "organizacion_id": "",
        "organizacion_label": "Sin organización seleccionada",
        "sin_organizaciones": not organizaciones,
        "meses_profesor": MESES,
        **periodo,
        "profesor_query": urlencode(periodo["periodo_parametros"]),
        "contexto_label": periodo["periodo_label"],
        "contexto_mutable": False,
        "puede_operar_profesor": False,
        "mensaje_contexto_accion": "Selecciona una organización para realizar esta acción.",
    }


def resolver_contexto_profesor(request):
    persona = getattr(request.user, "persona", None)
    if not request.user.is_authenticated or not request.user.is_active or not persona or not persona.activo:
        raise PermissionDenied("El espacio Profesor requiere una identidad activa.")

    organizaciones = list(organizaciones_profesor(request.user))
    if not organizaciones:
        raise PermissionDenied("No tienes organizaciones disponibles para el rol Profesor.")
    organizacion_raw = (request.GET.get("organizacion") or "").strip().lower()
    if not organizacion_raw:
        raise Http404

    periodo = _resolver_periodo_profesor(request)
    organizacion_todas = organizacion_raw == ORGANIZACION_TODAS
    organizacion_activa = None
    if organizacion_todas:
        organizacion_ids = [organizacion.pk for organizacion in organizaciones]
        asignaciones = AsignacionProfesorDisciplina.objects.operativas().select_related(
            "disciplina",
            "disciplina__organizacion",
        ).filter(
            profesor=persona,
            disciplina__organizacion_id__in=organizacion_ids,
            disciplina__activa=True,
        )
        organizacion_id = ORGANIZACION_TODAS
        organizacion_label = "Todas mis organizaciones"
    else:
        rol = rol_profesor_activo(request.user, organizacion_id=organizacion_raw)
        if not rol:
            raise Http404
        organizacion_activa = rol.organizacion
        organizacion_ids = [rol.organizacion_id]
        organizacion_id = str(rol.organizacion_id)
        organizacion_label = rol.organizacion.nombre
        asignaciones = AsignacionProfesorDisciplina.objects.operativas().select_related(
            "disciplina",
            "disciplina__organizacion",
        ).filter(
            profesor=persona,
            disciplina__organizacion=rol.organizacion,
            disciplina__activa=True,
        )

    disciplina_ids = list(asignaciones.values_list("disciplina_id", flat=True))
    disciplinas = Disciplina.objects.filter(pk__in=disciplina_ids).select_related(
        "organizacion"
    ).order_by("organizacion__nombre", "nombre", "pk")
    parametros = {"organizacion": organizacion_id, **periodo["periodo_parametros"]}
    contexto_mutable = not organizacion_todas and not periodo["periodo_todos"]
    puede_operar_profesor = contexto_mutable and bool(disciplina_ids)
    return {
        "profesor_mode": True,
        "profesor": persona,
        "organizaciones_profesor": organizaciones,
        "organizacion_activa": organizacion_activa,
        "organizacion_todas": organizacion_todas,
        "organizacion_ids": organizacion_ids,
        "organizacion_id": organizacion_id,
        "organizacion_label": organizacion_label,
        "meses_profesor": MESES,
        "disciplinas_profesor": disciplinas,
        "disciplina_ids": disciplina_ids,
        "profesor_query": urlencode(parametros),
        "contexto_label": f"{organizacion_label} · {periodo['periodo_label']}",
        "contexto_mutable": contexto_mutable,
        "puede_operar_profesor": puede_operar_profesor,
        "mensaje_contexto_accion": (
            "Selecciona una organización y un mes para realizar esta acción."
            if periodo["periodo_todos"]
            else "Selecciona una organización para realizar esta acción."
        ),
        **periodo,
    }


def exigir_contexto_mutable(contexto):
    if not contexto["contexto_mutable"] or not contexto["organizacion_activa"]:
        raise PermissionDenied(contexto["mensaje_contexto_accion"])
    if not contexto["disciplina_ids"]:
        raise PermissionDenied("No tienes clases activas asignadas en esta organización.")


def filtrar_periodo(queryset, campo, contexto):
    if contexto["periodo_todos"]:
        return queryset
    return queryset.filter(
        **{
            f"{campo}__month": contexto["periodo_mes"],
            f"{campo}__year": contexto["periodo_anio"],
        }
    )

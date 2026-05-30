from django.core.exceptions import PermissionDenied

from .models import Disciplina
from personas.models import Persona, PersonaRol
from personas.permissions import normalizar_codigo_rol

ROLE_ADMIN = "admin"
ROLE_STAFF_ASISTENCIA = "staff_asistencia"
ROLE_PROFESOR = "profesor"
ROLE_ESTUDIANTE = "estudiante"


def get_persona_for_user(user):
    if not user.is_authenticated:
        raise PermissionDenied("Debes iniciar sesión.")
    if user.is_superuser:
        return None
    try:
        return user.persona
    except Persona.DoesNotExist:
        raise PermissionDenied("Tu usuario no está vinculado a una persona.")


def usuario_tiene_roles(user, roles: list[str]) -> bool:
    if not roles:
        return True
    if user.is_superuser:
        return True
    if user.is_staff:
        return True
    roles_normalizados = {normalizar_codigo_rol(rol) for rol in roles}
    persona = getattr(user, "persona", None)
    if not persona:
        return False
    roles_usuario = {
        normalizar_codigo_rol(codigo)
        for codigo in PersonaRol.objects.filter(
            persona=persona,
            activo=True,
        ).values_list("rol__codigo", flat=True)
    }
    return bool(roles_usuario.intersection(roles_normalizados)) or PersonaRol.objects.filter(
        persona=persona,
        activo=True,
        rol__codigo__in=roles,
    ).exists()


def disciplinas_vigentes_qs(organizacion=None):
    """Retorna solo disciplinas vigentes para selección operativa."""
    queryset = Disciplina.objects.filter(activa=True)
    if organizacion is not None:
        queryset = queryset.filter(organizacion=organizacion)
    return queryset.order_by("nombre", "nivel")


def profesores_vigentes_qs(organizacion=None):
    """Retorna solo profesores vigentes para selección operativa."""
    queryset = Persona.objects.filter(
        activo=True,
        roles__rol__codigo="PROFESOR",
        roles__activo=True,
    )
    if organizacion is not None:
        queryset = queryset.filter(roles__organizacion=organizacion)
    return queryset.distinct().order_by("apellidos", "nombres")

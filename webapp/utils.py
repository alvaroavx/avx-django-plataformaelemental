from django.core.exceptions import PermissionDenied

from cuentas.models import Persona, PersonaRol

ROLE_ADMIN = "admin"
ROLE_STAFF_ASISTENCIA = "staff_asistencia"
ROLE_STAFF_FINANZAS = "staff_finanzas"
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
    persona = getattr(user, "persona", None)
    if not persona:
        return False
    return PersonaRol.objects.filter(
        persona=persona,
        activo=True,
        rol__codigo__in=roles,
    ).exists()

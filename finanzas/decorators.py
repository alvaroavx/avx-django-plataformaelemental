from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied

from database.models import PersonaRol


ADMIN_CODES = {"ADMINISTRADOR", "ADMIN", "admin"}


def usuario_es_admin_finanzas(user) -> bool:
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    persona = getattr(user, "persona", None)
    if not persona:
        return False
    return PersonaRol.objects.filter(
        persona=persona,
        activo=True,
        rol__codigo__in=ADMIN_CODES,
    ).exists()


def admin_finanzas_required(view_func):
    @login_required
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not usuario_es_admin_finanzas(request.user):
            raise PermissionDenied("Debes tener rol ADMINISTRADOR para acceder a finanzas.")
        return view_func(request, *args, **kwargs)

    return _wrapped

from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied

from .utils import usuario_tiene_roles


def role_required(*roles):
    def decorator(view_func):
        @login_required
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            from plataformaelemental.context import organizacion_desde_request

            if not roles:
                return view_func(request, *args, **kwargs)
            organizacion = organizacion_desde_request(request)
            if not (request.user.is_superuser or request.user.is_staff) and organizacion is None:
                raise PermissionDenied("Debes seleccionar una organización autorizada para operar.")
            if usuario_tiene_roles(request.user, roles, organizacion=organizacion):
                return view_func(request, *args, **kwargs)
            raise PermissionDenied("No tienes permisos para acceder.")

        return _wrapped_view

    return decorator

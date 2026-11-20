from rest_framework import permissions

from .models import ApiAccessKey


class ApiKeyLecturaOUsuarioAutenticado(permissions.BasePermission):
    message = "Debes autenticarte o usar una API key valida."

    def has_permission(self, request, view):
        tiene_api_key = isinstance(getattr(request, "auth", None), ApiAccessKey)
        if request.method in permissions.SAFE_METHODS:
            return tiene_api_key or bool(request.user and request.user.is_authenticated)
        return bool(request.user and request.user.is_authenticated)

from rest_framework.throttling import SimpleRateThrottle

from .models import ApiAccessKey


class BaseIdentidadThrottle(SimpleRateThrottle):
    def get_cache_key(self, request, view):
        identidad = self.obtener_identidad(request)
        if identidad is None:
            return None
        return self.cache_format % {
            "scope": self.scope,
            "ident": identidad,
        }

    def obtener_identidad(self, request):
        if isinstance(getattr(request, "auth", None), ApiAccessKey):
            return f"apikey:{request.auth.pk}"
        if getattr(request, "user", None) and request.user.is_authenticated:
            return f"user:{request.user.pk}"
        return f"ip:{self.get_ident(request)}"


class ApiBurstRateThrottle(BaseIdentidadThrottle):
    scope = "api_burst"


class ApiSustainedRateThrottle(BaseIdentidadThrottle):
    scope = "api_sustained"


class AuthBurstRateThrottle(BaseIdentidadThrottle):
    scope = "auth_burst"


class AuthSustainedRateThrottle(BaseIdentidadThrottle):
    scope = "auth_sustained"

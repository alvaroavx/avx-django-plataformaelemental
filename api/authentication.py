from django.contrib.auth.models import AnonymousUser
from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.exceptions import AuthenticationFailed

from .models import ApiAccessKey


class ApiKeyAuthentication(BaseAuthentication):
    keyword = "ApiKey"
    meta_header = "HTTP_X_API_KEY"

    def authenticate(self, request):
        clave_plana = request.META.get(self.meta_header, "").strip()
        if not clave_plana:
            auth = get_authorization_header(request).split()
            if auth and auth[0].lower() == self.keyword.lower().encode("utf-8"):
                if len(auth) != 2:
                    raise AuthenticationFailed("Header de API key invalido.")
                clave_plana = auth[1].decode("utf-8").strip()

        if not clave_plana:
            return None

        api_key = ApiAccessKey.desde_clave_plana(clave_plana)
        if api_key is None:
            raise AuthenticationFailed("API key invalida.")

        api_key.registrar_uso()
        request.api_key = api_key
        return AnonymousUser(), api_key

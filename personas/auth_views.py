from django.conf import settings
from django.contrib import messages
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.views import LoginView
from django.http import HttpResponseRedirect
from django.shortcuts import redirect
from django.utils.http import url_has_allowed_host_and_scheme

from allauth.socialaccount.providers.base.constants import AuthProcess
from allauth.socialaccount.providers.google.views import GoogleOAuth2Adapter
from allauth.socialaccount.providers.oauth2.views import OAuth2CallbackView, OAuth2LoginView


class GoogleOAuth2AdapterElemental(GoogleOAuth2Adapter):
    """Evita que claims de Google lleguen a persistirse en SocialAccount."""

    def complete_login(self, request, app, token, **kwargs):
        social_login = super().complete_login(request, app, token, **kwargs)
        social_login.account.extra_data = {}
        return social_login


class FormularioEmergenciaSuperusuario(AuthenticationForm):
    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if not user.is_superuser:
            raise self.get_invalid_login_error()


class LoginOperacionalView(LoginView):
    def dispatch(self, request, *args, **kwargs):
        if settings.GOOGLE_AUTH_ENFORCED and request.method == "POST":
            messages.error(request, "El acceso operativo requiere una cuenta Google autorizada.")
            return redirect("login")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["google_auth_enabled"] = settings.GOOGLE_AUTH_ENABLED
        context["google_auth_enforced"] = settings.GOOGLE_AUTH_ENFORCED
        return context


class LoginEmergenciaView(LoginView):
    authentication_form = FormularioEmergenciaSuperusuario

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["modo_emergencia"] = True
        context["google_auth_enabled"] = False
        context["google_auth_enforced"] = False
        return context


class InicioGoogleView(OAuth2LoginView):
    def dispatch(self, request, *args, **kwargs):
        if request.method != "POST":
            return HttpResponseRedirect(settings.LOGIN_URL)
        if not settings.GOOGLE_AUTH_ENABLED or not settings.GOOGLE_OAUTH_CONFIGURED:
            messages.error(request, "El acceso con Google no está disponible en este momento.")
            return redirect("login")
        siguiente = request.POST.get(self.redirect_field_name, "")
        if siguiente and not url_has_allowed_host_and_scheme(
            siguiente,
            allowed_hosts={request.get_host()},
            require_https=request.is_secure(),
        ):
            messages.error(request, "La dirección de retorno no es válida.")
            return redirect("login")
        auth_params = {"access_type": "online"}
        if request.POST.get("cambiar_cuenta") == "1":
            auth_params["prompt"] = "select_account"
        return self.get_provider().redirect(
            request,
            process=AuthProcess.LOGIN,
            next_url=siguiente or None,
            scope=["openid", "email", "profile"],
            auth_params=auth_params,
        )


class CallbackGoogleView(OAuth2CallbackView):
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)


InicioGoogleView.redirect_field_name = "next"
inicio_google = InicioGoogleView.adapter_view(GoogleOAuth2AdapterElemental)
callback_google = CallbackGoogleView.adapter_view(GoogleOAuth2AdapterElemental)

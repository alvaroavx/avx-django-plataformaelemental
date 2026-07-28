from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models.functions import Lower, Trim
from django.shortcuts import redirect

from allauth.core.exceptions import ImmediateHttpResponse
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter

from auditoria.models import AuditLog
from auditoria.services import registrar_auditoria
from .solicitudes_acceso import guardar_identidad_pendiente, solicitud_canonica_por_identidad
from .models import SolicitudAcceso
from .identidades_google import COMPATIBLE, SIN_VINCULO, bloquear_identidad_google, bloquear_usuario_google, estado_vinculo_google


def normalizar_email_google(valor):
    return (valor or "").strip().lower()


class AdaptadorSocialGoogleElemental(DefaultSocialAccountAdapter):
    """Permite solo identidades Google ya autorizadas en la plataforma."""

    provider_google = "google"

    def pre_social_login(self, request, sociallogin):
        if not settings.GOOGLE_AUTH_ENABLED:
            self._bloquear(request, "El acceso con Google no está disponible en este momento.")
        if sociallogin.account.provider != self.provider_google:
            self._bloquear(request, "No se pudo validar el proveedor de autenticación.")

        # Mantiene la misma exclusión transaccional que la resolución
        # administrativa. allauth crea SocialAccount sólo dentro de este flujo
        # validado, nunca desde el servicio administrativo.
        with transaction.atomic():
            bloquear_identidad_google(provider=self.provider_google, subject=sociallogin.account.uid)
            return self._pre_social_login_bloqueado(request, sociallogin)

    def _pre_social_login_bloqueado(self, request, sociallogin):
        if sociallogin.is_existing:
            usuario = sociallogin.user
            self._limpiar_datos_sociales(sociallogin)
            if not usuario or not usuario.is_active:
                self._solicitar_revision(request, sociallogin)
            return

        email = self._email_verificado(sociallogin)
        if not email:
            self._bloquear(request, "Google no entregó un correo verificado para esta cuenta.")

        solicitud_canonica = solicitud_canonica_por_identidad(
            provider=self.provider_google,
            provider_subject=sociallogin.account.uid,
            bloquear=True,
        )
        if solicitud_canonica:
            if solicitud_canonica.estado != SolicitudAcceso.Estado.APROBADA:
                self._solicitar_revision(request, sociallogin)
            if not solicitud_canonica.usuario_resuelto_id:
                self._bloquear(request, "No encontramos un acceso habilitado para esta cuenta.")
            usuario = get_user_model().objects.select_for_update().get(pk=solicitud_canonica.usuario_resuelto_id)
            if not usuario.is_active:
                self._bloquear(request, "No encontramos un acceso habilitado para esta cuenta.")
            bloquear_usuario_google(provider=self.provider_google, usuario_id=usuario.pk)
            if estado_vinculo_google(
                provider=self.provider_google,
                subject=sociallogin.account.uid,
                usuario=usuario,
                bloquear=True,
            ) not in {SIN_VINCULO, COMPATIBLE}:
                self._bloquear(request, "Esta cuenta Google no coincide con el acceso existente.")
            self._limpiar_datos_sociales(sociallogin)
            sociallogin.connect(request, usuario)
            return

        usuarios = list(
            get_user_model()
            .objects.annotate(email_normalizado=Lower(Trim("email")))
            .filter(email_normalizado=email)
            .order_by("id")
        )
        if len(usuarios) != 1 or not usuarios[0].is_active:
            self._solicitar_revision(request, sociallogin)

        usuario = get_user_model().objects.select_for_update().get(pk=usuarios[0].pk)
        bloquear_usuario_google(provider=self.provider_google, usuario_id=usuario.pk)
        if estado_vinculo_google(
            provider=self.provider_google,
            subject=sociallogin.account.uid,
            usuario=usuario,
            bloquear=True,
        ) != SIN_VINCULO:
            self._solicitar_revision(request, sociallogin)

        self._limpiar_datos_sociales(sociallogin)
        sociallogin.connect(request, usuario)
        registrar_auditoria(
            usuario=usuario,
            accion=AuditLog.ACCION_ASOCIAR,
            dominio="personas",
            objeto=usuario,
            resumen="Primer vínculo Google completado para usuario existente",
            metadata={"provider": self.provider_google, "user_id": usuario.pk},
        )

    def is_open_for_signup(self, request, sociallogin):
        return False

    def on_authentication_error(self, request, provider, error=None, exception=None, extra_context=None):
        if getattr(provider, "id", None) == self.provider_google:
            messages.error(request, "No fue posible completar el acceso con Google.")
            raise ImmediateHttpResponse(redirect("login"))
        return super().on_authentication_error(
            request,
            provider,
            error=error,
            exception=exception,
            extra_context=extra_context,
        )

    def _email_verificado(self, sociallogin):
        email_usuario = normalizar_email_google(getattr(sociallogin.user, "email", ""))
        for email_address in sociallogin.email_addresses:
            email = normalizar_email_google(email_address.email)
            if email and email == email_usuario and email_address.verified:
                return email
        return ""

    def _limpiar_datos_sociales(self, sociallogin):
        sociallogin.account.extra_data = {}
        if sociallogin.account.pk:
            sociallogin.account.save(update_fields=["extra_data"])

    def _bloquear(self, request, mensaje):
        messages.error(request, mensaje)
        raise ImmediateHttpResponse(redirect("login"))

    def _solicitar_revision(self, request, sociallogin):
        if settings.ACCESS_REQUESTS_ENABLED and guardar_identidad_pendiente(request, sociallogin):
            raise ImmediateHttpResponse(redirect("personas:solicitud_acceso"))
        self._bloquear(request, "No encontramos un acceso habilitado para esta cuenta.")

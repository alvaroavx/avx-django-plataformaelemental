from datetime import datetime, timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from auditoria.models import AuditLog
from auditoria.services import registrar_auditoria

from .models import SolicitudAcceso


SESION_IDENTIDAD_PENDIENTE = "identidad_google_pendiente"
TTL_IDENTIDAD_PENDIENTE = timedelta(minutes=10)
LIMITE_SOLICITUDES_POR_IDENTIDAD = 5
VENTANA_RATE_LIMIT_SOLICITUDES = timedelta(hours=24)
CAMPOS_IDENTIDAD_PENDIENTE = {"provider", "provider_subject", "email", "nombre", "expira_en"}


def normalizar_email_google(valor):
    return (valor or "").strip().lower()


def guardar_identidad_pendiente(request, sociallogin):
    email = _email_verificado(sociallogin)
    subject = getattr(sociallogin.account, "uid", "")
    if not email or not isinstance(subject, str) or not subject.strip():
        return False
    request.session[SESION_IDENTIDAD_PENDIENTE] = {
        "provider": "google",
        "provider_subject": subject.strip(),
        "email": email,
        "nombre": (getattr(sociallogin.user, "get_full_name", lambda: "")() or "").strip(),
        "expira_en": (timezone.now() + TTL_IDENTIDAD_PENDIENTE).isoformat(),
    }
    request.session.modified = True
    return True


def obtener_identidad_pendiente(request):
    identidad = request.session.get(SESION_IDENTIDAD_PENDIENTE)
    if not isinstance(identidad, dict) or not CAMPOS_IDENTIDAD_PENDIENTE.issubset(identidad):
        return _limpiar_identidad(request)
    try:
        expira_en = datetime.fromisoformat(identidad["expira_en"])
    except (TypeError, ValueError):
        return _limpiar_identidad(request)
    valores_validos = (
        identidad["provider"] == "google"
        and isinstance(identidad["provider_subject"], str)
        and bool(identidad["provider_subject"].strip())
        and bool(normalizar_email_google(identidad["email"]))
        and bool(getattr(expira_en, "tzinfo", None))
    )
    if not valores_validos or expira_en <= timezone.now():
        return _limpiar_identidad(request)
    return {**identidad, "email": normalizar_email_google(identidad["email"])}


def solicitud_pendiente_o_ultima(identidad):
    base = SolicitudAcceso.objects.filter(provider="google", provider_subject=identidad["provider_subject"])
    return base.filter(estado=SolicitudAcceso.Estado.PENDIENTE).first() or base.first()


def crear_o_recuperar_solicitud(request, identidad):
    filtros = {"estado": SolicitudAcceso.Estado.PENDIENTE}
    existente = SolicitudAcceso.objects.filter(
        provider="google", provider_subject=identidad["provider_subject"], **filtros
    ).first() or SolicitudAcceso.objects.filter(email_normalizado=identidad["email"], **filtros).first()
    if existente:
        _auditar(existente, "Solicitud de acceso pendiente recuperada")
        return existente, False
    ultima = solicitud_pendiente_o_ultima(identidad)
    if ultima and ultima.estado == SolicitudAcceso.Estado.RECHAZADA:
        return ultima, False
    _aplicar_rate_limit(identidad)
    try:
        with transaction.atomic():
            solicitud = SolicitudAcceso.objects.create(
                provider="google",
                provider_subject=identidad["provider_subject"],
                email=identidad["email"],
                email_normalizado=identidad["email"],
                nombre=identidad["nombre"],
            )
    except IntegrityError:
        solicitud = SolicitudAcceso.objects.filter(
            estado=SolicitudAcceso.Estado.PENDIENTE,
            provider="google",
            provider_subject=identidad["provider_subject"],
        ).first() or SolicitudAcceso.objects.filter(
            estado=SolicitudAcceso.Estado.PENDIENTE,
            email_normalizado=identidad["email"],
        ).first()
        if not solicitud:
            raise
        _auditar(solicitud, "Solicitud de acceso pendiente recuperada")
        return solicitud, False
    _auditar(solicitud, "Solicitud de acceso creada")
    return solicitud, True


def _email_verificado(sociallogin):
    email_usuario = normalizar_email_google(getattr(sociallogin.user, "email", ""))
    for direccion in sociallogin.email_addresses:
        email = normalizar_email_google(direccion.email)
        if email and email == email_usuario and direccion.verified:
            return email
    return ""


def _limpiar_identidad(request):
    request.session.pop(SESION_IDENTIDAD_PENDIENTE, None)
    return None


def _aplicar_rate_limit(identidad):
    solicitudes_previas = SolicitudAcceso.objects.filter(
        provider="google",
        provider_subject=identidad["provider_subject"],
        creada_en__gte=timezone.now() - VENTANA_RATE_LIMIT_SOLICITUDES,
    ).count()
    if solicitudes_previas >= LIMITE_SOLICITUDES_POR_IDENTIDAD:
        raise ValidationError("Demasiados intentos. Vuelve a iniciar sesión con Google.")


def _auditar(solicitud, resumen):
    registrar_auditoria(
        usuario=None,
        accion=AuditLog.ACCION_ASOCIAR if "recuperada" in resumen else AuditLog.ACCION_CREAR,
        dominio="personas",
        objeto=solicitud,
        resumen=resumen,
        metadata={"provider": "google"},
    )

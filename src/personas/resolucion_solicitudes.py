from django.contrib.auth import get_user_model
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from auditoria.models import AuditLog
from auditoria.services import registrar_auditoria

from .models import Persona, PersonaRol, SolicitudAcceso
from .identidades_google import COMPATIBLE, SIN_VINCULO, bloquear_identidad_google, bloquear_usuario_google, estado_vinculo_google


class ConflictoIdentidadGoogle(ValidationError):
    pass


def _denegar_gestion(*, solicitud_id, administrador, accion):
    registrar_auditoria(
        usuario=administrador,
        accion=accion,
        dominio="personas",
        modelo="personas.SolicitudAcceso",
        objeto_id=solicitud_id,
        resumen="Intento de gestión de solicitud sin permiso",
        metadata={"denegado": True},
    )
    raise ValidationError("No tienes permiso para gestionar solicitudes de acceso.")


def aprobar_solicitud(*, solicitud_id, administrador, tipo_resolucion, organizacion, rol, usuario=None, persona=None, nombres="", apellidos="", nota_interna="", confirmar_correo_distinto=False):
    if not settings.ACCESS_REQUESTS_ENABLED or not settings.ACCESS_REQUEST_APPROVAL_ENABLED:
        raise ValidationError("La aprobación de solicitudes no está habilitada.")
    if not administrador.has_perm("personas.gestionar_solicitudes_acceso"):
        _denegar_gestion(solicitud_id=solicitud_id, administrador=administrador, accion=AuditLog.ACCION_ASOCIAR)
    try:
        with transaction.atomic():
            return _aprobar_solicitud_bloqueada(solicitud_id=solicitud_id, administrador=administrador, tipo_resolucion=tipo_resolucion, organizacion=organizacion, rol=rol, usuario=usuario, persona=persona, nombres=nombres, apellidos=apellidos, nota_interna=nota_interna, confirmar_correo_distinto=confirmar_correo_distinto)
    except ConflictoIdentidadGoogle:
        registrar_auditoria(usuario=administrador, accion=AuditLog.ACCION_ASOCIAR, dominio="personas", modelo="personas.SolicitudAcceso", objeto_id=solicitud_id, resumen="Intento conflictivo de resolución Google", metadata={"conflicto_google": True})
        raise
    except Exception:
        registrar_auditoria(usuario=administrador, accion=AuditLog.ACCION_CAMBIAR_ESTADO, dominio="personas", modelo="personas.SolicitudAcceso", objeto_id=solicitud_id, resumen="Resolución de solicitud revertida", metadata={"revertida": True})
        raise


def _aprobar_solicitud_bloqueada(*, solicitud_id, administrador, tipo_resolucion, organizacion, rol, usuario, persona, nombres, apellidos, nota_interna, confirmar_correo_distinto):
        solicitud = SolicitudAcceso.objects.select_for_update().get(pk=solicitud_id)
        usuario_creado = False
        persona_creada = False
        persona_asociada = False
        if solicitud.estado != SolicitudAcceso.Estado.PENDIENTE:
            raise ValidationError("La solicitud ya fue resuelta.")
        # Debe adquirirse antes de revisar SocialAccount: protege también el
        # caso sin fila social existente frente al siguiente SocialLogin.
        bloquear_identidad_google(provider=solicitud.provider, subject=solicitud.provider_subject)
        if tipo_resolucion == SolicitudAcceso.TipoResolucion.USUARIO_EXISTENTE:
            if not usuario:
                raise ValidationError("Debes seleccionar un usuario activo existente.")
            usuario = get_user_model().objects.select_for_update().get(pk=usuario.pk)
            if not usuario.is_active:
                raise ValidationError("Debes seleccionar un usuario activo existente.")
            persona = Persona.objects.select_for_update().filter(user=usuario).first()
            if not persona or not persona.activo:
                raise ValidationError("El usuario seleccionado debe tener una Persona activa asociada.")
        elif tipo_resolucion == SolicitudAcceso.TipoResolucion.PERSONA_EXISTENTE:
            if not persona:
                raise ValidationError("Debes seleccionar una Persona existente sin User.")
            persona = Persona.objects.select_for_update().get(pk=persona.pk)
            if not persona.activo or persona.user_id:
                raise ValidationError("La Persona seleccionada debe estar activa y no tener un User asociado.")
            usuario = get_user_model().objects.create_user(username=_username_disponible(solicitud.email), email=solicitud.email)
            usuario.set_unusable_password()
            usuario.save(update_fields=["password"])
            usuario_creado = True
            persona.user = usuario
            persona.save(update_fields=["user"])
            persona_asociada = True
        elif tipo_resolucion == SolicitudAcceso.TipoResolucion.USUARIO_NUEVO:
            if not nombres.strip() or not apellidos.strip():
                raise ValidationError("Debes indicar nombres y apellidos para la nueva Persona.")
            if Persona.objects.filter(email__iexact=solicitud.email).exists():
                raise ValidationError("Ya existe una Persona con ese correo; debes seleccionarla explícitamente.")
            usuario = get_user_model().objects.create_user(username=_username_disponible(solicitud.email), email=solicitud.email)
            usuario.set_unusable_password()
            usuario.save(update_fields=["password"])
            usuario_creado = True
            persona = Persona(nombres=nombres.strip(), apellidos=apellidos.strip(), email=solicitud.email, user=usuario)
            persona.full_clean()
            persona.save()
            persona_creada = True
        else:
            raise ValidationError("Tipo de resolución inválido.")

        bloquear_usuario_google(provider=solicitud.provider, usuario_id=usuario.pk)
        estado_vinculo = estado_vinculo_google(provider=solicitud.provider, subject=solicitud.provider_subject, usuario=usuario, bloquear=True)
        if estado_vinculo not in {SIN_VINCULO, COMPATIBLE}:
            raise ConflictoIdentidadGoogle("Existe un conflicto con una identidad Google ya asociada.")
        correo_distinto = (usuario.email or "").strip().lower() != solicitud.email_normalizado
        if correo_distinto and (not confirmar_correo_distinto or not nota_interna.strip()):
            raise ValidationError("Debes confirmar la diferencia de correo e ingresar una nota interna.")

        try:
            persona_rol, creada = PersonaRol.objects.get_or_create(
                persona=persona, rol=rol, organizacion=organizacion, defaults={"activo": True}
            )
        except IntegrityError:
            persona_rol = PersonaRol.objects.select_for_update().get(persona=persona, rol=rol, organizacion=organizacion)
            creada = False
        if not persona_rol.activo:
            persona_rol.activo = True
            persona_rol.save(update_fields=["activo"])
        solicitud.estado = SolicitudAcceso.Estado.APROBADA
        solicitud.tipo_resolucion = tipo_resolucion
        solicitud.usuario_resuelto = usuario
        solicitud.resuelta_por = administrador
        solicitud.resuelta_en = timezone.now()
        solicitud.nota_interna = nota_interna
        solicitud.excepcion_correo_confirmada = correo_distinto
        solicitud.organizacion_resuelta = organizacion
        solicitud.rol_resuelto = rol
        solicitud.save(update_fields=["estado", "tipo_resolucion", "usuario_resuelto", "organizacion_resuelta", "rol_resuelto", "resuelta_por", "resuelta_en", "nota_interna", "excepcion_correo_confirmada"])
        registrar_auditoria(usuario=administrador, accion=AuditLog.ACCION_CAMBIAR_ESTADO, dominio="personas", objeto=solicitud, organizacion=organizacion, resumen="Solicitud de acceso aprobada", metadata={"tipo_resolucion": tipo_resolucion, "usuario_id": usuario.pk, "persona_id": persona.pk, "rol_id": rol.pk, "excepcion_correo": correo_distinto})
        registrar_auditoria(usuario=administrador, accion=AuditLog.ACCION_ASOCIAR if not usuario_creado else AuditLog.ACCION_CREAR, dominio="personas", objeto=solicitud, organizacion=organizacion, resumen="Usuario asociado a resolución de acceso" if not usuario_creado else "Usuario creado para resolución de acceso", metadata={"usuario_id": usuario.pk})
        if persona_creada or persona_asociada:
            registrar_auditoria(usuario=administrador, accion=AuditLog.ACCION_CREAR if persona_creada else AuditLog.ACCION_ASOCIAR, dominio="personas", objeto=solicitud, organizacion=organizacion, resumen="Persona creada para resolución de acceso" if persona_creada else "Persona asociada a usuario de acceso", metadata={"persona_id": persona.pk})
        if creada:
            registrar_auditoria(usuario=administrador, accion=AuditLog.ACCION_ASOCIAR, dominio="personas", objeto=solicitud, organizacion=organizacion, resumen="Rol asignado durante resolución de acceso", metadata={"persona_id": persona.pk, "rol_id": rol.pk, "organizacion_id": organizacion.pk})
        return solicitud, creada


def rechazar_solicitud(*, solicitud_id, administrador, motivo_rechazo=""):
    if not settings.ACCESS_REQUESTS_ENABLED or not settings.ACCESS_REQUEST_APPROVAL_ENABLED:
        raise ValidationError("La aprobación de solicitudes no está habilitada.")
    if not administrador.has_perm("personas.gestionar_solicitudes_acceso"):
        _denegar_gestion(solicitud_id=solicitud_id, administrador=administrador, accion=AuditLog.ACCION_CAMBIAR_ESTADO)
    with transaction.atomic():
        solicitud = SolicitudAcceso.objects.select_for_update().get(pk=solicitud_id)
        if solicitud.estado != SolicitudAcceso.Estado.PENDIENTE:
            raise ValidationError("La solicitud ya fue resuelta.")
        solicitud.estado = SolicitudAcceso.Estado.RECHAZADA
        solicitud.resuelta_por = administrador
        solicitud.resuelta_en = timezone.now()
        solicitud.motivo_rechazo = motivo_rechazo
        solicitud.save(update_fields=["estado", "resuelta_por", "resuelta_en", "motivo_rechazo"])
        registrar_auditoria(usuario=administrador, accion=AuditLog.ACCION_CAMBIAR_ESTADO, dominio="personas", objeto=solicitud, resumen="Solicitud de acceso rechazada", metadata={})
        return solicitud


def reabrir_solicitud(*, solicitud_id, administrador, nota_interna):
    if not settings.ACCESS_REQUESTS_ENABLED or not settings.ACCESS_REQUEST_APPROVAL_ENABLED:
        raise ValidationError("La reapertura de solicitudes no está habilitada.")
    if not administrador.has_perm("personas.gestionar_solicitudes_acceso"):
        _denegar_gestion(solicitud_id=solicitud_id, administrador=administrador, accion=AuditLog.ACCION_CAMBIAR_ESTADO)
    if not nota_interna.strip():
        raise ValidationError("Debes registrar una nota interna para reabrir la solicitud.")
    try:
        with transaction.atomic():
            solicitud = SolicitudAcceso.objects.select_for_update().get(pk=solicitud_id)
            if solicitud.estado != SolicitudAcceso.Estado.RECHAZADA:
                raise ValidationError("Solo se pueden reabrir solicitudes rechazadas.")
            solicitud.estado = SolicitudAcceso.Estado.PENDIENTE
            solicitud.resuelta_por = None
            solicitud.resuelta_en = None
            solicitud.nota_interna = nota_interna
            solicitud.motivo_rechazo = ""
            solicitud.save(update_fields=["estado", "resuelta_por", "resuelta_en", "nota_interna", "motivo_rechazo"])
            registrar_auditoria(usuario=administrador, accion=AuditLog.ACCION_CAMBIAR_ESTADO, dominio="personas", objeto=solicitud, resumen="Solicitud de acceso reabierta", metadata={})
            return solicitud
    except IntegrityError as error:
        raise ValidationError("No se puede reabrir mientras exista otra solicitud pendiente para esta identidad.") from error


def _username_disponible(email):
    base = (email.split("@", 1)[0] or "usuario")[:140]
    User = get_user_model()
    candidato = base
    numero = 1
    while User.objects.filter(username=candidato).exists():
        numero += 1
        candidato = f"{base[:140-len(str(numero))-1]}-{numero}"
    return candidato

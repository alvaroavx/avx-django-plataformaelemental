from django.db import connection

from allauth.socialaccount.models import SocialAccount

from .models import SolicitudAcceso


SIN_VINCULO = "sin_vinculo"
COMPATIBLE = "compatible"
SUB_OTRO_USUARIO = "sub_otro_usuario"
USUARIO_OTRO_SUB = "usuario_otro_sub"


def bloquear_identidad_google(*, provider, subject):
    """Serializa decisiones sobre una identidad Google durante una transacción.

    ``select_for_update`` no protege una fila de ``SocialAccount`` que todavía
    no existe. En PostgreSQL se toma por eso un advisory lock transaccional
    estable por proveedor y sujeto. La aprobación y el adaptador allauth usan
    esta misma función antes de leer o conectar la cuenta: ningún flujo de la
    aplicación puede observar un hueco y crear una asociación contradictoria.

    La degradación fuera de PostgreSQL mantiene compatibilidad para entornos
    de documentación; las pruebas y producción usan PostgreSQL.
    """
    if connection.vendor == "postgresql":
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT pg_advisory_xact_lock(hashtext(%s), hashtext(%s))",
                [provider, subject],
            )


def bloquear_usuario_google(*, provider, usuario_id):
    """Serializa asociaciones Google que convergen al mismo User.

    Dos callbacks con ``sub`` distintos pueden tomar locks de identidad
    diferentes y, sin este segundo lock, ambos observar una cuenta social aún
    ausente para el mismo usuario. El orden de adquisición es siempre
    identidad Google y luego User.
    """
    if connection.vendor == "postgresql":
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT pg_advisory_xact_lock(hashtext(%s), hashtext(%s))",
                [provider, str(usuario_id)],
            )


def estado_vinculo_google(*, provider, subject, usuario, bloquear=False):
    cuentas_sub = SocialAccount.objects.filter(provider=provider, uid=subject)
    cuentas_usuario = SocialAccount.objects.filter(user=usuario, provider=provider)
    if bloquear:
        cuentas_sub = cuentas_sub.select_for_update()
        cuentas_usuario = cuentas_usuario.select_for_update()
    cuenta_sub = cuentas_sub.first()
    cuenta_usuario = cuentas_usuario.first()
    if cuenta_sub and cuenta_sub.user_id != usuario.pk:
        return SUB_OTRO_USUARIO
    if cuenta_usuario and cuenta_usuario.uid != subject:
        return USUARIO_OTRO_SUB
    solicitudes_aprobadas = SolicitudAcceso.objects.filter(
        provider=provider,
        usuario_resuelto=usuario,
        estado=SolicitudAcceso.Estado.APROBADA,
    ).exclude(provider_subject=subject)
    if bloquear:
        solicitudes_aprobadas = solicitudes_aprobadas.select_for_update()
    if solicitudes_aprobadas.exists():
        return USUARIO_OTRO_SUB
    if cuenta_sub and cuenta_sub.user_id == usuario.pk:
        return COMPATIBLE
    return SIN_VINCULO

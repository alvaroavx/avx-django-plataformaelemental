from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied

from .models import PersonaRol


ROL_ADMIN = "admin"
ROL_FINANZAS = "finanzas"
ROL_PROFESOR = "profesor"
ROL_SOLO_LECTURA = "solo_lectura"

ACCION_VER_FINANZAS = "ver_finanzas"
ACCION_OPERAR_PAGOS = "operar_pagos"
ACCION_OPERAR_TRANSACCIONES = "operar_transacciones"
ACCION_OPERAR_DOCUMENTOS = "operar_documentos"
ACCION_EXPORTAR_DATOS = "exportar_datos"
ACCION_EDITAR_ASISTENCIAS = "editar_asistencias"
ACCION_ADMINISTRAR_PERSONAS = "administrar_personas"
ACCION_ADMINISTRAR_SESIONES = "administrar_sesiones"
ACCION_VER_SESION = "ver_sesion"
ACCION_LIBERAR_CLASE = "liberar_clase"
ACCION_REVERTIR_PAGO = "revertir_pago"

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}

ROL_ALIASES = {
    "ADMIN": ROL_ADMIN,
    "ADMINISTRADOR": ROL_ADMIN,
    "SUPERADMIN": ROL_ADMIN,
    "FINANZAS": ROL_FINANZAS,
    "PROFESOR": ROL_PROFESOR,
    "SOLO_LECTURA": ROL_SOLO_LECTURA,
    "LECTURA": ROL_SOLO_LECTURA,
    "READ_ONLY": ROL_SOLO_LECTURA,
    "STAFF_ASISTENCIA": "staff_asistencia",
}

ACCION_ROLES = {
    ACCION_VER_FINANZAS: {ROL_ADMIN, ROL_FINANZAS, ROL_SOLO_LECTURA},
    ACCION_OPERAR_PAGOS: {ROL_ADMIN, ROL_FINANZAS},
    ACCION_OPERAR_TRANSACCIONES: {ROL_ADMIN, ROL_FINANZAS},
    ACCION_OPERAR_DOCUMENTOS: {ROL_ADMIN, ROL_FINANZAS},
    ACCION_EXPORTAR_DATOS: {ROL_ADMIN, ROL_FINANZAS},
    ACCION_EDITAR_ASISTENCIAS: {ROL_ADMIN, "staff_asistencia", ROL_PROFESOR},
    ACCION_ADMINISTRAR_PERSONAS: {ROL_ADMIN},
    ACCION_ADMINISTRAR_SESIONES: {ROL_ADMIN, "staff_asistencia"},
    ACCION_VER_SESION: {ROL_ADMIN, "staff_asistencia", ROL_PROFESOR},
    ACCION_LIBERAR_CLASE: {ROL_ADMIN},
    ACCION_REVERTIR_PAGO: {ROL_ADMIN},
}


def normalizar_codigo_rol(codigo):
    codigo_normalizado = (codigo or "").strip()
    if not codigo_normalizado:
        return ""
    return ROL_ALIASES.get(codigo_normalizado.upper(), codigo_normalizado.lower())


def usuario_tiene_permiso(user, accion, *, organizacion=None):
    if not user.is_authenticated:
        return False
    if user.is_superuser or user.is_staff:
        return True
    roles_permitidos = ACCION_ROLES.get(accion, set())
    if not roles_permitidos:
        return False
    persona = getattr(user, "persona", None)
    if not persona:
        return False

    roles_qs = PersonaRol.objects.filter(persona=persona, activo=True)
    if organizacion is not None:
        roles_qs = roles_qs.filter(organizacion=organizacion)
    roles_usuario = {normalizar_codigo_rol(codigo) for codigo in roles_qs.values_list("rol__codigo", flat=True)}
    return bool(roles_usuario.intersection(roles_permitidos))


def permiso_requerido(accion, *, accion_lectura=None, mensaje=None):
    def decorator(view_func):
        @login_required
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            from plataformaelemental.context import organizacion_desde_request

            accion_requerida = accion_lectura if request.method in SAFE_METHODS and accion_lectura else accion
            organizacion = organizacion_desde_request(request)
            if not (request.user.is_superuser or request.user.is_staff) and organizacion is None:
                raise PermissionDenied("Debes seleccionar una organización autorizada para operar.")
            if usuario_tiene_permiso(request.user, accion_requerida, organizacion=organizacion):
                return view_func(request, *args, **kwargs)
            raise PermissionDenied(mensaje or "No tienes permisos para acceder.")

        return _wrapped

    return decorator

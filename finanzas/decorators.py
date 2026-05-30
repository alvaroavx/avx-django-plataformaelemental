from personas.permissions import (
    ACCION_EXPORTAR_DATOS,
    ACCION_OPERAR_DOCUMENTOS,
    ACCION_OPERAR_PAGOS,
    ACCION_OPERAR_TRANSACCIONES,
    ACCION_VER_FINANZAS,
    permiso_requerido,
    usuario_tiene_permiso,
)


def usuario_es_admin_finanzas(user) -> bool:
    return usuario_tiene_permiso(user, ACCION_OPERAR_PAGOS)


finanzas_read_required = permiso_requerido(
    ACCION_VER_FINANZAS,
    mensaje="Debes tener permiso de lectura financiera para acceder a finanzas.",
)
pagos_required = permiso_requerido(
    ACCION_OPERAR_PAGOS,
    accion_lectura=ACCION_VER_FINANZAS,
    mensaje="Debes tener permiso de pagos para modificar finanzas.",
)
documentos_required = permiso_requerido(
    ACCION_OPERAR_DOCUMENTOS,
    accion_lectura=ACCION_VER_FINANZAS,
    mensaje="Debes tener permiso de documentos tributarios para modificar finanzas.",
)
transacciones_required = permiso_requerido(
    ACCION_OPERAR_TRANSACCIONES,
    accion_lectura=ACCION_VER_FINANZAS,
    mensaje="Debes tener permiso de transacciones para modificar finanzas.",
)
exportar_finanzas_required = permiso_requerido(
    ACCION_EXPORTAR_DATOS,
    mensaje="Debes tener permiso de exportacion para descargar datos.",
)
admin_finanzas_required = pagos_required

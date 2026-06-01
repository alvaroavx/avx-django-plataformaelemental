import logging
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from django.db import models, transaction

from .models import AuditLog


logger = logging.getLogger(__name__)

CAMPO_SENSIBLE = object()
CAMPOS_SENSIBLES_DEFAULT = {"rut", "email", "telefono"}


def registrar_auditoria(
    *,
    usuario,
    accion,
    dominio,
    resumen,
    objeto=None,
    modelo=None,
    objeto_id=None,
    organizacion=None,
    metadata=None,
):
    usuario = usuario if getattr(usuario, "is_authenticated", False) else None
    modelo_nombre = modelo or _modelo_nombre(objeto)
    objeto_id_valor = objeto_id if objeto_id is not None else getattr(objeto, "pk", "")
    metadata_segura = _serializar_metadata(metadata or {})

    def _crear_log():
        try:
            AuditLog.objects.create(
                usuario=usuario,
                accion=accion,
                dominio=dominio,
                modelo=modelo_nombre,
                objeto_id=str(objeto_id_valor or ""),
                organizacion=organizacion,
                resumen=resumen,
                metadata=metadata_segura,
            )
        except Exception:
            logger.warning("No se pudo registrar auditoria %s.%s", dominio, accion, exc_info=True)

    transaction.on_commit(_crear_log)


def registrar_cambio(
    *,
    usuario,
    dominio,
    objeto,
    organizacion=None,
    resumen,
    antes,
    despues,
    campos,
    accion=AuditLog.ACCION_EDITAR,
    metadata=None,
    campos_sensibles=None,
):
    cambios = _diff_campos(
        antes,
        despues,
        campos=campos,
        campos_sensibles=campos_sensibles or CAMPOS_SENSIBLES_DEFAULT,
    )
    if not cambios:
        return
    metadata_final = {"cambios": cambios}
    if metadata:
        metadata_final.update(metadata)
    registrar_auditoria(
        usuario=usuario,
        accion=accion,
        dominio=dominio,
        objeto=objeto,
        organizacion=organizacion,
        resumen=resumen,
        metadata=metadata_final,
    )


def _modelo_nombre(objeto):
    if objeto is None:
        return ""
    return objeto._meta.label


def _serializar_metadata(valor):
    if isinstance(valor, dict):
        return {str(clave): _serializar_metadata(item) for clave, item in valor.items()}
    if isinstance(valor, (list, tuple, set)):
        return [_serializar_metadata(item) for item in valor]
    if isinstance(valor, Decimal):
        return str(valor)
    if isinstance(valor, (datetime, date, UUID)):
        return valor.isoformat() if hasattr(valor, "isoformat") else str(valor)
    if isinstance(valor, models.Model):
        return valor.pk
    return valor


def _diff_campos(antes, despues, *, campos, campos_sensibles=None):
    campos_sensibles = set(campos_sensibles or ())
    cambios = {}
    for campo in campos:
        valor_antes = _valor_campo(antes, campo)
        valor_despues = _valor_campo(despues, campo)
        if valor_antes == valor_despues:
            continue
        if campo in campos_sensibles:
            cambios[campo] = {
                "cambio": True,
                "antes_presente": bool(valor_antes),
                "despues_presente": bool(valor_despues),
            }
        else:
            cambios[campo] = {
                "antes": _serializar_metadata(valor_antes),
                "despues": _serializar_metadata(valor_despues),
            }
    return cambios


def _valor_campo(origen, campo):
    if isinstance(origen, dict):
        return origen.get(campo)
    return getattr(origen, campo)

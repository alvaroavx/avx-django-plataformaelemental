from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from auditoria.models import AuditLog
from auditoria.services import registrar_auditoria, registrar_cambio
from finanzas.services import asignar_consumo_asistencia

from ..models import Asistencia, ClaseLiberada


@transaction.atomic
def cambiar_estado_asistencia(*, asistencia, estado, usuario):
    if estado not in dict(Asistencia.Estado.choices):
        raise ValidationError("El estado de asistencia no es válido.")
    asistencia = (
        Asistencia.objects.select_for_update()
        .select_related("sesion__disciplina__organizacion")
        .get(pk=asistencia.pk)
    )
    estado_anterior = asistencia.estado
    if estado_anterior != estado:
        asistencia.estado = estado
        asistencia.save(update_fields=["estado"])
        registrar_cambio(
            usuario=usuario,
            dominio="asistencias",
            objeto=asistencia,
            organizacion=asistencia.sesion.disciplina.organizacion,
            resumen="Estado de asistencia actualizado",
            antes={"estado": estado_anterior},
            despues={"estado": estado},
            campos=["estado"],
            accion=AuditLog.ACCION_CAMBIAR_ESTADO,
            metadata={
                "asistencia_id": asistencia.pk,
                "sesion_id": asistencia.sesion_id,
                "persona_id": asistencia.persona_id,
            },
        )
    consumo = asignar_consumo_asistencia(asistencia)
    return asistencia, consumo


@transaction.atomic
def liberar_clase(*, asistencia, motivo, usuario):
    motivo = (motivo or "").strip()
    if not motivo:
        raise ValidationError("El motivo de la clase liberada es obligatorio.")
    asistencia = (
        Asistencia.objects.select_for_update()
        .select_related("sesion__disciplina__organizacion")
        .get(pk=asistencia.pk)
    )
    organizacion = asistencia.sesion.disciplina.organizacion
    liberacion, creada = ClaseLiberada.objects.select_for_update().get_or_create(
        asistencia=asistencia,
        defaults={
            "organizacion": organizacion,
            "motivo": motivo,
            "liberada_por": usuario,
        },
    )
    if not creada and liberacion.revertida_en is None:
        raise ValidationError("La asistencia ya tiene una clase liberada activa.")
    if not creada:
        liberacion.organizacion = organizacion
        liberacion.motivo = motivo
        liberacion.liberada_por = usuario
        liberacion.liberada_en = timezone.now()
        liberacion.revertida_por = None
        liberacion.revertida_en = None
        liberacion.save(
            update_fields=[
                "organizacion",
                "motivo",
                "liberada_por",
                "liberada_en",
                "revertida_por",
                "revertida_en",
            ]
        )
    consumo = asignar_consumo_asistencia(asistencia)
    registrar_auditoria(
        usuario=usuario,
        accion=AuditLog.ACCION_CAMBIAR_ESTADO,
        dominio="asistencias",
        objeto=liberacion,
        organizacion=organizacion,
        resumen="Clase liberada",
        metadata={
            "asistencia_id": asistencia.pk,
            "sesion_id": asistencia.sesion_id,
            "motivo": motivo,
        },
    )
    return liberacion, consumo


@transaction.atomic
def revertir_clase_liberada(*, asistencia, usuario):
    asistencia = (
        Asistencia.objects.select_for_update()
        .select_related("sesion__disciplina__organizacion")
        .get(pk=asistencia.pk)
    )
    try:
        liberacion = ClaseLiberada.objects.select_for_update().get(
            asistencia=asistencia,
            revertida_en__isnull=True,
        )
    except ClaseLiberada.DoesNotExist as exc:
        raise ValidationError("La asistencia no tiene una clase liberada activa.") from exc
    liberacion.revertida_por = usuario
    liberacion.revertida_en = timezone.now()
    liberacion.save(update_fields=["revertida_por", "revertida_en"])
    consumo = asignar_consumo_asistencia(asistencia)
    registrar_auditoria(
        usuario=usuario,
        accion=AuditLog.ACCION_CAMBIAR_ESTADO,
        dominio="asistencias",
        objeto=liberacion,
        organizacion=asistencia.sesion.disciplina.organizacion,
        resumen="Clase liberada revertida",
        metadata={
            "asistencia_id": asistencia.pk,
            "sesion_id": asistencia.sesion_id,
        },
    )
    return liberacion, consumo

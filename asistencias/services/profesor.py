from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from auditoria.models import AuditLog
from auditoria.services import registrar_auditoria
from finanzas.models import AttendanceConsumption
from personas.models import Organizacion, Persona, PersonaRol, Rol
from personas.permissions import (
    ACCION_ADMINISTRAR_PERSONAS,
    ACCION_ADMINISTRAR_SESIONES,
    usuario_tiene_permiso,
)

from ..models import (
    AlumnoDisciplina,
    AsignacionProfesorDisciplina,
    Asistencia,
    LiberacionSesion,
    SesionClase,
)
from .dominio import liberar_clase, revertir_clase_liberada


def _exigir_permiso_administrativo(*, user, accion, organizacion):
    if not usuario_tiene_permiso(
        user,
        accion,
        organizacion=organizacion,
        permitir_staff_global=False,
    ):
        raise PermissionDenied("Solo una persona administradora autorizada puede activar esta relación.")


@transaction.atomic
def activar_asignacion_profesor(*, user, asignacion):
    asignacion = (
        AsignacionProfesorDisciplina.objects.select_for_update()
        .select_related("disciplina__organizacion", "profesor")
        .get(pk=asignacion.pk)
    )
    _exigir_permiso_administrativo(
        user=user,
        accion=ACCION_ADMINISTRAR_SESIONES,
        organizacion=asignacion.disciplina.organizacion,
    )
    requiere_revision = (
        asignacion.origen == AsignacionProfesorDisciplina.Origen.HISTORICA
        and (not asignacion.revisada_por_id or not asignacion.revisada_en)
    )
    if not asignacion.activa or requiere_revision:
        asignacion.activa = True
        asignacion.asignada_por = user
        asignacion.revisada_por = user
        asignacion.revisada_en = timezone.now()
        asignacion.save(
            update_fields=[
                "activa",
                "asignada_por",
                "revisada_por",
                "revisada_en",
            ]
        )
        registrar_auditoria(
            usuario=user,
            accion=AuditLog.ACCION_CAMBIAR_ESTADO,
            dominio="asistencias",
            objeto=asignacion,
            organizacion=asignacion.disciplina.organizacion,
            resumen="Asignación profesor-disciplina activada explícitamente",
            metadata={
                "disciplina_id": asignacion.disciplina_id,
                "profesor_id": asignacion.profesor_id,
                "origen": asignacion.origen,
            },
        )
    return asignacion


@transaction.atomic
def activar_matricula_alumno(*, user, matricula):
    matricula = (
        AlumnoDisciplina.objects.select_for_update()
        .select_related("disciplina__organizacion", "alumno")
        .get(pk=matricula.pk)
    )
    _exigir_permiso_administrativo(
        user=user,
        accion=ACCION_ADMINISTRAR_PERSONAS,
        organizacion=matricula.disciplina.organizacion,
    )
    requiere_revision = (
        matricula.origen == AlumnoDisciplina.Origen.HISTORICA
        and (not matricula.revisada_por_id or not matricula.revisada_en)
    )
    if not matricula.activa or requiere_revision:
        matricula.activa = True
        matricula.asignada_por = user
        matricula.revisada_por = user
        matricula.revisada_en = timezone.now()
        matricula.save(
            update_fields=[
                "activa",
                "asignada_por",
                "revisada_por",
                "revisada_en",
            ]
        )
        registrar_auditoria(
            usuario=user,
            accion=AuditLog.ACCION_CAMBIAR_ESTADO,
            dominio="asistencias",
            objeto=matricula,
            organizacion=matricula.disciplina.organizacion,
            resumen="Matrícula alumno-disciplina activada explícitamente",
            metadata={
                "disciplina_id": matricula.disciplina_id,
                "alumno_id": matricula.alumno_id,
                "origen": matricula.origen,
            },
        )
    return matricula


def _ids_relaciones(relaciones):
    if hasattr(relaciones, "values_list"):
        return list(relaciones.values_list("pk", flat=True))
    return [relacion.pk for relacion in relaciones]


@transaction.atomic
def activar_asignaciones_profesor_en_lote(*, user, relaciones):
    """Activa una selección completa o revierte todo el lote ante un error."""
    ids = _ids_relaciones(relaciones)
    asignaciones = (
        AsignacionProfesorDisciplina.objects.select_for_update()
        .select_related("disciplina__organizacion", "profesor")
        .filter(pk__in=ids)
        .order_by("pk")
    )
    if asignaciones.count() != len(set(ids)):
        raise ValidationError("La selección contiene asignaciones inexistentes.")
    activadas = 0
    for asignacion in asignaciones:
        era_operativa = AsignacionProfesorDisciplina.objects.operativas().filter(
            pk=asignacion.pk
        ).exists()
        activar_asignacion_profesor(user=user, asignacion=asignacion)
        activadas += int(not era_operativa)
    return activadas


@transaction.atomic
def activar_matriculas_alumno_en_lote(*, user, relaciones):
    """Activa una selección completa o revierte todo el lote ante un error."""
    ids = _ids_relaciones(relaciones)
    matriculas = (
        AlumnoDisciplina.objects.select_for_update()
        .select_related("disciplina__organizacion", "alumno")
        .filter(pk__in=ids)
        .order_by("pk")
    )
    if matriculas.count() != len(set(ids)):
        raise ValidationError("La selección contiene matrículas inexistentes.")
    activadas = 0
    for matricula in matriculas:
        era_operativa = AlumnoDisciplina.objects.operativas().filter(pk=matricula.pk).exists()
        activar_matricula_alumno(user=user, matricula=matricula)
        activadas += int(not era_operativa)
    return activadas


@transaction.atomic
def asegurar_matricula_operativa(*, user, disciplina, alumno):
    _exigir_permiso_administrativo(
        user=user,
        accion=ACCION_ADMINISTRAR_PERSONAS,
        organizacion=disciplina.organizacion,
    )
    matricula, creada = AlumnoDisciplina.objects.select_for_update().get_or_create(
        disciplina=disciplina,
        alumno=alumno,
        defaults={
            "activa": True,
            "origen": AlumnoDisciplina.Origen.EXPLICITA,
            "asignada_por": user,
        },
    )
    if creada:
        registrar_auditoria(
            usuario=user,
            accion=AuditLog.ACCION_CREAR,
            dominio="asistencias",
            objeto=matricula,
            organizacion=disciplina.organizacion,
            resumen="Matrícula alumno-disciplina creada explícitamente",
            metadata={"disciplina_id": disciplina.pk, "alumno_id": alumno.pk},
        )
        return matricula
    return activar_matricula_alumno(user=user, matricula=matricula)


@transaction.atomic
def asegurar_asignaciones_profesores(*, disciplina, profesores, user=None):
    """Convierte una asignación administrativa de sesión en alcance explícito de clase."""
    _exigir_permiso_administrativo(
        user=user,
        accion=ACCION_ADMINISTRAR_SESIONES,
        organizacion=disciplina.organizacion,
    )
    for profesor in profesores:
        asignacion, creada = AsignacionProfesorDisciplina.objects.get_or_create(
            disciplina=disciplina,
            profesor=profesor,
            defaults={
                "activa": True,
                "origen": AsignacionProfesorDisciplina.Origen.EXPLICITA,
                "asignada_por": user,
            },
        )
        if not creada:
            activar_asignacion_profesor(user=user, asignacion=asignacion)
        if creada:
            registrar_auditoria(
                usuario=user,
                accion=AuditLog.ACCION_CREAR,
                dominio="asistencias",
                objeto=asignacion,
                organizacion=disciplina.organizacion,
                resumen="Profesor asignado a disciplina",
                metadata={"disciplina_id": disciplina.pk, "profesor_id": profesor.pk},
            )


def organizaciones_profesor(user):
    """Organizaciones donde la persona tiene un rol PROFESOR activo."""
    persona = getattr(user, "persona", None)
    if not user.is_authenticated or not user.is_active or not persona or not persona.activo:
        return Organizacion.objects.none()
    return (
        Organizacion.objects.filter(
            persona_roles__persona=persona,
            persona_roles__activo=True,
            persona_roles__rol__codigo__iexact="PROFESOR",
        )
        .distinct()
        .order_by("nombre", "pk")
    )


def rol_profesor_activo(user, *, organizacion_id):
    """Resuelve un rol exacto; nunca elige una organización implícitamente."""
    persona = getattr(user, "persona", None)
    if not user.is_authenticated or not user.is_active or not persona or not persona.activo:
        return None
    if organizacion_id in (None, ""):
        return None
    try:
        return (
            PersonaRol.objects.select_related("organizacion", "rol")
            .filter(
                persona=persona,
                activo=True,
                organizacion_id=organizacion_id,
                rol__codigo__iexact="PROFESOR",
            )
            .first()
        )
    except (TypeError, ValueError, ValidationError):
        return None


def disciplinas_asignadas_profesor(user, *, organizacion_id):
    rol = rol_profesor_activo(user, organizacion_id=organizacion_id)
    if not rol:
        return AsignacionProfesorDisciplina.objects.none(), None
    asignaciones = AsignacionProfesorDisciplina.objects.operativas().select_related(
        "disciplina",
        "disciplina__organizacion",
    ).filter(
        profesor=rol.persona,
        disciplina__organizacion=rol.organizacion,
        disciplina__activa=True,
    )
    return asignaciones, rol


def sesion_en_alcance_profesor(user, *, organizacion_id, sesion_id):
    asignaciones, rol = disciplinas_asignadas_profesor(
        user,
        organizacion_id=organizacion_id,
    )
    if not rol:
        return None
    disciplina_ids = asignaciones.values_list("disciplina_id", flat=True)
    return (
        SesionClase.objects.select_related("disciplina", "disciplina__organizacion", "bloque")
        .prefetch_related("profesores")
        .filter(
            pk=sesion_id,
            disciplina__organizacion_id=organizacion_id,
            disciplina_id__in=disciplina_ids,
            profesores=rol.persona,
        )
        .first()
    )


@transaction.atomic
def crear_sesion_profesor(*, user, organizacion_id, disciplina, fecha):
    if fecha < timezone.localdate():
        raise ValidationError("La sesión debe programarse para hoy o una fecha futura.")
    if disciplina.organizacion_id != organizacion_id:
        raise PermissionDenied("No tienes asignación activa para esta clase.")
    asignacion = (
        AsignacionProfesorDisciplina.objects.operativas().select_for_update()
        .select_related("disciplina__organizacion", "profesor")
        .filter(
            disciplina=disciplina,
            profesor=getattr(user, "persona", None),
            disciplina__activa=True,
        )
        .first()
    )
    rol = rol_profesor_activo(user, organizacion_id=disciplina.organizacion_id)
    if not asignacion or not rol:
        raise PermissionDenied("No tienes asignación activa para esta clase.")
    sesion = SesionClase.objects.create(disciplina=disciplina, fecha=fecha)
    sesion.profesores.add(rol.persona)
    registrar_auditoria(
        usuario=user,
        accion=AuditLog.ACCION_CREAR,
        dominio="asistencias",
        objeto=sesion,
        organizacion=disciplina.organizacion,
        resumen="Sesión creada por profesor",
        metadata={"sesion_id": sesion.pk, "disciplina_id": disciplina.pk, "fecha": fecha},
    )
    return sesion


@transaction.atomic
def liberar_sesion_profesor(*, user, organizacion_id, sesion, motivo):
    motivo = (motivo or "").strip()
    if not motivo:
        raise ValidationError("La glosa o motivo de liberación es obligatorio.")
    sesion = (
        SesionClase.objects.select_for_update()
        .select_related("disciplina__organizacion")
        .get(pk=sesion.pk)
    )
    if not sesion_en_alcance_profesor(
        user,
        organizacion_id=organizacion_id,
        sesion_id=sesion.pk,
    ):
        raise PermissionDenied("No tienes asignación activa para esta sesión.")
    if sesion.estado == SesionClase.Estado.CANCELADA:
        raise ValidationError("La sesión ya está cancelada.")
    if hasattr(sesion, "liberacion_operativa"):
        raise ValidationError("La sesión ya tiene una liberación registrada.")
    liberacion = LiberacionSesion.objects.create(
        sesion=sesion,
        motivo=motivo,
        liberada_por=user,
    )
    estado_anterior = sesion.estado
    sesion.estado = SesionClase.Estado.CANCELADA
    sesion.save(update_fields=["estado"])
    registrar_auditoria(
        usuario=user,
        accion=AuditLog.ACCION_CAMBIAR_ESTADO,
        dominio="asistencias",
        objeto=liberacion,
        organizacion=sesion.disciplina.organizacion,
        resumen="Sesión liberada por profesor",
        metadata={
            "sesion_id": sesion.pk,
            "motivo": motivo,
            "estado_anterior": estado_anterior,
            "estado_nuevo": sesion.estado,
        },
    )
    return liberacion


@transaction.atomic
def cambiar_estado_sesion_profesor(*, user, organizacion_id, sesion, estado):
    if estado not in {SesionClase.Estado.ABIERTA, SesionClase.Estado.COMPLETADA}:
        raise ValidationError("El profesor solo puede abrir o cerrar una sesión propia.")
    sesion = SesionClase.objects.select_for_update().select_related("disciplina__organizacion").get(pk=sesion.pk)
    if not sesion_en_alcance_profesor(
        user,
        organizacion_id=organizacion_id,
        sesion_id=sesion.pk,
    ):
        raise PermissionDenied("No tienes asignación activa para esta sesión.")
    if sesion.estado == SesionClase.Estado.CANCELADA:
        raise ValidationError("Una sesión cancelada no puede reabrirse desde el espacio profesor.")
    anterior = sesion.estado
    if anterior == estado:
        return sesion
    sesion.estado = estado
    sesion.save(update_fields=["estado"])
    registrar_auditoria(
        usuario=user,
        accion=AuditLog.ACCION_CAMBIAR_ESTADO,
        dominio="asistencias",
        objeto=sesion,
        organizacion=sesion.disciplina.organizacion,
        resumen="Estado de sesión actualizado por profesor",
        metadata={"estado_anterior": anterior, "estado_nuevo": estado},
    )
    return sesion


@transaction.atomic
def crear_alumno_profesor(
    *,
    user,
    organizacion_id,
    disciplina,
    nombres,
    apellidos="",
    email="",
    telefono="",
):
    if disciplina.organizacion_id != organizacion_id:
        raise PermissionDenied("No tienes asignación activa para esta clase.")
    asignacion = AsignacionProfesorDisciplina.objects.operativas().select_for_update().filter(
        disciplina=disciplina,
        profesor=getattr(user, "persona", None),
    ).first()
    rol_profesor = rol_profesor_activo(user, organizacion_id=disciplina.organizacion_id)
    if not asignacion or not rol_profesor:
        raise PermissionDenied("No tienes asignación activa para esta clase.")
    persona = Persona(
        nombres=nombres.strip(),
        apellidos=apellidos.strip(),
        email=(email or "").strip() or None,
        telefono=telefono,
    )
    persona.full_clean()
    persona.save()
    rol_estudiante = Rol.objects.filter(codigo__iexact="ESTUDIANTE").first()
    if not rol_estudiante:
        raise ValidationError("No existe el rol ESTUDIANTE requerido para crear alumnos.")
    PersonaRol.objects.create(
        persona=persona,
        rol=rol_estudiante,
        organizacion=disciplina.organizacion,
        activo=True,
    )
    AlumnoDisciplina.objects.create(
        disciplina=disciplina,
        alumno=persona,
        origen=AlumnoDisciplina.Origen.EXPLICITA,
        asignada_por=user,
    )
    registrar_auditoria(
        usuario=user,
        accion=AuditLog.ACCION_CREAR,
        dominio="personas",
        objeto=persona,
        organizacion=disciplina.organizacion,
        resumen="Alumno creado por profesor",
        metadata={"persona_id": persona.pk, "disciplina_id": disciplina.pk},
    )
    return persona


def _exigir_sesion_profesor(*, user, organizacion_id, sesion_id):
    sesion = sesion_en_alcance_profesor(
        user,
        organizacion_id=organizacion_id,
        sesion_id=sesion_id,
    )
    if not sesion:
        raise PermissionDenied("No tienes asignación activa para esta sesión.")
    return sesion


@transaction.atomic
def quitar_asistente_profesor(*, user, organizacion_id, sesion, asistencia):
    sesion = _exigir_sesion_profesor(
        user=user,
        organizacion_id=organizacion_id,
        sesion_id=sesion.pk,
    )
    asistencia = (
        Asistencia.objects.select_for_update()
        .select_related("persona", "sesion__disciplina__organizacion")
        .filter(
            pk=asistencia.pk,
            sesion=sesion,
            persona__activo=True,
            persona__roles__organizacion_id=organizacion_id,
            persona__roles__rol__codigo__iexact="ESTUDIANTE",
            persona__roles__activo=True,
        )
        .first()
    )
    if not asistencia:
        raise PermissionDenied("La asistencia no pertenece a esta sesión.")
    consumo = AttendanceConsumption.objects.select_for_update().filter(
        asistencia=asistencia
    ).first()
    metadata = {
        "asistencia_id": asistencia.pk,
        "sesion_id": sesion.pk,
        "persona_id": asistencia.persona_id,
        "estado_asistencia": asistencia.estado,
        "consumo_id": consumo.pk if consumo else None,
        "pago_id": consumo.pago_id if consumo else None,
    }
    registrar_auditoria(
        usuario=user,
        accion=AuditLog.ACCION_ELIMINAR,
        dominio="asistencias",
        objeto=asistencia,
        organizacion=sesion.disciplina.organizacion,
        resumen="Asistente quitado de sesión por profesor",
        metadata=metadata,
    )
    asistencia.delete()


@transaction.atomic
def liberar_clase_profesor(*, user, organizacion_id, sesion, asistencia, motivo):
    sesion = _exigir_sesion_profesor(
        user=user,
        organizacion_id=organizacion_id,
        sesion_id=sesion.pk,
    )
    asistencia = Asistencia.objects.select_for_update().filter(
        pk=asistencia.pk,
        sesion=sesion,
        persona__roles__organizacion_id=organizacion_id,
        persona__roles__rol__codigo__iexact="ESTUDIANTE",
        persona__roles__activo=True,
    ).first()
    if not asistencia:
        raise PermissionDenied("La asistencia no pertenece a esta organización y sesión.")
    return liberar_clase(asistencia=asistencia, motivo=motivo, usuario=user)


@transaction.atomic
def revertir_clase_liberada_profesor(*, user, organizacion_id, sesion, asistencia):
    sesion = _exigir_sesion_profesor(
        user=user,
        organizacion_id=organizacion_id,
        sesion_id=sesion.pk,
    )
    asistencia = Asistencia.objects.select_for_update().filter(
        pk=asistencia.pk,
        sesion=sesion,
        persona__roles__organizacion_id=organizacion_id,
        persona__roles__rol__codigo__iexact="ESTUDIANTE",
        persona__roles__activo=True,
    ).first()
    if not asistencia:
        raise PermissionDenied("La asistencia no pertenece a esta organización y sesión.")
    return revertir_clase_liberada(asistencia=asistencia, usuario=user)

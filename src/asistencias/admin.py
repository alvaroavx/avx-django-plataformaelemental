from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.db.models import Count
from django.utils import timezone

from auditoria.models import AuditLog
from auditoria.services import registrar_auditoria
from personas.models import Persona
from personas.permissions import (
    ACCION_ADMINISTRAR_PERSONAS,
    ACCION_ADMINISTRAR_SESIONES,
    usuario_tiene_permiso,
)

from .models import (
    AlumnoDisciplina,
    AsignacionProfesorDisciplina,
    Asistencia,
    BloqueHorario,
    ClaseLiberada,
    Disciplina,
    LiberacionSesion,
    SesionClase,
)
from .services import (
    activar_asignaciones_profesor_en_lote,
    activar_matriculas_alumno_en_lote,
)


class ActivacionRelacionAdminMixin:
    accion_permiso = None
    servicio_activacion_lote = None
    resumen_activacion = "Relación operativa activada explícitamente"
    actions = ("activar_relaciones_seleccionadas",)

    def get_actions(self, request):
        actions = super().get_actions(request)
        actions.pop("delete_selected", None)
        return actions

    @admin.action(description="Activar relaciones seleccionadas tras revisión")
    def activar_relaciones_seleccionadas(self, request, queryset):
        total = self.servicio_activacion_lote(user=request.user, relaciones=queryset)
        self.message_user(
            request,
            f"Se activaron explícitamente {total} relaciones; la operación quedó auditada.",
        )

    def save_model(self, request, obj, form, change):
        anterior = None
        if obj.pk:
            anterior = type(obj).objects.filter(pk=obj.pk).values("activa").first()
        requiere_revision_historica = (
            obj.origen == obj.Origen.HISTORICA
            and (not obj.revisada_por_id or not obj.revisada_en)
        )
        activando = obj.activa and (
            not anterior or not anterior["activa"] or requiere_revision_historica
        )
        desactivando = bool(anterior and anterior["activa"] and not obj.activa)
        if activando or desactivando:
            organizacion = obj.disciplina.organizacion
            if not usuario_tiene_permiso(
                request.user,
                self.accion_permiso,
                organizacion=organizacion,
                permitir_staff_global=False,
            ):
                raise PermissionDenied("No tienes permisos para activar esta relación.")
            obj.asignada_por = request.user
            obj.revisada_por = request.user
            obj.revisada_en = timezone.now()
        super().save_model(request, obj, form, change)
        if activando or desactivando:
            registrar_auditoria(
                usuario=request.user,
                accion=AuditLog.ACCION_CAMBIAR_ESTADO,
                dominio="asistencias",
                objeto=obj,
                organizacion=obj.disciplina.organizacion,
                resumen=(
                    self.resumen_activacion
                    if activando
                    else "Relación operativa desactivada administrativamente"
                ),
                metadata={"origen": obj.origen, "activa": obj.activa},
            )


@admin.register(AsignacionProfesorDisciplina)
class AsignacionProfesorDisciplinaAdmin(ActivacionRelacionAdminMixin, admin.ModelAdmin):
    accion_permiso = ACCION_ADMINISTRAR_SESIONES
    servicio_activacion_lote = staticmethod(activar_asignaciones_profesor_en_lote)
    resumen_activacion = "Asignación profesor-disciplina activada explícitamente"
    list_display = (
        "profesor",
        "disciplina",
        "organizacion",
        "origen",
        "activa",
        "revisada_en",
        "revisada_por",
        "asignada_en",
    )
    list_filter = ("activa", "origen", "disciplina__organizacion", "disciplina")
    search_fields = ("profesor__nombres", "profesor__apellidos", "disciplina__nombre")
    autocomplete_fields = ("profesor", "disciplina", "asignada_por", "revisada_por")
    readonly_fields = (
        "origen",
        "asignada_en",
        "revisada_en",
        "revisada_por",
        "asignada_por",
    )

    @admin.display(ordering="disciplina__organizacion", description="Organización")
    def organizacion(self, obj):
        return obj.disciplina.organizacion


@admin.register(AlumnoDisciplina)
class AlumnoDisciplinaAdmin(ActivacionRelacionAdminMixin, admin.ModelAdmin):
    accion_permiso = ACCION_ADMINISTRAR_PERSONAS
    servicio_activacion_lote = staticmethod(activar_matriculas_alumno_en_lote)
    resumen_activacion = "Matrícula alumno-disciplina activada explícitamente"
    list_display = (
        "alumno",
        "disciplina",
        "organizacion",
        "origen",
        "activa",
        "revisada_en",
        "revisada_por",
        "asignada_en",
    )
    list_filter = ("activa", "origen", "disciplina__organizacion", "disciplina")
    search_fields = ("alumno__nombres", "alumno__apellidos", "disciplina__nombre")
    autocomplete_fields = ("alumno", "disciplina", "asignada_por", "revisada_por")
    readonly_fields = (
        "origen",
        "asignada_en",
        "revisada_en",
        "revisada_por",
        "asignada_por",
    )

    @admin.display(ordering="disciplina__organizacion", description="Organización")
    def organizacion(self, obj):
        return obj.disciplina.organizacion


@admin.register(LiberacionSesion)
class LiberacionSesionAdmin(admin.ModelAdmin):
    list_display = ("sesion", "motivo", "liberada_por", "liberada_en")
    readonly_fields = ("sesion", "motivo", "liberada_por", "liberada_en")
    actions = None


@admin.register(Disciplina)
class DisciplinaAdmin(admin.ModelAdmin):
    list_display = ("nombre", "organizacion", "nivel", "badge_color", "activa", "creada_en")
    list_filter = ("organizacion", "activa", "badge_color", "nivel")
    search_fields = ("nombre", "nivel", "descripcion")
    list_per_page = 25


@admin.register(BloqueHorario)
class BloqueHorarioAdmin(admin.ModelAdmin):
    list_display = ("nombre", "organizacion", "dia_semana_display", "hora_inicio", "hora_fin", "disciplina")
    list_filter = ("organizacion", "dia_semana")
    search_fields = ("nombre", "disciplina__nombre")
    autocomplete_fields = ("disciplina",)
    list_select_related = ("organizacion", "disciplina")

    @admin.display(description="Dia")
    def dia_semana_display(self, obj):
        return obj.get_dia_semana_display()


@admin.register(SesionClase)
class SesionClaseAdmin(admin.ModelAdmin):
    list_display = ("fecha", "disciplina", "organizacion", "estado", "profesores_display", "asistentes_total")
    list_filter = (
        "disciplina__organizacion",
        "disciplina",
        "profesores",
        "estado",
        ("fecha", admin.DateFieldListFilter),
    )
    search_fields = ("disciplina__nombre", "profesores__nombres", "profesores__apellidos", "notas")
    autocomplete_fields = ("disciplina", "bloque", "profesores")
    list_select_related = ("disciplina", "disciplina__organizacion")
    date_hierarchy = "fecha"
    actions = None

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.select_related("disciplina", "disciplina__organizacion").prefetch_related("profesores").annotate(
            asistentes_total_admin=Count("asistencias", distinct=True)
        )

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        if db_field.name == "profesores":
            kwargs["queryset"] = (
                Persona.objects.filter(roles__rol__codigo="PROFESOR")
                .distinct()
                .order_by("apellidos", "nombres")
            )
        return super().formfield_for_manytomany(db_field, request, **kwargs)

    def profesores_display(self, obj):
        return obj.profesores_resumen or "-"

    profesores_display.short_description = "Profesores"

    @admin.display(description="Organizacion", ordering="disciplina__organizacion__nombre")
    def organizacion(self, obj):
        return obj.disciplina.organizacion

    @admin.display(description="Asistentes", ordering="asistentes_total_admin")
    def asistentes_total(self, obj):
        return obj.asistentes_total_admin


@admin.register(Asistencia)
class AsistenciaAdmin(admin.ModelAdmin):
    list_display = ("sesion", "persona", "estado", "organizacion", "fecha_sesion", "registrada_en")
    list_filter = (
        "estado",
        "sesion__disciplina__organizacion",
        "sesion__disciplina",
        ("sesion__fecha", admin.DateFieldListFilter),
        ("registrada_en", admin.DateFieldListFilter),
    )
    search_fields = ("persona__nombres", "persona__apellidos", "persona__rut", "sesion__disciplina__nombre")
    autocomplete_fields = ("sesion", "persona")
    list_select_related = ("sesion", "sesion__disciplina", "sesion__disciplina__organizacion", "persona")
    date_hierarchy = "registrada_en"
    actions = None

    @admin.display(description="Organizacion", ordering="sesion__disciplina__organizacion__nombre")
    def organizacion(self, obj):
        return obj.sesion.disciplina.organizacion

    @admin.display(description="Fecha sesion", ordering="sesion__fecha")
    def fecha_sesion(self, obj):
        return obj.sesion.fecha


@admin.register(ClaseLiberada)
class ClaseLiberadaAdmin(admin.ModelAdmin):
    list_display = (
        "asistencia",
        "organizacion",
        "motivo",
        "liberada_por",
        "liberada_en",
        "revertida_en",
    )
    list_filter = ("organizacion", "liberada_en", "revertida_en")
    readonly_fields = (
        "asistencia",
        "organizacion",
        "motivo",
        "liberada_por",
        "liberada_en",
        "revertida_por",
        "revertida_en",
    )
    actions = None

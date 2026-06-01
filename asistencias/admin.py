from django.contrib import admin
from django.db.models import Count

from personas.models import Persona

from .models import Asistencia, BloqueHorario, Disciplina, SesionClase


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

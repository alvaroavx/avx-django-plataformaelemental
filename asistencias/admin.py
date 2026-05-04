from django.contrib import admin

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
    list_display = ("disciplina", "fecha", "estado", "profesores_display", "cupo_maximo")
    list_filter = ("estado", "disciplina", ("fecha", admin.DateFieldListFilter))
    search_fields = ("disciplina__nombre", "profesores__nombres", "profesores__apellidos", "notas")
    autocomplete_fields = ("disciplina", "bloque", "profesores")
    list_select_related = ("disciplina",)
    date_hierarchy = "fecha"

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


@admin.register(Asistencia)
class AsistenciaAdmin(admin.ModelAdmin):
    list_display = ("sesion", "persona", "estado", "registrada_en")
    list_filter = (
        "estado",
        ("registrada_en", admin.DateFieldListFilter),
        "sesion__disciplina",
    )
    search_fields = ("persona__nombres", "persona__apellidos", "sesion__disciplina__nombre")
    autocomplete_fields = ("sesion", "persona")
    list_select_related = ("sesion", "persona")
    date_hierarchy = "registrada_en"

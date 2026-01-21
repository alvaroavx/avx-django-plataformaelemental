from django.contrib import admin

from .models import BloqueHorario, Disciplina, SesionClase


@admin.register(Disciplina)
class DisciplinaAdmin(admin.ModelAdmin):
    list_display = ("nombre", "organizacion", "nivel", "activa", "creada_en")
    list_filter = ("organizacion", "activa", "nivel")
    search_fields = ("nombre", "nivel", "descripcion")
    list_per_page = 25


@admin.register(BloqueHorario)
class BloqueHorarioAdmin(admin.ModelAdmin):
    list_display = ("nombre", "organizacion", "dia_semana_display", "hora_inicio", "hora_fin", "disciplina")
    list_filter = ("organizacion", "dia_semana")
    search_fields = ("nombre", "disciplina__nombre")
    autocomplete_fields = ("disciplina",)
    list_select_related = ("organizacion", "disciplina")

    @admin.display(description="Día")
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

    def profesores_display(self, obj):
        return obj.profesores_resumen or "-"

    profesores_display.short_description = "Profesores"

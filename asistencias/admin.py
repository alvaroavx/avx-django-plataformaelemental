from django.contrib import admin

from .models import Asistencia


@admin.register(Asistencia)
class AsistenciaAdmin(admin.ModelAdmin):
    list_display = ("sesion", "persona", "estado", "convenio", "registrada_en")
    list_filter = ("estado", ("registrada_en", admin.DateFieldListFilter), "sesion__disciplina", "convenio")
    search_fields = ("persona__nombres", "persona__apellidos", "sesion__disciplina__nombre")
    autocomplete_fields = ("sesion", "persona", "suscripcion", "convenio")
    list_select_related = ("sesion", "persona", "suscripcion", "convenio")
    date_hierarchy = "registrada_en"

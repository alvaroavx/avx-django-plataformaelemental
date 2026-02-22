from django.contrib import admin

from .models import Asistencia


@admin.register(Asistencia)
class AsistenciaAdmin(admin.ModelAdmin):
    list_display = ("sesion", "persona", "estado", "estado_cobro", "modalidad_cobro", "convenio", "registrada_en")
    list_filter = (
        "estado",
        "estado_cobro",
        "modalidad_cobro",
        ("registrada_en", admin.DateFieldListFilter),
        "sesion__disciplina",
        "convenio",
    )
    search_fields = ("persona__nombres", "persona__apellidos", "sesion__disciplina__nombre")
    autocomplete_fields = ("sesion", "persona", "convenio", "pago_plan")
    list_select_related = ("sesion", "persona", "convenio", "pago_plan")
    date_hierarchy = "registrada_en"

from django.contrib import admin

from .models import LiquidacionProfesor, MovimientoCaja, TarifaPagoProfesor


@admin.register(TarifaPagoProfesor)
class TarifaPagoProfesorAdmin(admin.ModelAdmin):
    list_display = ("organizacion", "disciplina", "monto_por_sesion", "vigente_desde", "vigente_hasta", "activo")
    list_filter = ("organizacion", "disciplina", "activo", ("vigente_desde", admin.DateFieldListFilter))
    search_fields = ("disciplina__nombre", "organizacion__nombre")
    list_select_related = ("organizacion", "disciplina")


@admin.register(LiquidacionProfesor)
class LiquidacionProfesorAdmin(admin.ModelAdmin):
    list_display = (
        "profesor",
        "organizacion",
        "periodo_inicio",
        "periodo_fin",
        "monto_total",
        "monto_retencion",
        "monto_neto",
        "estado",
    )
    list_filter = ("estado", "organizacion", ("periodo_inicio", admin.DateFieldListFilter))
    search_fields = ("profesor__nombres", "profesor__apellidos", "organizacion__nombre")
    filter_horizontal = ("sesiones",)
    autocomplete_fields = ("profesor", "organizacion")
    list_select_related = ("profesor", "organizacion")
    date_hierarchy = "periodo_inicio"


@admin.register(MovimientoCaja)
class MovimientoCajaAdmin(admin.ModelAdmin):
    list_display = ("fecha", "organizacion", "tipo", "categoria", "monto_total", "afecta_iva")
    list_filter = ("tipo", "categoria", "afecta_iva", ("fecha", admin.DateFieldListFilter))
    search_fields = ("glosa", "organizacion__nombre")
    autocomplete_fields = ("organizacion",)

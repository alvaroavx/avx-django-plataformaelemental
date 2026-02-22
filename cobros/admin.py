from django.contrib import admin

from .models import CondicionCobroPersona, ConvenioIntercambio, DocumentoVenta, Pago, Plan


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ("nombre", "organizacion", "precio", "duracion_dias", "clases_por_semana", "clases_por_mes", "activo")
    list_filter = ("organizacion", "activo")
    search_fields = ("nombre", "descripcion")
    list_select_related = ("organizacion",)


@admin.register(ConvenioIntercambio)
class ConvenioIntercambioAdmin(admin.ModelAdmin):
    list_display = ("nombre", "organizacion", "descuento_porcentaje", "vigente_desde", "vigente_hasta", "activo")
    list_filter = ("organizacion", "activo", ("vigente_desde", admin.DateFieldListFilter))
    search_fields = ("nombre", "descripcion")
    list_select_related = ("organizacion",)


@admin.register(DocumentoVenta)
class DocumentoVentaAdmin(admin.ModelAdmin):
    list_display = ("numero", "organizacion", "monto_total", "estado", "fecha_emision")
    list_filter = ("estado", "organizacion", ("fecha_emision", admin.DateFieldListFilter))
    search_fields = ("numero",)
    list_select_related = ("organizacion",)


@admin.register(Pago)
class PagoAdmin(admin.ModelAdmin):
    list_display = (
        "persona",
        "plan",
        "sesion",
        "tipo",
        "monto",
        "fecha_pago",
        "metodo",
        "clases_total",
        "clases_usadas",
        "valido_hasta",
        "carryover_approved",
        "freeze_days",
    )
    list_filter = ("tipo", "metodo", ("fecha_pago", admin.DateFieldListFilter))
    search_fields = ("documento__numero", "referencia", "persona__nombres", "persona__apellidos")
    autocomplete_fields = ("documento", "persona", "sesion", "plan")
    list_select_related = ("documento", "persona", "sesion", "plan")


@admin.register(CondicionCobroPersona)
class CondicionCobroPersonaAdmin(admin.ModelAdmin):
    list_display = (
        "persona",
        "organizacion",
        "tipo",
        "tarifa_clase_especial",
        "vigente_desde",
        "vigente_hasta",
        "activo",
    )
    list_filter = ("tipo", "activo", "organizacion")
    search_fields = ("persona__nombres", "persona__apellidos", "organizacion__nombre")
    autocomplete_fields = ("persona", "organizacion")
    list_select_related = ("persona", "organizacion")

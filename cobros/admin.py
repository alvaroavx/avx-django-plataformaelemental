from django.contrib import admin

from .models import ConvenioIntercambio, DocumentoVenta, Pago, Plan, Suscripcion


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ("nombre", "organizacion", "precio", "duracion_dias", "clases_por_semana", "activo")
    list_filter = ("organizacion", "activo")
    search_fields = ("nombre", "descripcion")
    list_select_related = ("organizacion",)


@admin.register(ConvenioIntercambio)
class ConvenioIntercambioAdmin(admin.ModelAdmin):
    list_display = ("nombre", "organizacion", "descuento_porcentaje", "vigente_desde", "vigente_hasta", "activo")
    list_filter = ("organizacion", "activo", ("vigente_desde", admin.DateFieldListFilter))
    search_fields = ("nombre", "descripcion")
    list_select_related = ("organizacion",)


@admin.register(Suscripcion)
class SuscripcionAdmin(admin.ModelAdmin):
    list_display = ("persona", "plan", "estado", "fecha_inicio", "fecha_fin", "monto_objetivo", "clases_asignadas", "clases_usadas")
    list_filter = ("estado", "plan__organizacion", ("fecha_inicio", admin.DateFieldListFilter))
    search_fields = ("persona__nombres", "persona__apellidos", "plan__nombre")
    filter_horizontal = ("convenios",)
    autocomplete_fields = ("persona", "plan")
    list_select_related = ("persona", "plan")
    date_hierarchy = "fecha_inicio"


@admin.register(DocumentoVenta)
class DocumentoVentaAdmin(admin.ModelAdmin):
    list_display = ("numero", "organizacion", "suscripcion", "monto_total", "estado", "fecha_emision")
    list_filter = ("estado", "organizacion", ("fecha_emision", admin.DateFieldListFilter))
    search_fields = ("numero", "suscripcion__persona__nombres", "suscripcion__persona__apellidos")
    autocomplete_fields = ("suscripcion",)
    list_select_related = ("organizacion", "suscripcion")


@admin.register(Pago)
class PagoAdmin(admin.ModelAdmin):
    list_display = ("persona", "suscripcion", "sesion", "tipo", "documento", "monto", "fecha_pago", "metodo")
    list_filter = ("tipo", "metodo", ("fecha_pago", admin.DateFieldListFilter))
    search_fields = ("documento__numero", "referencia", "persona__nombres", "persona__apellidos")
    autocomplete_fields = ("documento", "persona", "suscripcion", "sesion")
    list_select_related = ("documento", "persona", "suscripcion", "sesion")

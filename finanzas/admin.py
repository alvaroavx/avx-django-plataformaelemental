from django.contrib import admin

from .models import AttendanceConsumption, Category, DocumentoTributario, Payment, PaymentPlan, Transaction


@admin.register(PaymentPlan)
class PaymentPlanAdmin(admin.ModelAdmin):
    list_display = ("nombre", "organizacion", "num_clases", "precio", "precio_incluye_iva", "activo")
    list_filter = ("organizacion", "activo", "precio_incluye_iva")
    search_fields = ("nombre", "organizacion__nombre")


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("fecha_pago", "persona", "organizacion", "monto_total", "clases_asignadas", "metodo_pago")
    list_filter = ("organizacion", "metodo_pago", "aplica_iva")
    search_fields = ("persona__nombres", "persona__apellidos")


@admin.register(DocumentoTributario)
class DocumentoTributarioAdmin(admin.ModelAdmin):
    list_display = ("fecha_emision", "organizacion", "tipo_documento", "folio", "monto_total", "fuente")
    list_filter = ("organizacion", "tipo_documento", "fuente")
    search_fields = ("folio", "nombre_emisor", "nombre_receptor", "rut_emisor", "rut_receptor")


@admin.register(AttendanceConsumption)
class AttendanceConsumptionAdmin(admin.ModelAdmin):
    list_display = ("clase_fecha", "persona", "estado", "pago")
    list_filter = ("estado",)
    search_fields = ("persona__nombres", "persona__apellidos")


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("nombre", "tipo", "activa")
    list_filter = ("tipo", "activa")
    search_fields = ("nombre",)


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ("fecha", "organizacion", "tipo", "categoria", "monto")
    list_filter = ("organizacion", "tipo", "categoria")
    search_fields = ("descripcion", "categoria__nombre")

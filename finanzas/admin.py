from django.contrib import admin

from database.models import AttendanceConsumption, Category, Invoice, Payment, PaymentPlan, Transaction


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


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ("fecha_emision", "organizacion", "tipo", "folio", "monto_total")
    list_filter = ("organizacion", "tipo")
    search_fields = ("folio", "cliente")


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

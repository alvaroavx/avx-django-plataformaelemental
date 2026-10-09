from django.contrib import admin
from .models import AttendanceConsumption, Category, LotePago, Payment, PaymentPlan, Transaction


@admin.register(LotePago)
class LotePagoAdmin(admin.ModelAdmin):
    list_display = ("creado_en", "organizacion", "cantidad_pagos", "monto_total", "confirmado_en", "creado_por")
    list_filter = ("organizacion", "confirmado_en")
    readonly_fields = tuple(field.name for field in LotePago._meta.fields)
    actions = None


@admin.register(PaymentPlan)
class PaymentPlanAdmin(admin.ModelAdmin):
    list_display = ("nombre", "organizacion", "num_clases", "precio", "precio_incluye_iva", "activo")
    list_filter = ("organizacion", "activo", "precio_incluye_iva")
    search_fields = ("nombre", "organizacion__nombre")


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        "fecha_pago",
        "persona",
        "organizacion",
        "monto_total",
        "metodo_pago",
        "clases_asignadas",
        "disciplina",
        "transaccion",
        "registrado_por",
        "revertido_en",
        "creado_en",
    )
    list_filter = ("organizacion", "metodo_pago", "aplica_iva", ("fecha_pago", admin.DateFieldListFilter), ("creado_en", admin.DateFieldListFilter))
    search_fields = (
        "persona__nombres",
        "persona__apellidos",
        "persona__rut",
        "numero_comprobante",
    )
    readonly_fields = (
        "monto_neto",
        "monto_iva",
        "monto_total",
        "transaccion",
        "registrado_por",
        "clave_idempotencia",
        "revertido_en",
        "revertido_por",
        "motivo_reversa",
        "creado_en",
        "actualizado_en",
    )
    list_select_related = ("persona", "organizacion", "plan", "disciplina", "transaccion")
    actions = None


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
    list_display = ("fecha", "tipo", "categoria", "monto", "organizacion", "descripcion_corta")
    list_filter = ("organizacion", "tipo", "categoria", ("fecha", admin.DateFieldListFilter))
    search_fields = ("descripcion",)
    list_select_related = ("organizacion", "categoria")
    actions = None

    @admin.display(description="Descripcion")
    def descripcion_corta(self, obj):
        return (obj.descripcion[:80] + "...") if len(obj.descripcion) > 80 else obj.descripcion

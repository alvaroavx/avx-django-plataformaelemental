from django.contrib import admin
from django.db.models import Count

from .models import AttendanceConsumption, Category, DocumentoTributario, Payment, PaymentPlan, Transaction


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
        "documento_tributario",
        "creado_en",
    )
    list_filter = ("organizacion", "metodo_pago", "aplica_iva", ("fecha_pago", admin.DateFieldListFilter), ("creado_en", admin.DateFieldListFilter))
    search_fields = (
        "persona__nombres",
        "persona__apellidos",
        "persona__rut",
        "documento_tributario__folio",
        "numero_comprobante",
    )
    readonly_fields = ("monto_neto", "monto_iva", "monto_total", "creado_en", "actualizado_en")
    list_select_related = ("persona", "organizacion", "documento_tributario", "plan")
    actions = None


@admin.register(DocumentoTributario)
class DocumentoTributarioAdmin(admin.ModelAdmin):
    list_display = (
        "fecha_emision",
        "tipo_documento",
        "folio",
        "nombre_emisor",
        "nombre_receptor",
        "monto_total",
        "organizacion",
        "fuente",
    )
    list_filter = (
        "organizacion",
        "tipo_documento",
        "fuente",
        ("fecha_emision", admin.DateFieldListFilter),
    )
    search_fields = ("folio", "nombre_emisor", "nombre_receptor", "rut_emisor", "rut_receptor")
    readonly_fields = ("archivo_pdf", "archivo_xml", "metadata_extra", "creado_en", "actualizado_en")
    list_select_related = ("organizacion", "documento_relacionado", "persona_relacionada", "organizacion_relacionada")
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
    list_display = ("fecha", "tipo", "categoria", "monto", "organizacion", "descripcion_corta", "documentos_count")
    list_filter = ("organizacion", "tipo", "categoria", ("fecha", admin.DateFieldListFilter))
    search_fields = ("descripcion", "documentos_tributarios__folio")
    list_select_related = ("organizacion", "categoria")
    actions = None

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.select_related("organizacion", "categoria").annotate(
            documentos_count_admin=Count("documentos_tributarios", distinct=True)
        )

    @admin.display(description="Descripcion")
    def descripcion_corta(self, obj):
        return (obj.descripcion[:80] + "...") if len(obj.descripcion) > 80 else obj.descripcion

    @admin.display(description="Documentos", ordering="documentos_count_admin")
    def documentos_count(self, obj):
        return obj.documentos_count_admin

from django.contrib import admin

from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = (
        "fecha",
        "usuario",
        "accion",
        "dominio",
        "modelo",
        "objeto_id",
        "organizacion",
        "resumen_corto",
    )
    list_filter = ("fecha", "usuario", "dominio", "accion", "organizacion")
    search_fields = ("resumen", "modelo", "objeto_id")
    list_per_page = 50
    date_hierarchy = "fecha"
    actions = None
    readonly_fields = (
        "usuario",
        "fecha",
        "accion",
        "dominio",
        "modelo",
        "objeto_id",
        "organizacion",
        "resumen",
        "metadata",
    )

    def resumen_corto(self, obj):
        return obj.resumen[:80]

    resumen_corto.short_description = "Resumen"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_view_permission(self, request, obj=None):
        return bool(request.user and request.user.is_staff)

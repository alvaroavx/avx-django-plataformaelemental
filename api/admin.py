from django.contrib import admin

from .models import ApiAccessKey


@admin.register(ApiAccessKey)
class ApiAccessKeyAdmin(admin.ModelAdmin):
    list_display = ("nombre", "prefijo", "activa", "creada_en", "ultimo_uso_en")
    list_filter = ("activa",)
    search_fields = ("nombre", "prefijo", "descripcion")
    readonly_fields = ("prefijo", "hash_clave", "creada_en", "ultimo_uso_en")

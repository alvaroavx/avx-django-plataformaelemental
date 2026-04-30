from django.contrib import admin

from .models import (
    ConfiguracionMonitor,
    ConfiguracionSitio,
    DiscoverySitio,
    Proyecto,
    Sitio,
)


@admin.register(Proyecto)
class ProyectoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "organizacion", "activo", "actualizado_en")
    list_filter = ("activo", "organizacion")
    search_fields = ("nombre", "descripcion")


@admin.register(Sitio)
class SitioAdmin(admin.ModelAdmin):
    list_display = ("nombre", "dominio", "proyecto", "ultimo_estado", "ultimo_check_en", "activo")
    list_filter = ("ultimo_estado", "activo", "proyecto")
    search_fields = ("nombre", "url", "dominio")


@admin.register(ConfiguracionMonitor)
class ConfiguracionMonitorAdmin(admin.ModelAdmin):
    list_display = ("timeout_segundos", "frecuencia_minutos", "seguir_redirecciones", "actualizado_en")


@admin.register(ConfiguracionSitio)
class ConfiguracionSitioAdmin(admin.ModelAdmin):
    list_display = ("sitio", "timeout_segundos", "frecuencia_minutos", "seguir_redirecciones", "activo")
    list_filter = ("activo",)
    search_fields = ("sitio__nombre", "sitio__url")


@admin.register(DiscoverySitio)
class DiscoverySitioAdmin(admin.ModelAdmin):
    list_display = ("sitio", "estado_http", "ssl_valido", "tiempo_respuesta_ms", "creado_en")
    list_filter = ("ssl_valido", "estado_http")
    search_fields = ("sitio__nombre", "sitio__url", "titulo", "error")

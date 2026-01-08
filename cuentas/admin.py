from django.contrib import admin

from .models import Persona, Rol, PersonaRol


@admin.register(Persona)
class PersonaAdmin(admin.ModelAdmin):
    list_display = ("nombres", "apellidos", "email", "telefono", "activo", "creado_en", "user")
    search_fields = ("nombres", "apellidos", "email", "identificador")
    list_filter = ("activo", ("creado_en", admin.DateFieldListFilter))
    autocomplete_fields = ("user",)
    list_per_page = 25


@admin.register(Rol)
class RolAdmin(admin.ModelAdmin):
    list_display = ("nombre", "codigo", "creado_en")
    search_fields = ("nombre", "codigo")
    ordering = ("nombre",)


@admin.register(PersonaRol)
class PersonaRolAdmin(admin.ModelAdmin):
    list_display = ("persona", "rol", "organizacion", "activo", "asignado_en")
    list_filter = ("rol", "organizacion", "activo", ("asignado_en", admin.DateFieldListFilter))
    search_fields = ("persona__nombres", "persona__apellidos", "organizacion__nombre")
    autocomplete_fields = ("persona", "rol", "organizacion")
    list_select_related = ("persona", "rol", "organizacion")

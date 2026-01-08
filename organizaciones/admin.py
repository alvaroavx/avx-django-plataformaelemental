from django.contrib import admin

from .models import Organizacion


@admin.register(Organizacion)
class OrganizacionAdmin(admin.ModelAdmin):
    list_display = ("nombre", "rut", "email_contacto", "telefono_contacto", "creada_en")
    search_fields = ("nombre", "rut", "email_contacto")
    list_filter = (("creada_en", admin.DateFieldListFilter),)
    list_per_page = 25
    ordering = ("nombre",)

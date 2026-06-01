from django import forms
from django.contrib import admin, messages
from django.contrib.admin.widgets import FilteredSelectMultiple
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse

from .models import Organizacion, Persona, PersonaRol, Rol


class PersonaRolBulkForm(forms.ModelForm):
    personas = forms.ModelMultipleChoiceField(
        queryset=Persona.objects.all(),
        widget=FilteredSelectMultiple("Personas", is_stacked=False),
        help_text="Selecciona una o varias personas.",
    )

    class Meta:
        model = PersonaRol
        fields = ["personas", "rol", "organizacion", "activo"]

    def save_bulk(self):
        data = self.cleaned_data
        created = 0
        for persona in data["personas"]:
            obj, was_created = PersonaRol.objects.get_or_create(
                persona=persona,
                rol=data["rol"],
                organizacion=data["organizacion"],
                defaults={"activo": data.get("activo", True)},
            )
            if not was_created and obj.activo != data.get("activo", True):
                obj.activo = data.get("activo", True)
                obj.save(update_fields=["activo"])
            if was_created:
                created += 1
        return created


@admin.register(Organizacion)
class OrganizacionAdmin(admin.ModelAdmin):
    list_display = (
        "nombre",
        "rut",
        "tiene_logo",
        "es_exenta_iva",
        "email_contacto",
        "telefono_contacto",
        "creada_en",
    )
    search_fields = ("nombre", "rut", "email_contacto")
    list_filter = (("creada_en", admin.DateFieldListFilter),)
    readonly_fields = ("creada_en", "actualizada_en")
    list_per_page = 50
    ordering = ("nombre",)
    actions = None

    @admin.display(boolean=True, description="Logo")
    def tiene_logo(self, obj):
        return bool(obj.logo)


@admin.register(Persona)
class PersonaAdmin(admin.ModelAdmin):
    list_display = ("nombre_completo", "rut", "email", "telefono", "activo", "creado_en", "user")
    search_fields = ("nombres", "apellidos", "email", "telefono", "rut")
    list_filter = ("activo", "roles__organizacion", "roles__rol", ("creado_en", admin.DateFieldListFilter))
    readonly_fields = ("creado_en", "actualizado_en")
    autocomplete_fields = ("user",)
    list_select_related = ("user",)
    list_per_page = 50
    actions = None


@admin.register(Rol)
class RolAdmin(admin.ModelAdmin):
    list_display = ("nombre", "codigo", "creado_en")
    search_fields = ("nombre", "codigo")
    ordering = ("nombre",)


@admin.register(PersonaRol)
class PersonaRolAdmin(admin.ModelAdmin):
    list_display = ("persona", "organizacion", "rol", "activo", "valor_clase", "retencion_sii")
    list_filter = ("organizacion", "rol", "activo")
    search_fields = ("persona__nombres", "persona__apellidos", "persona__rut")
    autocomplete_fields = ("persona", "rol", "organizacion")
    list_select_related = ("persona", "rol", "organizacion")
    actions = None

    def get_form(self, request, obj=None, **kwargs):
        if obj is None:
            kwargs["form"] = PersonaRolBulkForm
        return super().get_form(request, obj, **kwargs)

    def add_view(self, request, form_url="", extra_context=None):
        if request.method == "POST":
            form = PersonaRolBulkForm(request.POST)
            if form.is_valid():
                created = form.save_bulk()
                self.message_user(
                    request,
                    f"Roles asignados: {created}.",
                    messages.SUCCESS,
                )
                return HttpResponseRedirect(reverse("admin:personas_personarol_changelist"))
        else:
            form = PersonaRolBulkForm(initial={"activo": True, "organizacion": Organizacion.objects.first()})

        fieldsets = [(None, {"fields": ("personas", "rol", "organizacion", "activo")})]
        admin_form = admin.helpers.AdminForm(
            form,
            fieldsets,
            self.get_prepopulated_fields(request),
            self.get_readonly_fields(request),
        )
        context = {
            **self.admin_site.each_context(request),
            "title": "Asignar rol a varias personas",
            "adminform": admin_form,
            "object_id": None,
            "original": None,
            "is_popup": False,
            "to_field": None,
            "media": self.media + form.media,
            "errors": admin.helpers.AdminErrorList(form, ()),
            "app_label": self.model._meta.app_label,
            "opts": self.model._meta,
            "add": True,
            "change": False,
            "save_as": self.save_as,
            "show_save": True,
            "has_view_permission": self.has_view_permission(request),
            "has_add_permission": self.has_add_permission(request),
            "has_change_permission": self.has_change_permission(request),
            "has_delete_permission": self.has_delete_permission(request),
            "has_editable_inline_admin_formsets": False,
            "form_url": form_url,
        }
        if extra_context:
            context.update(extra_context)
        return render(request, "admin/change_form.html", context)

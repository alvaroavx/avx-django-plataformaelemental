from django import forms
from django.contrib import admin, messages
from django.contrib.admin.widgets import FilteredSelectMultiple
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse

from .models import (
    Asistencia,
    BloqueHorario,
    Disciplina,
    Organizacion,
    Persona,
    PersonaRol,
    Rol,
    SesionClase,
)


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
    list_display = ("nombre", "rut", "email_contacto", "telefono_contacto", "creada_en")
    search_fields = ("nombre", "rut", "email_contacto")
    list_filter = (("creada_en", admin.DateFieldListFilter),)
    list_per_page = 25
    ordering = ("nombre",)


@admin.register(Persona)
class PersonaAdmin(admin.ModelAdmin):
    list_display = ("nombres", "apellidos", "email", "telefono", "activo", "creado_en", "user")
    search_fields = ("nombres", "apellidos", "email", "telefono", "identificador")
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
                return HttpResponseRedirect(reverse("admin:database_personarol_changelist"))
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


@admin.register(Disciplina)
class DisciplinaAdmin(admin.ModelAdmin):
    list_display = ("nombre", "organizacion", "nivel", "activa", "creada_en")
    list_filter = ("organizacion", "activa", "nivel")
    search_fields = ("nombre", "nivel", "descripcion")
    list_per_page = 25


@admin.register(BloqueHorario)
class BloqueHorarioAdmin(admin.ModelAdmin):
    list_display = ("nombre", "organizacion", "dia_semana_display", "hora_inicio", "hora_fin", "disciplina")
    list_filter = ("organizacion", "dia_semana")
    search_fields = ("nombre", "disciplina__nombre")
    autocomplete_fields = ("disciplina",)
    list_select_related = ("organizacion", "disciplina")

    @admin.display(description="Dia")
    def dia_semana_display(self, obj):
        return obj.get_dia_semana_display()


@admin.register(SesionClase)
class SesionClaseAdmin(admin.ModelAdmin):
    list_display = ("disciplina", "fecha", "estado", "profesores_display", "cupo_maximo")
    list_filter = ("estado", "disciplina", ("fecha", admin.DateFieldListFilter))
    search_fields = ("disciplina__nombre", "profesores__nombres", "profesores__apellidos", "notas")
    autocomplete_fields = ("disciplina", "bloque", "profesores")
    list_select_related = ("disciplina",)
    date_hierarchy = "fecha"

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        if db_field.name == "profesores":
            kwargs["queryset"] = (
                Persona.objects.filter(roles__rol__codigo="PROFESOR")
                .distinct()
                .order_by("apellidos", "nombres")
            )
        return super().formfield_for_manytomany(db_field, request, **kwargs)

    def profesores_display(self, obj):
        return obj.profesores_resumen or "-"

    profesores_display.short_description = "Profesores"


@admin.register(Asistencia)
class AsistenciaAdmin(admin.ModelAdmin):
    list_display = ("sesion", "persona", "estado", "registrada_en")
    list_filter = (
        "estado",
        ("registrada_en", admin.DateFieldListFilter),
        "sesion__disciplina",
    )
    search_fields = ("persona__nombres", "persona__apellidos", "sesion__disciplina__nombre")
    autocomplete_fields = ("sesion", "persona")
    list_select_related = ("sesion", "persona")
    date_hierarchy = "registrada_en"

from django import forms
from django.core.exceptions import ValidationError

from .models import ConfiguracionMonitor, ConfiguracionSitio, Proyecto, Sitio
from .services.urls import normalizar_url


class SitioCreateForm(forms.Form):
    proyecto = forms.ModelChoiceField(
        queryset=Proyecto.objects.filter(activo=True),
        required=False,
        label="Proyecto existente",
        empty_label="Seleccionar proyecto",
    )
    proyecto_nombre = forms.CharField(
        required=False,
        max_length=200,
        label="Nuevo proyecto",
        help_text="Usa este campo si el sitio no pertenece a un proyecto existente.",
    )
    nombre = forms.CharField(required=False, max_length=200, label="Nombre del sitio")
    url = forms.CharField(label="URL")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            css_class = widget.attrs.get("class", "")
            widget.attrs["class"] = f"{css_class} form-control".strip()
        self.fields["proyecto"].widget.attrs["class"] = "form-select"
        self.fields["url"].widget.attrs["placeholder"] = "https://ejemplo.cl"

    def clean_url(self):
        return normalizar_url(self.cleaned_data["url"])

    def clean(self):
        cleaned_data = super().clean()
        proyecto = cleaned_data.get("proyecto")
        proyecto_nombre = (cleaned_data.get("proyecto_nombre") or "").strip()
        if not proyecto and not proyecto_nombre:
            self.add_error("proyecto_nombre", "Selecciona un proyecto o crea uno nuevo.")
        return cleaned_data

    def crear_sitio(self) -> Sitio:
        proyecto = self.cleaned_data["proyecto"]
        if not proyecto:
            proyecto = Proyecto.objects.create(nombre=self.cleaned_data["proyecto_nombre"].strip())

        url = self.cleaned_data["url"]
        existente = Sitio.objects.filter(proyecto=proyecto, url=url).first()
        if existente:
            raise ValidationError("Este sitio ya existe en el proyecto seleccionado.")

        nombre = self.cleaned_data.get("nombre") or proyecto.nombre
        return Sitio.objects.create(proyecto=proyecto, nombre=nombre.strip(), url=url)


class ConfiguracionMonitorForm(forms.ModelForm):
    class Meta:
        model = ConfiguracionMonitor
        fields = [
            "timeout_segundos",
            "frecuencia_minutos",
            "seguir_redirecciones",
            "user_agent",
        ]
        widgets = {
            "seguir_redirecciones": forms.CheckboxInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if name == "seguir_redirecciones":
                field.widget.attrs["class"] = "form-check-input"
            else:
                field.widget.attrs["class"] = "form-control"


class NullableBooleanChoiceField(forms.TypedChoiceField):
    def prepare_value(self, value):
        if value is True:
            return "true"
        if value is False:
            return "false"
        return ""


class ConfiguracionSitioForm(forms.ModelForm):
    seguir_redirecciones = NullableBooleanChoiceField(
        choices=[
            ("", "Usar configuracion global"),
            ("true", "Si"),
            ("false", "No"),
        ],
        coerce=lambda value: None if value == "" else value == "true",
        empty_value=None,
        required=False,
        label="Seguir redirecciones",
    )

    class Meta:
        model = ConfiguracionSitio
        fields = [
            "timeout_segundos",
            "frecuencia_minutos",
            "seguir_redirecciones",
            "activo",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if name == "activo":
                field.widget.attrs["class"] = "form-check-input"
            elif name == "seguir_redirecciones":
                field.widget.attrs["class"] = "form-select"
            else:
                field.widget.attrs["class"] = "form-control"

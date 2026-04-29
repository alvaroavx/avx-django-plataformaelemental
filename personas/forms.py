from django import forms

from .models import Organizacion, Persona, PersonaRol, Rol
from .validators import formatear_rut_chileno


class OrganizacionCRMForm(forms.ModelForm):
    class Meta:
        model = Organizacion
        fields = [
            "nombre",
            "razon_social",
            "rut",
            "es_exenta_iva",
            "email_contacto",
            "telefono_contacto",
            "sitio_web",
            "direccion",
        ]
        widgets = {
            "direccion": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for _, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs["class"] = "form-check-input"
            else:
                css_class = field.widget.attrs.get("class", "")
                field.widget.attrs["class"] = f"{css_class} form-control".strip()


class PersonaCRMForm(forms.ModelForm):
    class Meta:
        model = Persona
        fields = [
            "nombres",
            "apellidos",
            "email",
            "telefono",
            "rut",
            "fecha_nacimiento",
            "activo",
            "user",
        ]
        widgets = {
            "fecha_nacimiento": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for _, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs["class"] = "form-check-input"
            else:
                css_class = field.widget.attrs.get("class", "")
                field.widget.attrs["class"] = f"{css_class} form-control".strip()
        self.fields["rut"].widget.attrs["placeholder"] = "12.345.678-5"

    def clean_rut(self):
        return formatear_rut_chileno(self.cleaned_data.get("rut", ""))


class PersonaRolCRMForm(forms.Form):
    rol = forms.ModelChoiceField(
        queryset=Rol.objects.order_by("nombre"),
        required=False,
    )
    organizacion = forms.ModelChoiceField(
        queryset=Organizacion.objects.order_by("nombre"),
        required=False,
    )
    valor_clase = forms.DecimalField(
        required=False,
        min_value=0,
        decimal_places=2,
        max_digits=12,
        widget=forms.NumberInput(attrs={"step": "1", "min": "0"}),
    )
    retencion_sii = forms.DecimalField(
        required=False,
        min_value=0,
        decimal_places=2,
        max_digits=5,
        widget=forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for _, field in self.fields.items():
            css_class = field.widget.attrs.get("class", "")
            if isinstance(field, forms.ModelChoiceField):
                field.widget.attrs["class"] = f"{css_class} form-select".strip()
            else:
                field.widget.attrs["class"] = f"{css_class} form-control".strip()
        self.fields["valor_clase"].widget.attrs["placeholder"] = "Opcional"
        self.fields["retencion_sii"].widget.attrs["placeholder"] = "Opcional"

    def clean(self):
        cleaned = super().clean()
        rol = cleaned.get("rol")
        organizacion = cleaned.get("organizacion")
        if bool(rol) != bool(organizacion):
            raise forms.ValidationError("Debes seleccionar rol y organizacion en conjunto.")
        if rol and rol.codigo != "PROFESOR":
            cleaned["valor_clase"] = None
            cleaned["retencion_sii"] = None
        return cleaned

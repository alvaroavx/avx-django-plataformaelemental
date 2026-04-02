from django import forms

from .models import Organizacion, Persona, PersonaRol, Rol


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
            "identificador",
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


class PersonaRolCRMForm(forms.Form):
    rol = forms.ModelChoiceField(
        queryset=Rol.objects.order_by("nombre"),
        required=False,
    )
    organizacion = forms.ModelChoiceField(
        queryset=Organizacion.objects.order_by("nombre"),
        required=False,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for _, field in self.fields.items():
            css_class = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = f"{css_class} form-select".strip()

    def clean(self):
        cleaned = super().clean()
        rol = cleaned.get("rol")
        organizacion = cleaned.get("organizacion")
        if bool(rol) != bool(organizacion):
            raise forms.ValidationError("Debes seleccionar rol y organizacion en conjunto.")
        return cleaned

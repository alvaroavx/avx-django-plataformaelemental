from django import forms

from django.contrib.auth import get_user_model

from .models import Organizacion, Persona, PersonaRol, Rol, SolicitudAcceso
from .utils import normalizar_telefono, tiene_identidad_minima
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
        rut = formatear_rut_chileno(self.cleaned_data.get("rut", ""))
        if rut and Persona.objects.filter(rut__iexact=rut).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Ya existe una persona con este RUT.")
        return rut

    def clean_telefono(self):
        return normalizar_telefono(self.cleaned_data.get("telefono", ""))

    def clean(self):
        cleaned = super().clean()
        if not tiene_identidad_minima(
            rut=cleaned.get("rut", ""),
            email=cleaned.get("email", ""),
            telefono=cleaned.get("telefono", ""),
        ):
            raise forms.ValidationError("Debes registrar al menos RUT, email o telefono.")
        return cleaned


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

    def __init__(self, *args, organizaciones=None, **kwargs):
        super().__init__(*args, **kwargs)
        if organizaciones is not None:
            self.fields["organizacion"].queryset = organizaciones
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


class ResolverSolicitudAccesoForm(forms.Form):
    tipo_resolucion = forms.ChoiceField(choices=SolicitudAcceso.TipoResolucion.choices, label="Tipo de resolución")
    usuario = forms.ModelChoiceField(queryset=get_user_model().objects.none(), required=False)
    persona = forms.ModelChoiceField(queryset=Persona.objects.none(), required=False)
    organizacion = forms.ModelChoiceField(queryset=Organizacion.objects.order_by("nombre"), label="Organización")
    rol = forms.ModelChoiceField(queryset=Rol.objects.order_by("nombre"), label="Rol")
    nombres = forms.CharField(max_length=150, required=False, label="Nombres para la nueva Persona")
    apellidos = forms.CharField(max_length=150, required=False, label="Apellidos para la nueva Persona")
    nota_interna = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}), required=False, label="Nota interna")
    confirmar_correo_distinto = forms.BooleanField(required=False, label="Confirmo que revisé la diferencia de correo")

    def __init__(self, *args, usuarios=None, personas=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["usuario"].queryset = usuarios if usuarios is not None else get_user_model().objects.none()
        self.fields["persona"].queryset = personas if personas is not None else Persona.objects.none()
        for nombre, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs["class"] = "form-check-input"
            elif isinstance(field, forms.ModelChoiceField):
                field.widget.attrs["class"] = "form-select"
            else:
                field.widget.attrs["class"] = "form-control"
        self.fields["usuario"].label = "Usuario existente"
        self.fields["persona"].label = "Persona existente sin User"

    def clean(self):
        cleaned = super().clean()
        tipo = cleaned.get("tipo_resolucion")
        if tipo == SolicitudAcceso.TipoResolucion.USUARIO_EXISTENTE and not cleaned.get("usuario"):
            self.add_error("usuario", "Busca y selecciona un usuario activo.")
        if tipo == SolicitudAcceso.TipoResolucion.PERSONA_EXISTENTE and not cleaned.get("persona"):
            self.add_error("persona", "Busca y selecciona una Persona sin User.")
        if tipo == SolicitudAcceso.TipoResolucion.USUARIO_NUEVO:
            if not (cleaned.get("nombres") or "").strip():
                self.add_error("nombres", "Indica los nombres de la nueva Persona.")
            if not (cleaned.get("apellidos") or "").strip():
                self.add_error("apellidos", "Indica los apellidos de la nueva Persona.")
        return cleaned

from django import forms
from django.contrib.auth.forms import AuthenticationForm

from personas.models import Persona
from personas.utils import normalizar_telefono

from .models import BloqueHorario, Disciplina, SesionClase
from .utils import disciplinas_vigentes_qs, profesores_vigentes_qs


class DisciplinaForm(forms.ModelForm):
    class Meta:
        model = Disciplina
        fields = ["organizacion", "nombre", "nivel", "badge_color", "descripcion", "activa"]
        widgets = {
            "organizacion": forms.Select(attrs={"class": "form-select"}),
            "nombre": forms.TextInput(attrs={"class": "form-control", "placeholder": "Nombre de disciplina"}),
            "nivel": forms.TextInput(attrs={"class": "form-control", "placeholder": "Nivel (opcional)"}),
            "badge_color": forms.Select(attrs={"class": "form-select"}),
            "descripcion": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 4,
                    "placeholder": "Descripción breve de la disciplina",
                }
            ),
            "activa": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(self, *args, organizaciones=None, **kwargs):
        super().__init__(*args, **kwargs)
        if organizaciones is not None:
            self.fields["organizacion"].queryset = organizaciones


class SesionBasicaForm(forms.Form):
    disciplina = forms.ModelChoiceField(
        queryset=Disciplina.objects.none(),
        required=True,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    fecha = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
    )
    profesores = forms.ModelMultipleChoiceField(
        queryset=Persona.objects.none(),
        required=False,
        widget=forms.SelectMultiple(attrs={"id": "id_profesores_basica", "class": "form-select"}),
    )

    def __init__(self, *args, organizacion=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["disciplina"].queryset = disciplinas_vigentes_qs(organizacion=organizacion)
        self.fields["profesores"].queryset = profesores_vigentes_qs(organizacion=organizacion)


class SesionesMasivasForm(forms.Form):
    disciplina = forms.ModelChoiceField(
        queryset=Disciplina.objects.none(),
        required=True,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    dias_semana = forms.MultipleChoiceField(
        choices=BloqueHorario.Dia.choices,
        required=True,
        widget=forms.CheckboxSelectMultiple(attrs={"class": "form-check-input"}),
        label="Dias de la semana",
    )
    max_sesiones = forms.IntegerField(
        min_value=1,
        required=False,
        label="Maximo de sesiones",
        help_text="Dejar vacio para crear todas las fechas del mes seleccionado.",
        widget=forms.NumberInput(attrs={"class": "form-control", "placeholder": "Ej: 1"}),
    )
    profesores = forms.ModelMultipleChoiceField(
        queryset=Persona.objects.none(),
        required=False,
        widget=forms.SelectMultiple(attrs={"id": "id_profesores_masivo", "class": "form-select"}),
    )

    def __init__(self, *args, organizacion=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["disciplina"].queryset = disciplinas_vigentes_qs(organizacion=organizacion)
        self.fields["profesores"].queryset = profesores_vigentes_qs(organizacion=organizacion)

    def clean_dias_semana(self):
        return [int(dia) for dia in self.cleaned_data["dias_semana"]]


class AsistenciaMasivaForm(forms.Form):
    sesion_id = forms.ModelChoiceField(
        queryset=SesionClase.objects.none(),
        required=True,
        label="Sesión",
        widget=forms.Select(attrs={"class": "form-select js-sesion-asistentes-select"}),
    )
    estudiantes = forms.ModelMultipleChoiceField(
        queryset=Persona.objects.none(),
        required=False,
        widget=forms.SelectMultiple(attrs={"id": "id_estudiantes", "class": "form-select"}),
    )

    def __init__(self, *args, sesiones_queryset=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["sesion_id"].queryset = sesiones_queryset or SesionClase.objects.none()


class PersonaRapidaForm(forms.Form):
    nombres = forms.CharField(
        max_length=150,
        required=True,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Nombres"}),
    )
    apellidos = forms.CharField(
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Apellidos"}),
    )
    telefono = forms.CharField(
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Telefono"}),
    )

    def clean_telefono(self):
        return normalizar_telefono(self.cleaned_data.get("telefono", ""))

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("telefono"):
            raise forms.ValidationError("Debes ingresar al menos un telefono para crear una persona.")
        return cleaned


class CustomLoginForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].widget.attrs.update({"class": "form-control", "placeholder": "usuario"})
        self.fields["password"].widget.attrs.update({"class": "form-control", "placeholder": "********"})

from django import forms
from django.contrib.auth.forms import AuthenticationForm

from personas.models import Persona

from .models import Disciplina


class DisciplinaForm(forms.ModelForm):
    class Meta:
        model = Disciplina
        fields = ["organizacion", "nombre", "nivel", "descripcion", "activa"]
        widgets = {
            "organizacion": forms.Select(attrs={"class": "form-select"}),
            "nombre": forms.TextInput(attrs={"class": "form-control", "placeholder": "Nombre de disciplina"}),
            "nivel": forms.TextInput(attrs={"class": "form-control", "placeholder": "Nivel (opcional)"}),
            "descripcion": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 4,
                    "placeholder": "Descripción breve de la disciplina",
                }
            ),
            "activa": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }


class SesionBasicaForm(forms.Form):
    disciplina = forms.ModelChoiceField(
        queryset=Disciplina.objects.all(),
        required=True,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    fecha = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
    )
    profesores = forms.ModelMultipleChoiceField(
        queryset=Persona.objects.filter(roles__rol__codigo="PROFESOR").distinct().order_by("apellidos", "nombres"),
        required=False,
        widget=forms.SelectMultiple(attrs={"id": "id_profesores_basica", "class": "form-select"}),
    )


class AsistenciaMasivaForm(forms.Form):
    sesion_id = forms.IntegerField(widget=forms.HiddenInput)
    estudiantes = forms.ModelMultipleChoiceField(
        queryset=Persona.objects.none(),
        required=False,
        widget=forms.SelectMultiple(attrs={"id": "id_estudiantes", "class": "form-select"}),
    )


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


class CustomLoginForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].widget.attrs.update({"class": "form-control", "placeholder": "usuario"})
        self.fields["password"].widget.attrs.update({"class": "form-control", "placeholder": "********"})

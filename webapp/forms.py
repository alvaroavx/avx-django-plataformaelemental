from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.utils import timezone

from academia.models import Disciplina, SesionClase
from asistencias.models import Asistencia
from cobros.models import Pago
from cuentas.models import Persona


class SesionRapidaForm(forms.Form):
    disciplina = forms.ModelChoiceField(queryset=Disciplina.objects.all(), required=True)
    profesores = forms.ModelMultipleChoiceField(
        queryset=Persona.objects.filter(roles__rol__codigo="PROFESOR").distinct().order_by("apellidos", "nombres"),
        required=False,
        widget=forms.SelectMultiple(attrs={"id": "id_profesores", "class": "form-select"}),
    )
    fecha = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    cupo_maximo = forms.IntegerField(required=False, min_value=1)
    notas = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}), required=False)


class SesionBasicaForm(forms.Form):
    disciplina = forms.ModelChoiceField(queryset=Disciplina.objects.all(), required=True)
    fecha = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
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
    nombres = forms.CharField(max_length=150, required=True)
    apellidos = forms.CharField(max_length=150, required=False)
    telefono = forms.CharField(max_length=50, required=False)


class AsistenciaRapidaForm(forms.ModelForm):
    class Meta:
        model = Asistencia
        fields = ["persona", "estado"]


class AsistenciaSesionForm(forms.ModelForm):
    sesion = forms.ModelChoiceField(queryset=SesionClase.objects.all(), required=True)

    class Meta:
        model = Asistencia
        fields = ["sesion", "persona", "estado"]


class PagoRapidoForm(forms.ModelForm):
    class Meta:
        model = Pago
        fields = ["persona", "fecha_pago", "monto", "metodo", "tipo", "sesion"]
        widgets = {
            "fecha_pago": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["fecha_pago"].required = False
        self.fields["fecha_pago"].initial = timezone.localdate()
        self.fields["persona"].required = True

    def clean_fecha_pago(self):
        fecha = self.cleaned_data.get("fecha_pago")
        return fecha or timezone.localdate()


class CustomLoginForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].widget.attrs.update(
            {"class": "form-control", "placeholder": "usuario"}
        )
        self.fields["password"].widget.attrs.update(
            {"class": "form-control", "placeholder": "••••••••"}
        )

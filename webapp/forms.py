from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.utils import timezone

from academia.models import Disciplina
from cobros.models import Pago, Plan
from cuentas.models import Persona


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


class CustomLoginForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].widget.attrs.update(
            {"class": "form-control", "placeholder": "usuario"}
        )
        self.fields["password"].widget.attrs.update(
            {"class": "form-control", "placeholder": "••••••••"}
        )




class PagoPersonaForm(forms.ModelForm):
    fecha_pago = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        input_formats=["%Y-%m-%d"],
    )

    class Meta:
        model = Pago
        fields = ["tipo", "plan", "fecha_pago", "monto", "metodo", "referencia", "clases_total"]

    def __init__(self, *args, **kwargs):
        plan_queryset = kwargs.pop("plan_queryset", Plan.objects.filter(activo=True))
        super().__init__(*args, **kwargs)
        self.fields["tipo"].widget.attrs.update({"class": "form-select"})
        self.fields["tipo"].initial = Pago.Tipo.PLAN
        self.fields["plan"].queryset = plan_queryset
        self.fields["plan"].required = False
        self.fields["plan"].widget.attrs.update({"class": "form-select"})
        self.fields["fecha_pago"].widget.attrs.update({"class": "form-control"})
        self.fields["monto"].widget.attrs.update({"class": "form-control"})
        self.fields["metodo"].widget.attrs.update({"class": "form-select"})
        self.fields["referencia"].widget.attrs.update({"class": "form-control"})
        self.fields["clases_total"].widget.attrs.update({"class": "form-control"})
        self.fields["fecha_pago"].required = False
        self.fields["fecha_pago"].initial = timezone.localdate()

    def clean_fecha_pago(self):
        fecha = self.cleaned_data.get("fecha_pago")
        return fecha or timezone.localdate()

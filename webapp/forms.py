from django import forms
from django.utils import timezone

from academia.models import Disciplina, SesionClase
from asistencias.models import Asistencia
from cobros.models import Pago
from cuentas.models import Persona


class SesionRapidaForm(forms.Form):
    disciplina = forms.ModelChoiceField(queryset=Disciplina.objects.all(), required=False)
    disciplina_nombre = forms.CharField(max_length=150, required=False)
    profesor = forms.ModelChoiceField(queryset=Persona.objects.all(), required=False)
    profesores = forms.ModelMultipleChoiceField(queryset=Persona.objects.all(), required=False)
    fecha = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    cupo_maximo = forms.IntegerField(required=False, min_value=1)
    notas = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}), required=False)


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
        fields = ["persona", "fecha_pago", "monto", "metodo"]
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

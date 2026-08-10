import json
import uuid

from django import forms
from django.utils import timezone

from finanzas.models import Payment, PaymentPlan
from personas.models import Persona
from personas.utils import normalizar_telefono

from .models import Disciplina


class SesionProfesorForm(forms.Form):
    disciplina = forms.ModelChoiceField(queryset=Disciplina.objects.none(), label="Clase")
    fecha = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))

    def __init__(self, *args, disciplinas=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["disciplina"].queryset = disciplinas or Disciplina.objects.none()
        self.initial.setdefault("fecha", timezone.localdate())

    def clean_fecha(self):
        fecha = self.cleaned_data["fecha"]
        if fecha < timezone.localdate():
            raise forms.ValidationError("Selecciona hoy o una fecha futura.")
        return fecha


class AlumnoProfesorForm(forms.Form):
    disciplina = forms.ModelChoiceField(queryset=Disciplina.objects.none(), label="Clase")
    nombres = forms.CharField(max_length=150)
    apellidos = forms.CharField(max_length=150, required=False)
    email = forms.EmailField(required=False)
    telefono = forms.CharField(max_length=50, required=False)

    def __init__(self, *args, disciplinas=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["disciplina"].queryset = disciplinas or Disciplina.objects.none()

    def clean_telefono(self):
        return normalizar_telefono(self.cleaned_data.get("telefono", ""))

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("telefono") and not cleaned.get("email"):
            raise forms.ValidationError("Ingresa al menos un teléfono o un correo válido.")
        email = cleaned.get("email")
        if email and Persona.objects.filter(email__iexact=email).exists():
            self.add_error("email", "Ya existe una persona con este correo.")
        return cleaned


class PagoProfesorForm(forms.Form):
    disciplina = forms.ModelChoiceField(queryset=Disciplina.objects.none(), label="Clase")
    persona = forms.ModelChoiceField(queryset=Persona.objects.none(), label="Alumno")
    plan = forms.ModelChoiceField(queryset=PaymentPlan.objects.none(), required=False)
    fecha_pago = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    metodo_pago = forms.ChoiceField(choices=Payment.Metodo.choices)
    numero_comprobante = forms.CharField(max_length=100, required=False)
    monto = forms.DecimalField(max_digits=12, decimal_places=0, min_value=1, label="Monto CLP")
    clases_asignadas = forms.IntegerField(min_value=0, initial=0)
    glosa = forms.CharField(widget=forms.Textarea(attrs={"rows": 2}), required=True)
    respaldo = forms.FileField(required=False)
    clave_idempotencia = forms.CharField(widget=forms.HiddenInput, required=False)

    def __init__(self, *args, disciplinas=None, alumnos=None, planes=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["disciplina"].queryset = disciplinas or Disciplina.objects.none()
        self.fields["persona"].queryset = alumnos or Persona.objects.none()
        self.fields["plan"].queryset = planes or PaymentPlan.objects.none()
        self.initial.setdefault("fecha_pago", timezone.localdate())
        self.initial.setdefault("clave_idempotencia", uuid.uuid4().hex)

    def clean(self):
        cleaned = super().clean()
        disciplina = cleaned.get("disciplina")
        persona = cleaned.get("persona")
        plan = cleaned.get("plan")
        if disciplina and persona and not disciplina.alumnos_asignados.operativas().filter(
            alumno=persona,
        ).exists():
            self.add_error("persona", "El alumno no está asociado a la clase seleccionada.")
        if plan and disciplina and plan.organizacion_id != disciplina.organizacion_id:
            self.add_error("plan", "El plan no pertenece a la organización de la clase.")
        if cleaned.get("metodo_pago") == Payment.Metodo.TRANSFERENCIA and not (
            cleaned.get("numero_comprobante") or ""
        ).strip():
            self.add_error("numero_comprobante", "El comprobante es obligatorio para transferencias.")
        return cleaned


class PagoMasivoProfesorForm(forms.Form):
    disciplina = forms.ModelChoiceField(queryset=Disciplina.objects.none(), label="Clase")
    personas_seleccionadas = forms.CharField(widget=forms.HiddenInput)
    fecha_pago = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    plan = forms.ModelChoiceField(queryset=PaymentPlan.objects.none(), required=False)
    metodo_pago = forms.ChoiceField(choices=Payment.Metodo.choices)
    numero_comprobante = forms.CharField(max_length=100, required=False)
    monto = forms.DecimalField(max_digits=12, decimal_places=0, min_value=1, label="Monto CLP")
    clases_asignadas = forms.IntegerField(min_value=0, initial=0)
    respaldo = forms.FileField(required=False)
    glosa = forms.CharField(widget=forms.Textarea(attrs={"rows": 2}), required=True)
    filas_json = forms.CharField(widget=forms.HiddenInput, required=False)
    clave_idempotencia = forms.CharField(widget=forms.HiddenInput)

    def __init__(self, *args, disciplinas=None, alumnos=None, planes=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.disciplinas = disciplinas or Disciplina.objects.none()
        self.alumnos = alumnos or Persona.objects.none()
        self.fields["disciplina"].queryset = self.disciplinas
        self.fields["plan"].queryset = planes or PaymentPlan.objects.none()
        self.initial.setdefault("fecha_pago", timezone.localdate())
        self.initial.setdefault("clave_idempotencia", uuid.uuid4().hex)

    def clean_personas_seleccionadas(self):
        raw = self.cleaned_data["personas_seleccionadas"]
        try:
            ids = [int(item) for item in raw.split(",") if item.strip()]
        except ValueError as exc:
            raise forms.ValidationError("La selección no es válida.") from exc
        if len(ids) < 10 or len(ids) > 20:
            raise forms.ValidationError("Selecciona entre 10 y 20 alumnos.")
        if len(ids) != len(set(ids)):
            raise forms.ValidationError("No puedes seleccionar dos veces al mismo alumno.")
        return ids

    def clean_filas_json(self):
        try:
            value = json.loads(self.cleaned_data.get("filas_json") or "{}")
        except json.JSONDecodeError as exc:
            raise forms.ValidationError("Los ajustes por fila no son válidos.") from exc
        if not isinstance(value, dict):
            raise forms.ValidationError("Los ajustes por fila no son válidos.")
        return value

    def clean(self):
        cleaned = super().clean()
        disciplina = cleaned.get("disciplina")
        ids = cleaned.get("personas_seleccionadas") or []
        if disciplina:
            elegibles = set(
                disciplina.alumnos_asignados.operativas().filter(alumno_id__in=ids).values_list(
                    "alumno_id", flat=True
                )
            )
            if elegibles != set(ids):
                self.add_error("personas_seleccionadas", "Uno o más alumnos están fuera de tu clase.")
        plan = cleaned.get("plan")
        if plan and disciplina and plan.organizacion_id != disciplina.organizacion_id:
            self.add_error("plan", "El plan no pertenece a la organización de la clase.")
        if cleaned.get("metodo_pago") == Payment.Metodo.TRANSFERENCIA and not (
            cleaned.get("numero_comprobante") or ""
        ).strip():
            self.add_error("numero_comprobante", "El comprobante es obligatorio para transferencias.")
        return cleaned

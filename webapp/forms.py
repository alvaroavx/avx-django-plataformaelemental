from django import forms

from academia.models import BloqueHorario, Disciplina, SesionClase
from asistencias.models import Asistencia
from cobros.models import ConvenioIntercambio, Pago, Plan, Suscripcion
from cuentas.models import Persona, Rol
from finanzas.models import LiquidacionProfesor, MovimientoCaja


class DisciplinaForm(forms.ModelForm):
    class Meta:
        model = Disciplina
        fields = ["organizacion", "nombre", "descripcion", "nivel", "activa"]


class BloqueHorarioForm(forms.ModelForm):
    class Meta:
        model = BloqueHorario
        fields = ["organizacion", "nombre", "dia_semana", "hora_inicio", "hora_fin", "disciplina"]


class SesionClaseForm(forms.ModelForm):
    class Meta:
        model = SesionClase
        fields = [
            "disciplina",
            "bloque",
            "profesor",
            "fecha",
            "estado",
            "cupo_maximo",
            "notas",
        ]
        widgets = {
            "fecha": forms.DateInput(attrs={"type": "date"}),
        }


class PersonaForm(forms.ModelForm):
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
        ]
        widgets = {
            "fecha_nacimiento": forms.DateInput(attrs={"type": "date"}),
        }


class PersonaRolForm(forms.ModelForm):
    class Meta:
        model = Rol
        fields = ["nombre", "codigo", "descripcion"]


class AsistenciaForm(forms.ModelForm):
    class Meta:
        model = Asistencia
        fields = ["persona", "estado", "convenio"]


class PlanForm(forms.ModelForm):
    class Meta:
        model = Plan
        fields = ["organizacion", "nombre", "descripcion", "precio", "duracion_dias", "clases_por_semana", "activo"]


class SuscripcionForm(forms.ModelForm):
    class Meta:
        model = Suscripcion
        fields = ["persona", "plan", "fecha_inicio", "fecha_fin", "estado", "notas", "convenios"]
        widgets = {
            "fecha_inicio": forms.DateInput(attrs={"type": "date"}),
            "fecha_fin": forms.DateInput(attrs={"type": "date"}),
        }


class ConvenioForm(forms.ModelForm):
    class Meta:
        model = ConvenioIntercambio
        fields = [
            "organizacion",
            "nombre",
            "descripcion",
            "descuento_porcentaje",
            "vigente_desde",
            "vigente_hasta",
            "activo",
        ]
        widgets = {
            "vigente_desde": forms.DateInput(attrs={"type": "date"}),
            "vigente_hasta": forms.DateInput(attrs={"type": "date"}),
        }


class PagoForm(forms.ModelForm):
    class Meta:
        model = Pago
        fields = ["persona", "suscripcion", "documento", "fecha_pago", "monto", "metodo", "referencia", "comprobante"]
        widgets = {
            "fecha_pago": forms.DateInput(attrs={"type": "date"}),
        }


class LiquidacionForm(forms.ModelForm):
    class Meta:
        model = LiquidacionProfesor
        fields = ["organizacion", "profesor", "periodo_inicio", "periodo_fin", "observaciones"]
        widgets = {
            "periodo_inicio": forms.DateInput(attrs={"type": "date"}),
            "periodo_fin": forms.DateInput(attrs={"type": "date"}),
        }


class MovimientoCajaForm(forms.ModelForm):
    class Meta:
        model = MovimientoCaja
        fields = ["organizacion", "tipo", "fecha", "monto_total", "afecta_iva", "categoria", "glosa"]
        widgets = {
            "fecha": forms.DateInput(attrs={"type": "date"}),
        }

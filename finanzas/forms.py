import json

from django import forms
from django.db.models import Q
from django.utils import timezone

from personas.models import Organizacion, Persona, PersonaRol

from .models import Category, Payment, PaymentPlan, Transaction


class PersonaOrganizacionSelect(forms.Select):
    def __init__(self, *args, persona_orgs=None, **kwargs):
        self.persona_orgs = persona_orgs or {}
        super().__init__(*args, **kwargs)

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex=subindex, attrs=attrs)
        raw_value = getattr(value, "value", value)
        try:
            persona_id = int(raw_value) if raw_value is not None and raw_value != "" else None
        except (TypeError, ValueError):
            persona_id = None
        if persona_id is not None:
            orgs = self.persona_orgs.get(persona_id, [])
            if orgs:
                option["attrs"]["data-orgs"] = ",".join(str(org_id) for org_id in orgs)
        return option


class OrganizacionIvaSelect(forms.Select):
    def __init__(self, *args, organizaciones_iva=None, **kwargs):
        self.organizaciones_iva = organizaciones_iva or {}
        super().__init__(*args, **kwargs)

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex=subindex, attrs=attrs)
        raw_value = getattr(value, "value", value)
        try:
            organizacion_id = int(raw_value) if raw_value is not None and raw_value != "" else None
        except (TypeError, ValueError):
            organizacion_id = None
        if organizacion_id is not None:
            es_exenta_iva = self.organizaciones_iva.get(organizacion_id)
            if es_exenta_iva is not None:
                option["attrs"]["data-es-exenta-iva"] = "true" if es_exenta_iva else "false"
        return option


class PlanMontoSelect(forms.Select):
    def __init__(self, *args, planes_data=None, **kwargs):
        self.planes_data = planes_data or {}
        super().__init__(*args, **kwargs)

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex=subindex, attrs=attrs)
        raw_value = getattr(value, "value", value)
        try:
            plan_id = int(raw_value) if raw_value is not None and raw_value != "" else None
        except (TypeError, ValueError):
            plan_id = None
        if plan_id is not None and plan_id in self.planes_data:
            plan_data = self.planes_data[plan_id]
            option["attrs"]["data-precio"] = str(plan_data["precio"])
            option["attrs"]["data-num-clases"] = str(plan_data["num_clases"])
            option["attrs"]["data-org"] = str(plan_data["organizacion_id"])
        return option


class PaymentPlanForm(forms.ModelForm):
    class Meta:
        model = PaymentPlan
        fields = [
            "organizacion",
            "nombre",
            "num_clases",
            "precio",
            "precio_incluye_iva",
            "es_por_defecto",
            "fecha_inicio",
            "fecha_fin",
            "descripcion",
            "activo",
        ]
        widgets = {
            "fecha_inicio": forms.DateInput(attrs={"type": "date"}),
            "fecha_fin": forms.DateInput(attrs={"type": "date"}),
            "descripcion": forms.Textarea(attrs={"rows": 2}),
        }


class PaymentForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = [
            "organizacion",
            "persona",
            "plan",
            "fecha_pago",
            "metodo_pago",
            "numero_comprobante",
            "aplica_iva",
            "monto_incluye_iva",
            "monto_referencia",
            "clases_asignadas",
            "observaciones",
        ]
        widgets = {
            "fecha_pago": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
            "numero_comprobante": forms.TextInput(attrs={"placeholder": "Codigo de transferencia"}),
            "observaciones": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, periodo_mes=None, periodo_anio=None, organizacion=None, **kwargs):
        self.periodo_mes = periodo_mes
        self.periodo_anio = periodo_anio
        self.organizacion_filtro = organizacion
        super().__init__(*args, **kwargs)
        if not self.is_bound and not self.initial.get("fecha_pago"):
            self.initial["fecha_pago"] = timezone.localdate()
        organizaciones_qs = self.fields["organizacion"].queryset.only("id", "es_exenta_iva")
        self.fields["organizacion"].widget = OrganizacionIvaSelect(
            attrs=self.fields["organizacion"].widget.attrs,
            choices=self.fields["organizacion"].choices,
            organizaciones_iva={org.pk: org.es_exenta_iva for org in organizaciones_qs},
        )
        estudiantes_qs = (
            Persona.objects.filter(roles__rol__codigo="ESTUDIANTE", roles__activo=True)
            .distinct()
            .order_by("apellidos", "nombres")
        )
        self.fields["persona"].queryset = estudiantes_qs
        persona_orgs = {}
        for persona_id, org_id in (
            PersonaRol.objects.filter(
                persona_id__in=estudiantes_qs.values_list("id", flat=True),
                rol__codigo="ESTUDIANTE",
                activo=True,
            )
            .values_list("persona_id", "organizacion_id")
            .iterator()
        ):
            persona_orgs.setdefault(persona_id, set()).add(org_id)
        self.fields["persona"].widget = PersonaOrganizacionSelect(
            attrs=self.fields["persona"].widget.attrs,
            choices=self.fields["persona"].choices,
            persona_orgs={k: sorted(v) for k, v in persona_orgs.items()},
        )
        planes_qs = PaymentPlan.objects.filter(activo=True).order_by("-es_por_defecto", "nombre")
        if self.instance.pk and self.instance.plan_id:
            planes_qs = PaymentPlan.objects.filter(Q(activo=True) | Q(pk=self.instance.plan_id)).order_by(
                "-es_por_defecto",
                "nombre",
            )
        self.fields["plan"].queryset = planes_qs
        self.fields["plan"].widget = PlanMontoSelect(
            attrs=self.fields["plan"].widget.attrs,
            choices=self.fields["plan"].choices,
            planes_data={
                plan.pk: {
                    "precio": plan.precio,
                    "num_clases": plan.num_clases,
                    "organizacion_id": plan.organizacion_id,
                }
                for plan in planes_qs.only("id", "precio", "num_clases", "organizacion_id")
            },
        )
        if not self.is_bound and not self.instance.pk and not self.initial.get("plan"):
            organizacion_inicial = self.initial.get("organizacion")
            organizacion_id = getattr(organizacion_inicial, "pk", organizacion_inicial)
            if organizacion_id:
                plan_por_defecto = planes_qs.filter(organizacion_id=organizacion_id, es_por_defecto=True).first()
                if plan_por_defecto:
                    self.initial["plan"] = plan_por_defecto.pk
        if not self.is_bound and not self.instance.pk and "aplica_iva" not in self.initial:
            organizacion_inicial = self.initial.get("organizacion")
            organizacion_id = getattr(organizacion_inicial, "pk", organizacion_inicial)
            if organizacion_id:
                plan_org = organizaciones_qs.filter(pk=organizacion_id).first()
                if plan_org is not None:
                    self.initial["aplica_iva"] = not plan_org.es_exenta_iva

    def clean_persona(self):
        persona = self.cleaned_data["persona"]
        organizacion = self.cleaned_data.get("organizacion")
        filtros = {"rol__codigo": "ESTUDIANTE", "activo": True}
        if organizacion:
            filtros["organizacion"] = organizacion
        if not persona.roles.filter(**filtros).exists():
            raise forms.ValidationError(
                "La persona seleccionada no tiene rol ESTUDIANTE activo en la organizacion indicada."
            )
        return persona

    def clean(self):
        cleaned = super().clean()
        metodo = cleaned.get("metodo_pago")
        numero_comprobante = (cleaned.get("numero_comprobante") or "").strip()
        if metodo == Payment.Metodo.TRANSFERENCIA and not numero_comprobante:
            self.add_error(
                "numero_comprobante",
                "El numero de comprobante es obligatorio para pagos por transferencia.",
            )
        if metodo != Payment.Metodo.TRANSFERENCIA:
            cleaned["numero_comprobante"] = ""
        plan = cleaned.get("plan")
        organizacion = cleaned.get("organizacion")
        if plan and organizacion and plan.organizacion_id != organizacion.id:
            self.add_error("plan", "El plan seleccionado no pertenece a la organizacion indicada.")
        return cleaned


class PagoMasivoForm(forms.Form):
    organizacion = forms.ModelChoiceField(queryset=Organizacion.objects.none(), required=True)
    fecha_pago = forms.DateField(widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}))
    plan = forms.ModelChoiceField(queryset=PaymentPlan.objects.none(), required=False)
    metodo_pago = forms.ChoiceField(choices=Payment.Metodo.choices)
    numero_comprobante = forms.CharField(required=False)
    aplica_iva = forms.BooleanField(required=False, initial=True)
    monto_incluye_iva = forms.BooleanField(required=False)
    monto_referencia = forms.DecimalField(max_digits=12, decimal_places=2, min_value=0)
    clases_asignadas = forms.IntegerField(min_value=0, required=False, initial=0)
    observaciones = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))
    personas_seleccionadas = forms.CharField(widget=forms.HiddenInput)
    filas_json = forms.CharField(widget=forms.HiddenInput, required=False)
    clave_idempotencia = forms.CharField(widget=forms.HiddenInput)

    def __init__(self, *args, organizaciones=None, personas=None, planes=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["organizacion"].queryset = organizaciones or Organizacion.objects.none()
        self.fields["plan"].queryset = planes or PaymentPlan.objects.none()
        self.personas_queryset = personas or Persona.objects.none()

    def clean_personas_seleccionadas(self):
        raw = self.cleaned_data["personas_seleccionadas"] or ""
        try:
            ids = [int(value) for value in raw.split(",") if value.strip()]
        except ValueError as exc:
            raise forms.ValidationError("La selección de personas no es válida.") from exc
        if not ids:
            raise forms.ValidationError("Selecciona al menos una persona.")
        if len(ids) > 20:
            raise forms.ValidationError("El lote admite como máximo 20 personas.")
        if len(ids) != len(set(ids)):
            raise forms.ValidationError("No puedes seleccionar dos veces a la misma persona.")
        personas = list(self.personas_queryset.filter(pk__in=ids))
        if len(personas) != len(ids):
            raise forms.ValidationError("Una o más personas no son elegibles para la organización.")
        self.personas_seleccionadas_obj = {persona.pk: persona for persona in personas}
        return ids

    def clean_filas_json(self):
        raw = self.cleaned_data.get("filas_json") or "{}"
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise forms.ValidationError("Los ajustes individuales no son válidos.") from exc
        if not isinstance(value, dict):
            raise forms.ValidationError("Los ajustes individuales no son válidos.")
        return value

    def clean(self):
        cleaned = super().clean()
        metodo = cleaned.get("metodo_pago")
        comprobante = (cleaned.get("numero_comprobante") or "").strip()
        if metodo == Payment.Metodo.TRANSFERENCIA and not comprobante:
            self.add_error("numero_comprobante", "El número de comprobante es obligatorio para transferencias.")
        if metodo != Payment.Metodo.TRANSFERENCIA:
            cleaned["numero_comprobante"] = ""
        organizacion = cleaned.get("organizacion")
        plan = cleaned.get("plan")
        if plan and organizacion and plan.organizacion_id != organizacion.pk:
            self.add_error("plan", "El plan no pertenece a la organización seleccionada.")
        return cleaned


class ReversaPagoForm(forms.Form):
    motivo = forms.CharField(
        required=True,
        min_length=3,
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 3,
                "placeholder": "Indica por qué se revierte este pago",
            }
        ),
    )


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ["nombre", "tipo", "activa"]


class TransactionForm(forms.ModelForm):
    tipo = forms.CharField(required=False, widget=forms.HiddenInput())

    class Meta:
        model = Transaction
        fields = [
            "organizacion",
            "categoria",
            "fecha",
            "tipo",
            "monto",
            "descripcion",
            "archivo",
        ]
        widgets = {
            "fecha": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
            "descripcion": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, periodo_mes=None, periodo_anio=None, organizacion=None, **kwargs):
        self.periodo_mes = periodo_mes
        self.periodo_anio = periodo_anio
        self.organizacion_filtro = organizacion
        super().__init__(*args, **kwargs)
        if not self.is_bound and self.instance.pk:
            self.initial["tipo"] = self.instance.categoria.tipo if self.instance.categoria_id else self.instance.tipo
        self.fields["tipo"].initial = self.initial.get("tipo", "")
        self.fields["archivo"].label = "Respaldo del movimiento"
        self.fields["archivo"].help_text = "Adjunta cartola, comprobante de transferencia u otro respaldo de caja."

    def clean(self):
        cleaned = super().clean()
        categoria = cleaned.get("categoria")
        if categoria:
            cleaned["tipo"] = categoria.tipo
        return cleaned

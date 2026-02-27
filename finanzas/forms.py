from django import forms
from django.utils import timezone

from database.models import Category, Invoice, Payment, PaymentPlan, Persona, PersonaRol, Transaction


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
            "boleta",
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.is_bound and not self.initial.get("fecha_pago"):
            self.initial["fecha_pago"] = timezone.localdate()
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
        planes_qs = PaymentPlan.objects.filter(activo=True).order_by("nombre")
        self.fields["plan"].queryset = planes_qs
        self.fields["plan"].widget = PlanMontoSelect(
            attrs=self.fields["plan"].widget.attrs,
            choices=self.fields["plan"].choices,
            planes_data={
                plan.pk: {"precio": plan.precio, "num_clases": plan.num_clases}
                for plan in planes_qs.only("id", "precio", "num_clases")
            },
        )

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
        return cleaned


class InvoiceForm(forms.ModelForm):
    class Meta:
        model = Invoice
        fields = [
            "organizacion",
            "tipo",
            "folio",
            "fecha_emision",
            "cliente",
            "monto_neto",
            "monto_iva",
            "monto_total",
            "archivo",
            "enlace_sii",
            "observaciones",
        ]
        widgets = {
            "fecha_emision": forms.DateInput(attrs={"type": "date"}),
            "observaciones": forms.Textarea(attrs={"rows": 2}),
        }


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ["nombre", "tipo", "activa"]


class TransactionForm(forms.ModelForm):
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
            "fecha": forms.DateInput(attrs={"type": "date"}),
            "descripcion": forms.Textarea(attrs={"rows": 2}),
        }

    def clean(self):
        cleaned = super().clean()
        categoria = cleaned.get("categoria")
        tipo = cleaned.get("tipo")
        if categoria and tipo and categoria.tipo != tipo:
            self.add_error("categoria", "La categoria debe coincidir con el tipo de transaccion.")
        return cleaned

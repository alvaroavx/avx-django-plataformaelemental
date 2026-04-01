from django import forms
from django.core.exceptions import NON_FIELD_ERRORS
from django.db.models import Q
from django.utils import timezone
from decimal import Decimal, InvalidOperation

from database.models import Category, DocumentoTributario, Payment, PaymentPlan, Persona, PersonaRol, Transaction


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
            "documento_tributario",
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
        documentos_qs = DocumentoTributario.objects.order_by("-fecha_emision", "-id")
        if self.instance.pk and self.instance.documento_tributario_id:
            documentos_qs = DocumentoTributario.objects.filter(
                Q(pk=self.instance.documento_tributario_id) | Q(pk__in=documentos_qs.values("pk"))
            ).order_by("-fecha_emision", "-id")
        self.fields["documento_tributario"].queryset = documentos_qs
        self.fields["documento_tributario"].label = "Documento tributario"
        self.fields["documento_tributario"].help_text = "Asocia el documento emitido al cliente si ya fue cargado."

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
        documento_tributario = cleaned.get("documento_tributario")
        if documento_tributario and organizacion and documento_tributario.organizacion_id != organizacion.id:
            self.add_error(
                "documento_tributario",
                "El documento tributario seleccionado no pertenece a la organizacion indicada.",
            )
        return cleaned


class DocumentoTributarioForm(forms.ModelForm):
    monto_neto = forms.CharField(required=False)
    monto_exento = forms.CharField(required=False)
    monto_iva = forms.CharField(required=False)
    retencion_monto = forms.CharField(required=False)
    monto_total = forms.CharField(required=False)

    class Meta:
        model = DocumentoTributario
        fields = [
            "organizacion",
            "tipo_documento",
            "fuente",
            "folio",
            "fecha_emision",
            "nombre_emisor",
            "rut_emisor",
            "nombre_receptor",
            "rut_receptor",
            "monto_neto",
            "monto_exento",
            "iva_tasa",
            "monto_iva",
            "retencion_tasa",
            "retencion_monto",
            "monto_total",
            "documento_relacionado",
            "archivo_pdf",
            "archivo_xml",
            "enlace_sii",
            "metadata_extra",
            "observaciones",
        ]
        widgets = {
            "fecha_emision": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
            "metadata_extra": forms.Textarea(attrs={"rows": 2}),
            "observaciones": forms.Textarea(attrs={"rows": 2}),
        }
        error_messages = {
            NON_FIELD_ERRORS: {
                "unique_together": (
                    "Ya existe un documento tributario con ese tipo, folio y RUT emisor dentro de la organizacion."
                ),
            }
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["documento_relacionado"].queryset = DocumentoTributario.objects.order_by("-fecha_emision", "-id")
        self.fields["documento_relacionado"].label = "Documento relacionado"
        self.fields["documento_relacionado"].help_text = (
            "Permite vincular, por ejemplo, una boleta de honorarios con una factura o documento origen."
        )
        self.fields["archivo_pdf"].label = "PDF del documento"
        self.fields["archivo_xml"].label = "XML del documento"
        self.fields["metadata_extra"].help_text = "Uso opcional para datos adicionales importados desde SII."

    @staticmethod
    def _normalizar_monto_tributario(value):
        if value in (None, ""):
            return Decimal("0")
        if isinstance(value, Decimal):
            return value
        raw = str(value).strip().replace("$", "").replace(" ", "")
        if "," in raw:
            raw = raw.replace(".", "").replace(",", ".")
        elif "." in raw and raw.count(".") >= 1:
            partes = raw.split(".")
            if all(parte.isdigit() for parte in partes) and all(len(parte) == 3 for parte in partes[1:]):
                raw = "".join(partes)
        try:
            return Decimal(raw)
        except (InvalidOperation, ValueError):
            raise forms.ValidationError("Ingresa un monto valido.")

    def clean_monto_neto(self):
        return self._normalizar_monto_tributario(self.data.get(self.add_prefix("monto_neto")))

    def clean_monto_exento(self):
        return self._normalizar_monto_tributario(self.data.get(self.add_prefix("monto_exento")))

    def clean_monto_iva(self):
        return self._normalizar_monto_tributario(self.data.get(self.add_prefix("monto_iva")))

    def clean_retencion_monto(self):
        return self._normalizar_monto_tributario(self.data.get(self.add_prefix("retencion_monto")))

    def clean_monto_total(self):
        return self._normalizar_monto_tributario(self.data.get(self.add_prefix("monto_total")))


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ["nombre", "tipo", "activa"]


class DocumentoTributarioMultipleChoiceField(forms.ModelMultipleChoiceField):
    def label_from_instance(self, obj):
        extracto = (obj.observaciones or "").strip().replace("\n", " ")
        if len(extracto) > 80:
            extracto = f"{extracto[:77].rstrip()}..."
        base = f"{obj.get_tipo_documento_display()} #{obj.folio}"
        return f"{base} - {extracto}" if extracto else base


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
            "documentos_tributarios",
            "archivo",
        ]
        widgets = {
            "fecha": forms.DateInput(attrs={"type": "date"}),
            "descripcion": forms.Textarea(attrs={"rows": 2}),
            "documentos_tributarios": forms.SelectMultiple(attrs={"size": 6}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        queryset_documentos = DocumentoTributario.objects.order_by("-fecha_emision", "-id")
        self.fields["documentos_tributarios"] = DocumentoTributarioMultipleChoiceField(
            queryset=queryset_documentos,
            required=False,
            widget=forms.SelectMultiple(attrs={"size": 6}),
            help_text="Asocia uno o mas documentos tributarios relacionados con este movimiento.",
        )
        if self.is_bound:
            self.fields["documentos_tributarios"].widget.choices = self.fields["documentos_tributarios"].choices
        elif self.instance.pk:
            self.initial["tipo"] = self.instance.categoria.tipo if self.instance.categoria_id else self.instance.tipo
        self.fields["tipo"].initial = self.initial.get("tipo", "")
        self.fields["documentos_tributarios"].help_text = (
            "Asocia uno o mas documentos tributarios relacionados con este movimiento."
        )
        self.fields["archivo"].label = "Respaldo del movimiento"
        self.fields["archivo"].help_text = "Adjunta cartola, comprobante de transferencia u otro respaldo de caja."

    def clean(self):
        cleaned = super().clean()
        categoria = cleaned.get("categoria")
        if categoria:
            cleaned["tipo"] = categoria.tipo
        organizacion = cleaned.get("organizacion")
        for documento in cleaned.get("documentos_tributarios") or []:
            if organizacion and documento.organizacion_id != organizacion.id:
                self.add_error(
                    "documentos_tributarios",
                    "Todos los documentos tributarios deben pertenecer a la misma organizacion de la transaccion.",
                )
                break
        return cleaned


class DocumentoTributarioImportUploadForm(forms.Form):
    archivo = forms.FileField(required=False, label="Archivo tributario")

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("archivo"):
            raise forms.ValidationError("Debes subir un archivo XML o PDF.")
        return cleaned


class DocumentoTributarioImportConfirmForm(forms.Form):
    token_importacion = forms.CharField(widget=forms.HiddenInput())
    guardar_pago_sugerido = forms.BooleanField(
        required=False,
        initial=False,
        label="Guardar tambien el pago sugerido",
    )

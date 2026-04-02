from decimal import Decimal, ROUND_HALF_UP

from django.db import models
from django.utils import timezone


IVA_RATE = Decimal("0.19")


def _money(value: Decimal) -> Decimal:
    return (value or Decimal("0")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class TimeStampedModel(models.Model):
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class PaymentPlan(TimeStampedModel):
    organizacion = models.ForeignKey(
        "personas.Organizacion",
        on_delete=models.CASCADE,
        related_name="planes_pago",
    )
    nombre = models.CharField(max_length=150)
    num_clases = models.PositiveIntegerField(default=1)
    precio = models.DecimalField(max_digits=12, decimal_places=2)
    precio_incluye_iva = models.BooleanField(default=False)
    es_por_defecto = models.BooleanField(default=False)
    fecha_inicio = models.DateField(null=True, blank=True)
    fecha_fin = models.DateField(null=True, blank=True)
    descripcion = models.TextField(blank=True)
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Plan de pago"
        verbose_name_plural = "Planes de pago"
        ordering = ["organizacion__nombre", "nombre"]
        db_table = "finanzas_paymentplan"
        unique_together = ("organizacion", "nombre")

    def __str__(self) -> str:
        return f"{self.nombre} ({self.organizacion})"

    def save(self, *args, **kwargs):
        queryset_organizacion = PaymentPlan.objects.filter(organizacion_id=self.organizacion_id)
        if self.pk:
            queryset_organizacion = queryset_organizacion.exclude(pk=self.pk)
        if not queryset_organizacion.exists():
            self.es_por_defecto = True
        elif not self.es_por_defecto and not queryset_organizacion.filter(es_por_defecto=True).exists():
            self.es_por_defecto = True
        super().save(*args, **kwargs)
        if self.es_por_defecto:
            PaymentPlan.objects.filter(organizacion_id=self.organizacion_id).exclude(pk=self.pk).update(
                es_por_defecto=False
            )

    def delete(self, *args, **kwargs):
        organizacion_id = self.organizacion_id
        era_por_defecto = self.es_por_defecto
        super().delete(*args, **kwargs)
        if era_por_defecto:
            siguiente_plan = PaymentPlan.objects.filter(organizacion_id=organizacion_id).order_by("nombre", "id").first()
            if siguiente_plan:
                PaymentPlan.objects.filter(pk=siguiente_plan.pk).update(es_por_defecto=True)

    def calcular_montos(self):
        precio = _money(Decimal(self.precio or 0))
        if self.organizacion.es_exenta_iva:
            return precio, Decimal("0.00"), precio
        if self.precio_incluye_iva:
            total = precio
            neto = _money(total / (Decimal("1.00") + IVA_RATE))
            iva = _money(total - neto)
            return neto, iva, total
        neto = precio
        iva = _money(neto * IVA_RATE)
        total = _money(neto + iva)
        return neto, iva, total


class DocumentoTributario(TimeStampedModel):
    class TipoDocumento(models.TextChoices):
        FACTURA_AFECTA = "factura_afecta", "Factura afecta"
        FACTURA_EXENTA = "factura_exenta", "Factura exenta"
        BOLETA_VENTA_AFECTA = "boleta_venta_afecta", "Boleta de venta afecta"
        BOLETA_VENTA_EXENTA = "boleta_venta_exenta", "Boleta de venta exenta"
        BOLETA_HONORARIOS = "boleta_honorarios", "Boleta de honorarios"
        NOTA_CREDITO = "nota_credito", "Nota de credito"
        NOTA_DEBITO = "nota_debito", "Nota de debito"
        OTRO = "otro", "Otro"

    class Fuente(models.TextChoices):
        MANUAL = "manual", "Carga manual"
        SII = "sii", "Importado desde SII"

    organizacion = models.ForeignKey(
        "personas.Organizacion",
        on_delete=models.CASCADE,
        related_name="documentos_tributarios",
    )
    tipo_documento = models.CharField(
        max_length=40,
        choices=TipoDocumento.choices,
        default=TipoDocumento.FACTURA_AFECTA,
    )
    fuente = models.CharField(max_length=20, choices=Fuente.choices, default=Fuente.MANUAL)
    folio = models.CharField(max_length=100)
    fecha_emision = models.DateField(default=timezone.localdate)
    nombre_emisor = models.CharField(max_length=255, blank=True)
    rut_emisor = models.CharField(max_length=20, blank=True)
    nombre_receptor = models.CharField(max_length=255, blank=True)
    rut_receptor = models.CharField(max_length=20, blank=True)
    monto_neto = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    monto_exento = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    iva_tasa = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("19.00"))
    monto_iva = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    retencion_tasa = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    retencion_monto = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    monto_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    documento_relacionado = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        related_name="documentos_hijos",
        null=True,
        blank=True,
    )
    archivo_pdf = models.FileField(upload_to="finanzas/documentos/pdf/", null=True, blank=True)
    archivo_xml = models.FileField(upload_to="finanzas/documentos/xml/", null=True, blank=True)
    enlace_sii = models.URLField(blank=True)
    metadata_extra = models.JSONField(default=dict, blank=True)
    observaciones = models.TextField(blank=True)

    class Meta:
        verbose_name = "Documento tributario"
        verbose_name_plural = "Documentos tributarios"
        ordering = ["-fecha_emision", "-id"]
        db_table = "finanzas_invoice"
        unique_together = ("organizacion", "tipo_documento", "folio", "rut_emisor")

    def __str__(self) -> str:
        return f"{self.get_tipo_documento_display()} #{self.folio}"

    @property
    def archivo_principal(self):
        return self.archivo_pdf or self.archivo_xml

    @property
    def tiene_archivo_pdf(self) -> bool:
        return bool(self.archivo_pdf and self.archivo_pdf.name.lower().endswith(".pdf"))


class Category(TimeStampedModel):
    class Tipo(models.TextChoices):
        INGRESO = "ingreso", "Ingreso"
        EGRESO = "egreso", "Egreso"

    nombre = models.CharField(max_length=150, unique=True)
    tipo = models.CharField(max_length=20, choices=Tipo.choices)
    activa = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Categoria"
        verbose_name_plural = "Categorias"
        ordering = ["tipo", "nombre"]
        db_table = "finanzas_category"

    def __str__(self) -> str:
        return f"{self.nombre} ({self.get_tipo_display()})"


class Payment(TimeStampedModel):
    class Metodo(models.TextChoices):
        EFECTIVO = "efectivo", "Efectivo"
        TRANSFERENCIA = "transferencia", "Transferencia"
        TARJETA = "tarjeta", "Tarjeta"
        OTRO = "otro", "Otro"

    persona = models.ForeignKey(
        "personas.Persona",
        on_delete=models.PROTECT,
        related_name="pagos_financieros",
        limit_choices_to={"roles__rol__codigo__iexact": "ESTUDIANTE", "roles__activo": True},
    )
    organizacion = models.ForeignKey(
        "personas.Organizacion",
        on_delete=models.CASCADE,
        related_name="pagos_financieros",
    )
    plan = models.ForeignKey(
        PaymentPlan,
        on_delete=models.SET_NULL,
        related_name="pagos",
        null=True,
        blank=True,
    )
    documento_tributario = models.ForeignKey(
        DocumentoTributario,
        on_delete=models.SET_NULL,
        related_name="pagos_asociados",
        null=True,
        blank=True,
    )
    fecha_pago = models.DateField(default=timezone.localdate)
    metodo_pago = models.CharField(max_length=20, choices=Metodo.choices, default=Metodo.TRANSFERENCIA)
    numero_comprobante = models.CharField(max_length=100, blank=True, default="")
    aplica_iva = models.BooleanField(default=True)
    monto_incluye_iva = models.BooleanField(default=False)
    monto_referencia = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    monto_neto = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    monto_iva = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    monto_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    clases_asignadas = models.PositiveIntegerField(default=0)
    observaciones = models.TextField(blank=True)

    class Meta:
        verbose_name = "Pago"
        verbose_name_plural = "Pagos"
        ordering = ["-fecha_pago", "-id"]
        db_table = "finanzas_payment"
        indexes = [
            models.Index(fields=["fecha_pago", "organizacion"]),
            models.Index(fields=["persona", "fecha_pago"]),
        ]

    def __str__(self) -> str:
        return f"Pago {self.persona} - {self.fecha_pago}"

    def calcular_montos(self):
        base = Decimal(self.monto_referencia or 0)
        if self.plan_id and not base:
            base = Decimal(self.plan.precio)
        base = _money(base)

        aplica_iva = bool(self.aplica_iva) and not self.organizacion.es_exenta_iva
        if not aplica_iva:
            neto = base
            iva = Decimal("0.00")
            total = base
        elif self.monto_incluye_iva or (self.plan_id and self.plan.precio_incluye_iva):
            total = base
            neto = _money(total / (Decimal("1.00") + IVA_RATE))
            iva = _money(total - neto)
        else:
            neto = base
            iva = _money(neto * IVA_RATE)
            total = _money(neto + iva)
        return neto, iva, total

    @property
    def clases_consumidas(self):
        return self.consumos.filter(estado=AttendanceConsumption.Estado.CONSUMIDO).count()

    @property
    def saldo_clases(self):
        return self.clases_asignadas - self.clases_consumidas

    def save(self, *args, **kwargs):
        if self.plan_id and not self.clases_asignadas:
            self.clases_asignadas = self.plan.num_clases
        if self.organizacion.es_exenta_iva:
            self.aplica_iva = False
        neto, iva, total = self.calcular_montos()
        self.monto_neto = neto
        self.monto_iva = iva
        self.monto_total = total
        super().save(*args, **kwargs)


class AttendanceConsumption(TimeStampedModel):
    class Estado(models.TextChoices):
        CONSUMIDO = "consumido", "Consumido"
        PENDIENTE = "pendiente", "Pendiente"
        DEUDA = "deuda", "Deuda"

    asistencia = models.OneToOneField(
        "asistencias.Asistencia",
        on_delete=models.CASCADE,
        related_name="consumo_financiero",
    )
    persona = models.ForeignKey(
        "personas.Persona",
        on_delete=models.CASCADE,
        related_name="consumos_asistencia",
    )
    clase_fecha = models.DateField()
    pago = models.ForeignKey(
        Payment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="consumos",
    )
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.PENDIENTE)
    observaciones = models.TextField(blank=True)

    class Meta:
        verbose_name = "Consumo de asistencia"
        verbose_name_plural = "Consumos de asistencia"
        ordering = ["-clase_fecha", "-id"]
        db_table = "finanzas_attendanceconsumption"
        indexes = [
            models.Index(fields=["persona", "clase_fecha"]),
            models.Index(fields=["estado", "clase_fecha"]),
        ]

    def __str__(self) -> str:
        return f"{self.persona} - {self.clase_fecha} ({self.get_estado_display()})"


class Transaction(TimeStampedModel):
    class Tipo(models.TextChoices):
        INGRESO = "ingreso", "Ingreso"
        EGRESO = "egreso", "Egreso"

    organizacion = models.ForeignKey(
        "personas.Organizacion",
        on_delete=models.CASCADE,
        related_name="transacciones_financieras",
    )
    categoria = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="transacciones",
    )
    fecha = models.DateField(default=timezone.localdate)
    tipo = models.CharField(max_length=20, choices=Tipo.choices)
    monto = models.DecimalField(max_digits=12, decimal_places=2)
    descripcion = models.TextField(blank=True)
    archivo = models.FileField(upload_to="finanzas/transactions/", null=True, blank=True)
    documentos_tributarios = models.ManyToManyField(
        DocumentoTributario,
        related_name="transacciones_asociadas",
        blank=True,
    )

    class Meta:
        verbose_name = "Transaccion"
        verbose_name_plural = "Transacciones"
        ordering = ["-fecha", "-id"]
        db_table = "finanzas_transaction"
        indexes = [
            models.Index(fields=["fecha", "organizacion"]),
            models.Index(fields=["tipo", "fecha"]),
        ]

    def __str__(self) -> str:
        return f"{self.get_tipo_display()} {self.monto} ({self.categoria})"


Invoice = DocumentoTributario

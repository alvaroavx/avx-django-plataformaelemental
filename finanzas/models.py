from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
import uuid

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


IVA_RATE = Decimal("0.19")


def _clp(value) -> int:
    """Redondea a pesos enteros (CLP no usa decimales)."""
    return int(Decimal(str(value or 0)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def desglosar_montos(base, *, afecto: bool, incluye_iva: bool) -> tuple[int, int, int]:
    """Devuelve (neto, iva, total) en CLP enteros con la regla de Cuadratura.

    Con IVA incluido el total manda: neto = round(total / 1,19) e iva = total - neto.
    Con IVA agregado, iva = round(neto * 0,19); el resultado es idéntico a aplicar
    la regla anterior sobre el total, porque el error de redondeo nunca supera 0,5.
    """
    base = _clp(base)
    if not afecto:
        return base, 0, base
    if incluye_iva:
        neto = _clp(Decimal(base) / (Decimal("1") + IVA_RATE))
        return neto, base - neto, base
    iva = _clp(Decimal(base) * IVA_RATE)
    return base, iva, base + iva


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
    precio = models.BigIntegerField(help_text="Pesos chilenos enteros.")
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
        return desglosar_montos(
            self.precio,
            afecto=not self.organizacion.es_exenta_iva,
            incluye_iva=self.precio_incluye_iva,
        )


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


class LotePago(TimeStampedModel):
    """Identidad auditable de una confirmación de pagos masivos."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organizacion = models.ForeignKey(
        "personas.Organizacion",
        on_delete=models.PROTECT,
        related_name="lotes_pago",
    )
    clave_idempotencia = models.CharField(max_length=128, unique=True)
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="lotes_pago_creados",
    )
    cantidad_pagos = models.PositiveIntegerField(default=0)
    monto_total = models.BigIntegerField(default=0)
    confirmado_en = models.DateTimeField(null=True, blank=True)
    origen = models.CharField(max_length=40, default="pago_masivo")
    respaldo = models.FileField(upload_to="finanzas/lotes/", null=True, blank=True)
    metadatos = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = "Lote de pagos"
        verbose_name_plural = "Lotes de pagos"
        ordering = ["-creado_en"]

    def __str__(self):
        return f"Lote {self.pk} ({self.cantidad_pagos} pagos)"


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
    disciplina = models.ForeignKey(
        "asistencias.Disciplina",
        on_delete=models.PROTECT,
        related_name="pagos_operacionales",
        null=True,
        blank=True,
    )
    fecha_pago = models.DateField(default=timezone.localdate)
    metodo_pago = models.CharField(max_length=20, choices=Metodo.choices, default=Metodo.TRANSFERENCIA)
    numero_comprobante = models.CharField(max_length=100, blank=True, default="")
    aplica_iva = models.BooleanField(default=True)
    monto_incluye_iva = models.BooleanField(default=False)
    monto_referencia = models.BigIntegerField(default=0)
    monto_neto = models.BigIntegerField(default=0)
    monto_iva = models.BigIntegerField(default=0)
    monto_total = models.BigIntegerField(default=0)
    clases_asignadas = models.PositiveIntegerField(default=0)
    observaciones = models.TextField(blank=True)
    respaldo = models.FileField(upload_to="finanzas/pagos/", null=True, blank=True)
    registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="pagos_operacionales_registrados",
    )
    clave_idempotencia = models.CharField(max_length=160, null=True, blank=True, unique=True)
    transaccion = models.OneToOneField(
        "Transaction",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="pago_operacional",
    )
    revertido_en = models.DateTimeField(null=True, blank=True)
    revertido_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="pagos_revertidos",
    )
    motivo_reversa = models.TextField(blank=True)
    lote = models.ForeignKey(
        "LotePago",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="pagos",
    )

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
        base = self.monto_referencia or 0
        if self.plan_id and not base:
            base = self.plan.precio
        return desglosar_montos(
            base,
            afecto=bool(self.aplica_iva) and not self.organizacion.es_exenta_iva,
            incluye_iva=self.monto_incluye_iva or bool(self.plan_id and self.plan.precio_incluye_iva),
        )

    @property
    def clases_consumidas(self):
        if self.revertido_en:
            return 0
        return self.consumos.filter(estado=AttendanceConsumption.Estado.CONSUMIDO).count()

    @property
    def saldo_clases(self):
        if self.revertido_en:
            return 0
        return self.clases_asignadas - self.clases_consumidas

    @property
    def esta_revertido(self):
        return self.revertido_en is not None

    def save(self, *args, **kwargs):
        if self.plan_id and not self.clases_asignadas:
            self.clases_asignadas = self.plan.num_clases
        if self.organizacion.es_exenta_iva:
            self.aplica_iva = False
        neto, iva, total = self.calcular_montos()
        self.monto_neto = neto
        self.monto_iva = iva
        self.monto_total = total
        self._validar_mes_no_enviado()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        self._validar_mes_no_enviado()
        return super().delete(*args, **kwargs)

    def _validar_mes_no_enviado(self):
        if self.pk:
            original = Payment.objects.filter(pk=self.pk).values_list("organizacion_id", "fecha_pago").first()
            if original:
                validar_meses_no_enviados(*original)
        validar_meses_no_enviados(self.organizacion_id, self.fecha_pago)


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
    monto = models.BigIntegerField(help_text="Pesos chilenos enteros.")
    descripcion = models.TextField(blank=True)
    archivo = models.FileField(upload_to="finanzas/transactions/", null=True, blank=True)
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="transacciones_financieras_creadas",
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

    def save(self, *args, **kwargs):
        self._validar_mes_no_enviado()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        self._validar_mes_no_enviado()
        return super().delete(*args, **kwargs)

    def _validar_mes_no_enviado(self):
        """Solo los movimientos enlazados a un pago viajan a Cuadratura y quedan bloqueados."""
        if not self.pk:
            return
        pago = Payment.objects.filter(transaccion_id=self.pk).values_list("organizacion_id", "fecha_pago").first()
        if pago:
            validar_meses_no_enviados(pago[0], pago[1], self.fecha)


class EnvioCuadratura(TimeStampedModel):
    """Intento de envío de un mes a la API de Cuadratura (ADR 0023).

    El mes queda bloqueado (pagos y movimientos enlazados no se pueden crear, editar,
    revertir ni eliminar) mientras el último intento esté en curso, enviado o incierto.
    Un intento rechazado o fallido antes de transmitir datos lo libera.
    """

    class Estado(models.TextChoices):
        EN_CURSO = "en_curso", "En curso"
        ENVIADO = "enviado", "Enviado"
        INCIERTO = "incierto", "Sin confirmación de Cuadratura"
        RECHAZADO = "rechazado", "Rechazado por Cuadratura"
        FALLIDO = "fallido", "No se pudo transmitir"

    ESTADOS_QUE_BLOQUEAN = (Estado.EN_CURSO, Estado.ENVIADO, Estado.INCIERTO)

    organizacion = models.ForeignKey(
        "personas.Organizacion",
        on_delete=models.PROTECT,
        related_name="envios_cuadratura",
    )
    periodo = models.DateField(help_text="Primer día del mes enviado.")
    estado = models.CharField(max_length=20, choices=Estado.choices)
    enviado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="envios_cuadratura",
    )
    contrato = models.CharField(max_length=64)
    batch_id = models.CharField(max_length=64, help_text="Llave de idempotencia enviada a Cuadratura.")
    operaciones = models.PositiveIntegerField(default=0)
    monto_total = models.BigIntegerField(default=0)
    lote_cuadratura = models.CharField(max_length=64, blank=True, help_text="Identificador del lote en Cuadratura.")
    estado_cuadratura = models.CharField(max_length=20, blank=True)
    url_revision = models.URLField(max_length=500, blank=True)
    respuesta = models.JSONField(default=dict, blank=True, help_text="Acuse o error devuelto por Cuadratura.")
    detalle_error = models.TextField(blank=True)

    class Meta:
        verbose_name = "Envío a Cuadratura"
        verbose_name_plural = "Envíos a Cuadratura"
        ordering = ["-creado_en", "-id"]
        db_table = "finanzas_enviocuadratura"
        constraints = [
            models.UniqueConstraint(
                fields=["organizacion", "periodo"],
                condition=models.Q(estado__in=["en_curso", "enviado"]),
                name="uq_envio_cuadratura_mes_activo",
            )
        ]

    def __str__(self) -> str:
        return f"{self.organizacion} {self.periodo:%Y-%m} ({self.get_estado_display()})"


MESES_ES = (
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
)


def ultimo_envio_cuadratura(organizacion_id, periodo):
    return (
        EnvioCuadratura.objects.filter(organizacion_id=organizacion_id, periodo=periodo)
        .order_by("-creado_en", "-id")
        .first()
    )


def validar_meses_no_enviados(organizacion_id, *fechas):
    """Rechaza cambios financieros en un mes enviado o en envío a Cuadratura."""
    periodos = set()
    for fecha in fechas:
        if isinstance(fecha, str):
            fecha = date.fromisoformat(fecha)
        if fecha:
            periodos.add(fecha.replace(day=1))
    if not organizacion_id or not periodos:
        return
    for periodo in sorted(periodos):
        envio = ultimo_envio_cuadratura(organizacion_id, periodo)
        if envio is None or envio.estado not in EnvioCuadratura.ESTADOS_QUE_BLOQUEAN:
            continue
        mes = f"{MESES_ES[periodo.month - 1].capitalize()} {periodo.year}"
        if envio.estado == EnvioCuadratura.Estado.ENVIADO:
            raise ValidationError(
                f"{mes} ya fue enviado a Cuadratura y está bloqueado: no se pueden registrar ni modificar sus pagos."
            )
        raise ValidationError(
            f"{mes} tiene un envío a Cuadratura en curso o sin confirmar: está bloqueado hasta que "
            "un reintento del envío termine."
        )

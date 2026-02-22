import math
from datetime import timedelta
from decimal import Decimal
from django.db import models
from django.utils import timezone


class Plan(models.Model):
    organizacion = models.ForeignKey(
        "organizaciones.Organizacion",
        on_delete=models.CASCADE,
        related_name="planes",
    )
    nombre = models.CharField(max_length=150)
    descripcion = models.TextField(blank=True)
    precio = models.DecimalField(max_digits=10, decimal_places=2)
    duracion_dias = models.PositiveIntegerField(default=30)
    clases_por_semana = models.PositiveIntegerField(default=1)
    clases_por_mes = models.PositiveIntegerField(default=4)
    activo = models.BooleanField(default=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Plan"
        verbose_name_plural = "Planes"
        unique_together = ("organizacion", "nombre")

    def __str__(self) -> str:
        return f"{self.nombre} ({self.organizacion})"

    def clases_asignadas_para_periodo(self, dias):
        semanas = max(1, math.ceil(dias / 7))
        return self.clases_por_semana * semanas


class ConvenioIntercambio(models.Model):
    organizacion = models.ForeignKey(
        "organizaciones.Organizacion",
        on_delete=models.CASCADE,
        related_name="convenios",
    )
    nombre = models.CharField(max_length=150)
    descripcion = models.TextField(blank=True)
    descuento_porcentaje = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    vigente_desde = models.DateField()
    vigente_hasta = models.DateField(null=True, blank=True)
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Convenio de intercambio"
        verbose_name_plural = "Convenios de intercambio"
        ordering = ["nombre"]

    def __str__(self) -> str:
        return self.nombre


class DocumentoVenta(models.Model):
    class Estado(models.TextChoices):
        BORRADOR = "borrador", "Borrador"
        EMITIDO = "emitido", "Emitido"
        PAGADO = "pagado", "Pagado"
        ANULADO = "anulado", "Anulado"

    organizacion = models.ForeignKey(
        "organizaciones.Organizacion",
        on_delete=models.CASCADE,
        related_name="documentos_venta",
    )
    numero = models.CharField(max_length=50)
    fecha_emision = models.DateField()
    monto_total = models.DecimalField(max_digits=10, decimal_places=2)
    estado = models.CharField(
        max_length=20,
        choices=Estado.choices,
        default=Estado.BORRADOR,
    )
    notas = models.TextField(blank=True)

    class Meta:
        verbose_name = "Documento de venta"
        verbose_name_plural = "Documentos de venta"
        unique_together = ("organizacion", "numero")

    def __str__(self) -> str:
        return f"{self.numero} - {self.organizacion}"


class Pago(models.Model):
    class Tipo(models.TextChoices):
        PLAN = "plan", "Plan"
        CLASE = "clase", "Clase"
        OTRO = "otro", "Otro"

    class Metodo(models.TextChoices):
        EFECTIVO = "efectivo", "Efectivo"
        TRANSFERENCIA = "transferencia", "Transferencia"
        TARJETA = "tarjeta", "Tarjeta"

    persona = models.ForeignKey(
        "cuentas.Persona",
        on_delete=models.CASCADE,
        related_name="pagos",
        null=True,
        blank=True,
    )
    plan = models.ForeignKey(
        Plan,
        on_delete=models.SET_NULL,
        related_name="pagos",
        null=True,
        blank=True,
    )
    sesion = models.ForeignKey(
        "academia.SesionClase",
        on_delete=models.SET_NULL,
        related_name="pagos",
        null=True,
        blank=True,
    )
    documento = models.ForeignKey(
        DocumentoVenta,
        on_delete=models.CASCADE,
        related_name="pagos",
        null=True,
        blank=True,
    )
    tipo = models.CharField(max_length=20, choices=Tipo.choices, default=Tipo.PLAN)
    fecha_pago = models.DateField()
    paid_at = models.DateTimeField(default=timezone.now)
    ciclo_start = models.DateTimeField(null=True, blank=True)
    ciclo_end = models.DateTimeField(null=True, blank=True)
    carryover_approved = models.BooleanField(default=False)
    freeze_days = models.PositiveIntegerField(default=0)
    valido_hasta = models.DateField(null=True, blank=True)
    clases_total = models.PositiveIntegerField(null=True, blank=True)
    clases_usadas = models.PositiveIntegerField(default=0)
    precio_lista_referencia = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    tarifa_clase_personalizada = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    monto = models.DecimalField(max_digits=10, decimal_places=2)
    metodo = models.CharField(max_length=20, choices=Metodo.choices)
    referencia = models.CharField(max_length=100, blank=True)
    registrado_en = models.DateTimeField(auto_now_add=True)
    comprobante = models.FileField(upload_to="comprobantes/pagos/", null=True, blank=True)

    class Meta:
        verbose_name = "Pago"
        verbose_name_plural = "Pagos"
        ordering = ["-fecha_pago"]

    def __str__(self) -> str:
        return f"{self.monto} - {self.persona or self.documento}"

    def es_plan(self):
        return self.tipo == self.Tipo.PLAN

    def clases_restantes(self):
        if not self.es_plan() and self.tipo != self.Tipo.CLASE:
            return 0
        total = self.clases_total or 0
        return max(0, total - (self.clases_usadas or 0))

    def vigente_en(self, fecha=None):
        if not self.es_plan() and self.tipo != self.Tipo.CLASE:
            return False
        fecha = fecha or timezone.localdate()
        if self.valido_hasta:
            return self.fecha_pago <= fecha <= self.valido_hasta
        return self.fecha_pago <= fecha

    def save(self, *args, **kwargs):
        if self.es_plan() or self.tipo == self.Tipo.CLASE:
            if not self.paid_at:
                self.paid_at = timezone.now()
            if self.es_plan() and not self.precio_lista_referencia and self.plan:
                self.precio_lista_referencia = self.plan.precio
            if self.tipo == self.Tipo.CLASE and not self.precio_lista_referencia:
                self.precio_lista_referencia = Decimal("9000")
            if not self.ciclo_start:
                self.ciclo_start = self.paid_at
            if not self.ciclo_end and self.ciclo_start:
                dias = self.plan.duracion_dias if self.plan and self.plan.duracion_dias else 30
                dias += self.freeze_days or 0
                self.ciclo_end = self.ciclo_start + timedelta(days=dias)
            if not self.valido_hasta and self.fecha_pago:
                dias = self.plan.duracion_dias if self.plan and self.plan.duracion_dias else 30
                dias += self.freeze_days or 0
                self.valido_hasta = self.fecha_pago + timedelta(days=dias)
            if self.clases_total is None:
                if self.es_plan() and self.plan:
                    self.clases_total = self.plan.clases_por_mes
                elif self.tipo == self.Tipo.CLASE:
                    self.clases_total = 1
        super().save(*args, **kwargs)

    @classmethod
    def asignar_plan_para_asistencia(cls, persona, fecha):
        from .services import imputar_asistencia

        asistencia = (
            persona.asistencias.filter(sesion__fecha=fecha)
            .select_related("sesion", "sesion__disciplina")
            .order_by("-id")
            .first()
        )
        if asistencia:
            imputar_asistencia(asistencia)
            return asistencia.pago_plan
        pagos_qs = (
            cls.objects.filter(
                persona=persona,
                tipo__in=[cls.Tipo.PLAN, cls.Tipo.CLASE],
                fecha_pago__lte=fecha,
            )
            .exclude(valido_hasta__lt=fecha)
            .order_by("fecha_pago", "id")
        )
        for pago in pagos_qs:
            if pago.clases_restantes() > 0:
                pago.clases_usadas = (pago.clases_usadas or 0) + 1
                pago.save(update_fields=["clases_usadas"])
                return pago
        return None


class CondicionCobroPersona(models.Model):
    class Tipo(models.TextChoices):
        NORMAL = "normal", "Normal"
        CLASE_ESPECIAL = "clase_especial", "Clase especial"
        BECA = "beca", "Beca"

    persona = models.ForeignKey(
        "cuentas.Persona",
        on_delete=models.CASCADE,
        related_name="condiciones_cobro",
    )
    organizacion = models.ForeignKey(
        "organizaciones.Organizacion",
        on_delete=models.CASCADE,
        related_name="condiciones_cobro_persona",
    )
    tipo = models.CharField(max_length=20, choices=Tipo.choices, default=Tipo.NORMAL)
    tarifa_clase_especial = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    vigente_desde = models.DateField()
    vigente_hasta = models.DateField(null=True, blank=True)
    activo = models.BooleanField(default=True)
    observaciones = models.CharField(max_length=255, blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Condicion de cobro persona"
        verbose_name_plural = "Condiciones de cobro persona"
        ordering = ["-vigente_desde", "-id"]

    def __str__(self):
        return f"{self.persona} - {self.get_tipo_display()} ({self.organizacion})"

    def vigente_en(self, fecha):
        if not self.activo:
            return False
        if self.vigente_desde and fecha < self.vigente_desde:
            return False
        if self.vigente_hasta and fecha > self.vigente_hasta:
            return False
        return True

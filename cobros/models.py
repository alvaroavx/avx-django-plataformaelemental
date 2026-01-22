import math
from decimal import Decimal

from django.apps import apps
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


class Suscripcion(models.Model):
    class Estado(models.TextChoices):
        ACTIVA = "activa", "Activa"
        CONGELADA = "congelada", "Congelada"
        FINALIZADA = "finalizada", "Finalizada"

    persona = models.ForeignKey(
        "cuentas.Persona",
        on_delete=models.CASCADE,
        related_name="suscripciones",
    )
    plan = models.ForeignKey(
        Plan,
        on_delete=models.PROTECT,
        related_name="suscripciones",
    )
    convenios = models.ManyToManyField(
        ConvenioIntercambio,
        blank=True,
        related_name="suscripciones",
    )
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField(null=True, blank=True)
    monto_pactado = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    descuento_porcentaje = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    descuento_monto = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    estado = models.CharField(
        max_length=20,
        choices=Estado.choices,
        default=Estado.ACTIVA,
    )
    notas = models.TextField(blank=True)
    creada_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Suscripcion"
        verbose_name_plural = "Suscripciones"
        ordering = ["-fecha_inicio"]

    def __str__(self) -> str:
        return f"{self.persona} - {self.plan}"

    def _fecha_fin_real(self):
        return self.fecha_fin or timezone.now().date()

    def dias_periodo(self):
        delta = (self._fecha_fin_real() - self.fecha_inicio).days + 1
        return max(1, delta)

    def clases_asignadas(self):
        return self.plan.clases_asignadas_para_periodo(self.dias_periodo())

    def asistencias_periodo(self):
        Asistencia = apps.get_model("asistencias", "Asistencia")
        return Asistencia.objects.filter(
            persona=self.persona,
            sesion__fecha__gte=self.fecha_inicio,
            sesion__fecha__lte=self._fecha_fin_real(),
        )

    def clases_usadas(self):
        return self.asistencias_periodo().filter(convenio__isnull=True).count()

    def clases_disponibles(self):
        return max(0, self.clases_asignadas() - self.clases_usadas())

    def clases_sobreconsumo(self):
        excedente = self.clases_usadas() - self.clases_asignadas()
        return max(0, excedente)

    def pagos_registrados(self):
        Pago = apps.get_model("cobros", "Pago")
        pagos_qs = Pago.objects.filter(
            models.Q(persona=self.persona)
            | models.Q(suscripcion=self)
            | models.Q(documento__suscripcion=self)
        ).distinct()
        pagos_qs = pagos_qs.exclude(tipo=Pago.Tipo.CLASE)
        return sum(
            (pago.monto for pago in pagos_qs),
            Decimal("0"),
        )

    def monto_objetivo(self):
        base = self.monto_pactado if self.monto_pactado is not None else self.plan.precio
        if self.descuento_porcentaje:
            descuento = (base * (Decimal(self.descuento_porcentaje) / Decimal("100"))).quantize(Decimal("0.01"))
        else:
            descuento = Decimal(self.descuento_monto or 0)
        total = base - descuento
        return total if total > 0 else Decimal("0")

    def saldo_pendiente(self):
        saldo = self.monto_objetivo() - self.pagos_registrados()
        return saldo if saldo > 0 else Decimal("0")


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
    suscripcion = models.ForeignKey(
        Suscripcion,
        on_delete=models.SET_NULL,
        related_name="documentos",
        null=True,
        blank=True,
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
        SUSCRIPCION = "suscripcion", "Suscripcion"
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
    suscripcion = models.ForeignKey(
        Suscripcion,
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
    tipo = models.CharField(max_length=20, choices=Tipo.choices, default=Tipo.SUSCRIPCION)
    fecha_pago = models.DateField()
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

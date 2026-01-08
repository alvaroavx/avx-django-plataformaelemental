from decimal import Decimal

from django.apps import apps
from django.db import models

IVA_RATE = Decimal("0.19")
RETENCION_PROFESOR = Decimal("0.145")
TARIFA_DEFECTO = Decimal("3743")


class TarifaPagoProfesor(models.Model):
    organizacion = models.ForeignKey(
        "organizaciones.Organizacion",
        on_delete=models.CASCADE,
        related_name="tarifas_profesores",
    )
    disciplina = models.ForeignKey(
        "academia.Disciplina",
        on_delete=models.SET_NULL,
        related_name="tarifas_profesores",
        null=True,
        blank=True,
    )
    monto_por_sesion = models.DecimalField(max_digits=10, decimal_places=2)
    vigente_desde = models.DateField()
    vigente_hasta = models.DateField(null=True, blank=True)
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Tarifa pago profesor"
        verbose_name_plural = "Tarifas pago profesor"
        ordering = ["organizacion", "vigente_desde"]

    def __str__(self) -> str:
        target = self.disciplina or "General"
        return f"{target} - {self.monto_por_sesion}"

    @classmethod
    def obtener_tarifa_para_fecha(cls, organizacion, disciplina, fecha):
        qs = cls.objects.filter(
            organizacion=organizacion,
            activo=True,
            vigente_desde__lte=fecha,
        ).order_by("-vigente_desde")
        if disciplina is not None:
            qs_disciplina = qs.filter(models.Q(disciplina=disciplina) | models.Q(disciplina__isnull=True))
        else:
            qs_disciplina = qs.filter(disciplina__isnull=True)
        if fecha:
            qs_disciplina = qs_disciplina.filter(
                models.Q(vigente_hasta__isnull=True) | models.Q(vigente_hasta__gte=fecha)
            )
        return qs_disciplina.first()


class LiquidacionProfesor(models.Model):
    class Estado(models.TextChoices):
        BORRADOR = "borrador", "Borrador"
        EMITIDA = "emitida", "Emitida"
        PAGADA = "pagada", "Pagada"

    organizacion = models.ForeignKey(
        "organizaciones.Organizacion",
        on_delete=models.CASCADE,
        related_name="liquidaciones_profesores",
    )
    profesor = models.ForeignKey(
        "cuentas.Persona",
        on_delete=models.PROTECT,
        related_name="liquidaciones",
    )
    sesiones = models.ManyToManyField(
        "academia.SesionClase",
        related_name="liquidaciones",
        blank=True,
    )
    periodo_inicio = models.DateField()
    periodo_fin = models.DateField()
    monto_total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    monto_retencion = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    monto_neto = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    estado = models.CharField(
        max_length=20,
        choices=Estado.choices,
        default=Estado.BORRADOR,
    )
    observaciones = models.TextField(blank=True)
    generada_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Liquidacion profesor"
        verbose_name_plural = "Liquidaciones profesores"
        ordering = ["-periodo_inicio"]

    def __str__(self) -> str:
        return f"{self.profesor} - {self.periodo_inicio} / {self.periodo_fin}"

    def calcular_totales(self):
        Asistencia = apps.get_model("asistencias", "Asistencia")
        asistencias_qs = Asistencia.objects.filter(
            sesion__profesor=self.profesor,
            sesion__fecha__gte=self.periodo_inicio,
            sesion__fecha__lte=self.periodo_fin,
            sesion__disciplina__organizacion=self.organizacion,
        ).select_related("sesion__disciplina")
        total_asistencias = asistencias_qs.count()
        primera_sesion = asistencias_qs.first()
        tarifa = None
        if primera_sesion:
            tarifa = TarifaPagoProfesor.obtener_tarifa_para_fecha(
                self.organizacion,
                primera_sesion.sesion.disciplina,
                primera_sesion.sesion.fecha,
            )
        monto_por_asistente = tarifa.monto_por_sesion if tarifa else TARIFA_DEFECTO
        bruto = (monto_por_asistente * Decimal(total_asistencias)).quantize(Decimal("0.01"))
        retencion = (bruto * RETENCION_PROFESOR).quantize(Decimal("0.01"))
        neto = (bruto - retencion).quantize(Decimal("0.01"))
        self.monto_total = bruto
        self.monto_retencion = retencion
        self.monto_neto = neto
        return total_asistencias


class MovimientoCaja(models.Model):
    class Tipo(models.TextChoices):
        INGRESO = "ingreso", "Ingreso"
        EGRESO = "egreso", "Egreso"

    class Categoria(models.TextChoices):
        TALLERES = "talleres", "Talleres/Clases"
        ARRIENDO = "arriendo", "Arriendo"
        INSUMOS = "insumos", "Insumos"
        HONORARIOS = "honorarios", "Honorarios"
        SERVICIOS = "servicios", "Servicios"
        OTROS = "otros", "Otros"

    organizacion = models.ForeignKey(
        "organizaciones.Organizacion",
        on_delete=models.CASCADE,
        related_name="movimientos_caja",
    )
    tipo = models.CharField(max_length=20, choices=Tipo.choices)
    fecha = models.DateField()
    monto_total = models.DecimalField(max_digits=12, decimal_places=2)
    afecta_iva = models.BooleanField(default=False)
    monto_neto = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    monto_iva = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    categoria = models.CharField(max_length=20, choices=Categoria.choices)
    glosa = models.CharField(max_length=255, blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Movimiento de caja"
        verbose_name_plural = "Movimientos de caja"
        ordering = ["-fecha", "-creado_en"]

    def __str__(self) -> str:
        return f"{self.get_tipo_display()} {self.monto_total} - {self.fecha}"

    def calcular_iva(self):
        monto_total = Decimal(self.monto_total)
        if self.afecta_iva:
            neto = monto_total / (Decimal("1.0") + IVA_RATE)
            iva = monto_total - neto
        else:
            neto = monto_total
            iva = Decimal("0")
        self.monto_neto = neto.quantize(Decimal("0.01"))
        self.monto_iva = iva.quantize(Decimal("0.01"))

    def save(self, *args, **kwargs):
        self.calcular_iva()
        super().save(*args, **kwargs)

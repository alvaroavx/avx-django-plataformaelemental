from django.db import models


class Asistencia(models.Model):
    class Estado(models.TextChoices):
        PRESENTE = "presente", "Presente"
        AUSENTE = "ausente", "Ausente"
        JUSTIFICADA = "justificada", "Justificada"

    class EstadoCobro(models.TextChoices):
        CUBIERTA = "cubierta", "Cubierta"
        DEUDA = "deuda", "Deuda"

    class ModalidadCobro(models.TextChoices):
        PLAN = "plan", "Plan"
        CLASE_NORMAL = "clase_normal", "Clase normal"
        CLASE_ESPECIAL = "clase_especial", "Clase especial"
        BECA = "beca", "Beca"

    sesion = models.ForeignKey(
        "academia.SesionClase",
        on_delete=models.CASCADE,
        related_name="asistencias",
    )
    persona = models.ForeignKey(
        "cuentas.Persona",
        on_delete=models.CASCADE,
        related_name="asistencias",
    )
    pago_plan = models.ForeignKey(
        "cobros.Pago",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asistencias_plan",
    )
    convenio = models.ForeignKey(
        "cobros.ConvenioIntercambio",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asistencias",
    )
    estado = models.CharField(
        max_length=20,
        choices=Estado.choices,
        default=Estado.PRESENTE,
    )
    comentario = models.TextField(blank=True)
    estado_cobro = models.CharField(
        max_length=20,
        choices=EstadoCobro.choices,
        default=EstadoCobro.DEUDA,
    )
    modalidad_cobro = models.CharField(
        max_length=30,
        choices=ModalidadCobro.choices,
        default=ModalidadCobro.CLASE_NORMAL,
    )
    monto_cobro = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    factor_pago_profesor = models.DecimalField(max_digits=6, decimal_places=4, default=1)
    registrada_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Asistencia"
        verbose_name_plural = "Asistencias"
        unique_together = ("sesion", "persona")
        ordering = ["-registrada_en"]

    def __str__(self) -> str:
        return f"{self.persona} - {self.sesion} ({self.estado})"

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        if is_new:
            from cobros.services import imputar_asistencia

            imputar_asistencia(self)

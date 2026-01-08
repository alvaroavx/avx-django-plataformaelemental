from django.db import models


class Asistencia(models.Model):
    class Estado(models.TextChoices):
        PRESENTE = "presente", "Presente"
        AUSENTE = "ausente", "Ausente"
        JUSTIFICADA = "justificada", "Justificada"

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
    suscripcion = models.ForeignKey(
        "cobros.Suscripcion",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asistencias",
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
    registrada_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Asistencia"
        verbose_name_plural = "Asistencias"
        unique_together = ("sesion", "persona")
        ordering = ["-registrada_en"]

    def __str__(self) -> str:
        return f"{self.persona} - {self.sesion} ({self.estado})"

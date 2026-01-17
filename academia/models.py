from django.db import models


class Disciplina(models.Model):
    organizacion = models.ForeignKey(
        "organizaciones.Organizacion",
        on_delete=models.CASCADE,
        related_name="disciplinas",
    )
    nombre = models.CharField(max_length=150)
    descripcion = models.TextField(blank=True)
    nivel = models.CharField(max_length=100, blank=True)
    activa = models.BooleanField(default=True)
    creada_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Disciplina"
        verbose_name_plural = "Disciplinas"
        unique_together = ("organizacion", "nombre", "nivel")
        ordering = ["nombre"]

    def __str__(self) -> str:
        return self.nombre


class BloqueHorario(models.Model):
    class Dia(models.IntegerChoices):
        LUNES = 0, "Lunes"
        MARTES = 1, "Martes"
        MIERCOLES = 2, "Miercoles"
        JUEVES = 3, "Jueves"
        VIERNES = 4, "Viernes"
        SABADO = 5, "Sabado"
        DOMINGO = 6, "Domingo"

    organizacion = models.ForeignKey(
        "organizaciones.Organizacion",
        on_delete=models.CASCADE,
        related_name="bloques_horarios",
    )
    nombre = models.CharField(max_length=150)
    dia_semana = models.IntegerField(choices=Dia.choices)
    hora_inicio = models.TimeField()
    hora_fin = models.TimeField()
    disciplina = models.ForeignKey(
        Disciplina,
        on_delete=models.SET_NULL,
        related_name="bloques",
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = "Bloque horario"
        verbose_name_plural = "Bloques horarios"
        ordering = ["dia_semana", "hora_inicio"]

    def __str__(self) -> str:
        return f"{self.nombre} ({self.get_dia_semana_display()})"


class SesionClase(models.Model):
    class Estado(models.TextChoices):
        PROGRAMADA = "programada", "Programada"
        COMPLETADA = "completada", "Completada"
        CANCELADA = "cancelada", "Cancelada"

    disciplina = models.ForeignKey(
        Disciplina,
        on_delete=models.CASCADE,
        related_name="sesiones",
    )
    bloque = models.ForeignKey(
        BloqueHorario,
        on_delete=models.SET_NULL,
        related_name="sesiones",
        null=True,
        blank=True,
    )
    profesor = models.ForeignKey(
        "cuentas.Persona",
        on_delete=models.SET_NULL,
        related_name="sesiones_impartidas",
        null=True,
        blank=True,
    )
    profesores = models.ManyToManyField(
        "cuentas.Persona",
        related_name="sesiones_en_equipo",
        blank=True,
    )
    fecha = models.DateField()
    estado = models.CharField(
        max_length=20,
        choices=Estado.choices,
        default=Estado.PROGRAMADA,
    )
    cupo_maximo = models.PositiveIntegerField(null=True, blank=True)
    notas = models.TextField(blank=True)
    creada_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Sesion de clase"
        verbose_name_plural = "Sesiones de clase"
        ordering = ["-fecha"]
        indexes = [
            models.Index(fields=["fecha", "disciplina"]),
        ]

    def __str__(self) -> str:
        return f"{self.disciplina} - {self.fecha}"

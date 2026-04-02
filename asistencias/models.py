from django.db import models


class Disciplina(models.Model):
    organizacion = models.ForeignKey(
        "personas.Organizacion",
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
        db_table = "academia_disciplina"

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
        "personas.Organizacion",
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
        db_table = "academia_bloquehorario"

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
    profesores = models.ManyToManyField(
        "personas.Persona",
        related_name="sesiones_en_equipo",
        blank=True,
        db_table="academia_sesionclase_profesores",
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
        db_table = "academia_sesionclase"
        indexes = [
            models.Index(fields=["fecha", "disciplina"]),
        ]

    def __str__(self) -> str:
        return f"{self.disciplina} - {self.fecha}"

    @property
    def profesores_resumen(self):
        return ", ".join([str(persona) for persona in self.profesores.all()])


class Asistencia(models.Model):
    class Estado(models.TextChoices):
        PRESENTE = "presente", "Presente"
        AUSENTE = "ausente", "Ausente"
        JUSTIFICADA = "justificada", "Justificada"

    sesion = models.ForeignKey(
        SesionClase,
        on_delete=models.CASCADE,
        related_name="asistencias",
    )
    persona = models.ForeignKey(
        "personas.Persona",
        on_delete=models.CASCADE,
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
        db_table = "asistencias_asistencia"

    def __str__(self) -> str:
        return f"{self.persona} - {self.sesion} ({self.estado})"

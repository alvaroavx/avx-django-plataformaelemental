from django.conf import settings
from django.db import models


class RelacionOperativaQuerySet(models.QuerySet):
    def operativas(self):
        """Solo relaciones explícitas o históricas revisadas que estén activas."""
        return self.filter(activa=True).filter(
            models.Q(origen="explicita")
            | models.Q(
                origen="historica",
                revisada_en__isnull=False,
                revisada_por__isnull=False,
            )
        )


class Disciplina(models.Model):
    class BadgeColor(models.TextChoices):
        ROJO = "rojo", "Rojo"
        NARANJO = "naranjo", "Naranjo"
        AZUL = "azul", "Azul"
        CELESTE = "celeste", "Celeste"
        AMARILLO = "amarillo", "Amarillo"
        VERDE = "verde", "Verde"
        CAFE = "cafe", "Cafe"
        MORADO = "morado", "Morado"

    BADGE_COLOR_CLASSES = {
        BadgeColor.ROJO: "disciplina-badge-rojo",
        BadgeColor.NARANJO: "disciplina-badge-naranjo",
        BadgeColor.AZUL: "disciplina-badge-azul",
        BadgeColor.CELESTE: "disciplina-badge-celeste",
        BadgeColor.AMARILLO: "disciplina-badge-amarillo",
        BadgeColor.VERDE: "disciplina-badge-verde",
        BadgeColor.CAFE: "disciplina-badge-cafe",
        BadgeColor.MORADO: "disciplina-badge-morado",
    }

    organizacion = models.ForeignKey(
        "personas.Organizacion",
        on_delete=models.CASCADE,
        related_name="disciplinas",
    )
    nombre = models.CharField(max_length=150)
    descripcion = models.TextField(blank=True)
    nivel = models.CharField(max_length=100, blank=True)
    badge_color = models.CharField(
        "color de badge",
        max_length=20,
        choices=BadgeColor.choices,
        default=BadgeColor.AZUL,
    )
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

    @property
    def badge_class(self) -> str:
        return f"disciplina-badge {self.BADGE_COLOR_CLASSES.get(self.badge_color, self.BADGE_COLOR_CLASSES[self.BadgeColor.AZUL])}"

    @classmethod
    def badge_color_options(cls):
        return [
            {
                "value": value,
                "label": label,
                "class": f"disciplina-badge {cls.BADGE_COLOR_CLASSES[value]}",
            }
            for value, label in cls.BadgeColor.choices
        ]


class AsignacionProfesorDisciplina(models.Model):
    """Alcance explícito que habilita a una profesora para operar una disciplina."""

    class Origen(models.TextChoices):
        EXPLICITA = "explicita", "Explícita"
        HISTORICA = "historica", "Inferida desde historia"

    disciplina = models.ForeignKey(
        Disciplina,
        on_delete=models.CASCADE,
        related_name="asignaciones_profesores",
    )
    profesor = models.ForeignKey(
        "personas.Persona",
        on_delete=models.CASCADE,
        related_name="asignaciones_disciplinas",
    )
    activa = models.BooleanField(default=True)
    origen = models.CharField(
        max_length=20,
        choices=Origen.choices,
        default=Origen.EXPLICITA,
    )
    asignada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asignaciones_profesor_disciplina_creadas",
    )
    asignada_en = models.DateTimeField(auto_now_add=True)
    revisada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asignaciones_profesor_disciplina_revisadas",
    )
    revisada_en = models.DateTimeField(null=True, blank=True)

    objects = RelacionOperativaQuerySet.as_manager()

    class Meta:
        verbose_name = "Asignación de profesor a disciplina"
        verbose_name_plural = "Asignaciones de profesores a disciplinas"
        db_table = "asistencias_asignacionprofesordisciplina"
        constraints = [
            models.UniqueConstraint(
                fields=["disciplina", "profesor"],
                name="asistencias_profesor_disciplina_unica",
            )
        ]

    def __str__(self):
        return f"{self.profesor} · {self.disciplina}"


class AlumnoDisciplina(models.Model):
    """Matrícula operativa; limita alumnos visibles y cobrables por disciplina."""

    class Origen(models.TextChoices):
        EXPLICITA = "explicita", "Explícita"
        HISTORICA = "historica", "Inferida desde historia"

    disciplina = models.ForeignKey(
        Disciplina,
        on_delete=models.CASCADE,
        related_name="alumnos_asignados",
    )
    alumno = models.ForeignKey(
        "personas.Persona",
        on_delete=models.CASCADE,
        related_name="disciplinas_asignadas",
    )
    activa = models.BooleanField(default=True)
    origen = models.CharField(
        max_length=20,
        choices=Origen.choices,
        default=Origen.EXPLICITA,
    )
    asignada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asignaciones_alumno_disciplina_creadas",
    )
    asignada_en = models.DateTimeField(auto_now_add=True)
    revisada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asignaciones_alumno_disciplina_revisadas",
    )
    revisada_en = models.DateTimeField(null=True, blank=True)

    objects = RelacionOperativaQuerySet.as_manager()

    class Meta:
        verbose_name = "Alumno de disciplina"
        verbose_name_plural = "Alumnos de disciplinas"
        db_table = "asistencias_alumnodisciplina"
        constraints = [
            models.UniqueConstraint(
                fields=["disciplina", "alumno"],
                name="asistencias_alumno_disciplina_unico",
            )
        ]

    def __str__(self):
        return f"{self.alumno} · {self.disciplina}"


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
        PROGRAMADA = "programada", "Planificada"
        ABIERTA = "abierta", "Abierta"
        COMPLETADA = "completada", "Cerrada"
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


class LiberacionSesion(models.Model):
    """Cancelación auditable de una sesión propia, sin eliminar su historia."""

    sesion = models.OneToOneField(
        SesionClase,
        on_delete=models.PROTECT,
        related_name="liberacion_operativa",
    )
    motivo = models.TextField()
    liberada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="sesiones_liberadas",
    )
    liberada_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Liberación de sesión"
        verbose_name_plural = "Liberaciones de sesiones"
        db_table = "asistencias_liberacionsesion"

    def __str__(self):
        return f"Liberación de sesión {self.sesion_id}"


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


class ClaseLiberada(models.Model):
    asistencia = models.OneToOneField(
        Asistencia,
        on_delete=models.CASCADE,
        related_name="clase_liberada",
    )
    organizacion = models.ForeignKey(
        "personas.Organizacion",
        on_delete=models.PROTECT,
        related_name="clases_liberadas",
    )
    motivo = models.TextField()
    liberada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="clases_liberadas_registradas",
    )
    liberada_en = models.DateTimeField(auto_now_add=True)
    revertida_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="clases_liberadas_revertidas",
    )
    revertida_en = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Clase liberada"
        verbose_name_plural = "Clases liberadas"
        db_table = "asistencias_claseliberada"

    @property
    def activa(self):
        return self.revertida_en is None

    def __str__(self):
        estado = "activa" if self.activa else "revertida"
        return f"Clase liberada {self.asistencia_id} ({estado})"

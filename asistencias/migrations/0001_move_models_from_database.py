import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("database", "0002_organizacion_es_exenta_iva"),
        ("personas", "0001_initial"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.CreateModel(
                    name="Disciplina",
                    fields=[
                        ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                        ("nombre", models.CharField(max_length=150)),
                        ("descripcion", models.TextField(blank=True)),
                        ("nivel", models.CharField(blank=True, max_length=100)),
                        ("activa", models.BooleanField(default=True)),
                        ("creada_en", models.DateTimeField(auto_now_add=True)),
                        (
                            "organizacion",
                            models.ForeignKey(
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name="disciplinas",
                                to="personas.organizacion",
                            ),
                        ),
                    ],
                    options={
                        "verbose_name": "Disciplina",
                        "verbose_name_plural": "Disciplinas",
                        "db_table": "academia_disciplina",
                        "ordering": ["nombre"],
                        "unique_together": {("organizacion", "nombre", "nivel")},
                    },
                ),
                migrations.CreateModel(
                    name="BloqueHorario",
                    fields=[
                        ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                        ("nombre", models.CharField(max_length=150)),
                        ("dia_semana", models.IntegerField(choices=[(0, "Lunes"), (1, "Martes"), (2, "Miercoles"), (3, "Jueves"), (4, "Viernes"), (5, "Sabado"), (6, "Domingo")])),
                        ("hora_inicio", models.TimeField()),
                        ("hora_fin", models.TimeField()),
                        (
                            "disciplina",
                            models.ForeignKey(
                                blank=True,
                                null=True,
                                on_delete=django.db.models.deletion.SET_NULL,
                                related_name="bloques",
                                to="asistencias.disciplina",
                            ),
                        ),
                        (
                            "organizacion",
                            models.ForeignKey(
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name="bloques_horarios",
                                to="personas.organizacion",
                            ),
                        ),
                    ],
                    options={
                        "verbose_name": "Bloque horario",
                        "verbose_name_plural": "Bloques horarios",
                        "db_table": "academia_bloquehorario",
                        "ordering": ["dia_semana", "hora_inicio"],
                    },
                ),
                migrations.CreateModel(
                    name="SesionClase",
                    fields=[
                        ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                        ("fecha", models.DateField()),
                        ("estado", models.CharField(choices=[("programada", "Programada"), ("completada", "Completada"), ("cancelada", "Cancelada")], default="programada", max_length=20)),
                        ("cupo_maximo", models.PositiveIntegerField(blank=True, null=True)),
                        ("notas", models.TextField(blank=True)),
                        ("creada_en", models.DateTimeField(auto_now_add=True)),
                        (
                            "bloque",
                            models.ForeignKey(
                                blank=True,
                                null=True,
                                on_delete=django.db.models.deletion.SET_NULL,
                                related_name="sesiones",
                                to="asistencias.bloquehorario",
                            ),
                        ),
                        (
                            "disciplina",
                            models.ForeignKey(
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name="sesiones",
                                to="asistencias.disciplina",
                            ),
                        ),
                        (
                            "profesores",
                            models.ManyToManyField(
                                blank=True,
                                db_table="academia_sesionclase_profesores",
                                related_name="sesiones_en_equipo",
                                to="personas.persona",
                            ),
                        ),
                    ],
                    options={
                        "verbose_name": "Sesion de clase",
                        "verbose_name_plural": "Sesiones de clase",
                        "db_table": "academia_sesionclase",
                        "ordering": ["-fecha"],
                    },
                ),
                migrations.CreateModel(
                    name="Asistencia",
                    fields=[
                        ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                        ("estado", models.CharField(choices=[("presente", "Presente"), ("ausente", "Ausente"), ("justificada", "Justificada")], default="presente", max_length=20)),
                        ("comentario", models.TextField(blank=True)),
                        ("registrada_en", models.DateTimeField(auto_now_add=True)),
                        (
                            "persona",
                            models.ForeignKey(
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name="asistencias",
                                to="personas.persona",
                            ),
                        ),
                        (
                            "sesion",
                            models.ForeignKey(
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name="asistencias",
                                to="asistencias.sesionclase",
                            ),
                        ),
                    ],
                    options={
                        "verbose_name": "Asistencia",
                        "verbose_name_plural": "Asistencias",
                        "db_table": "asistencias_asistencia",
                        "ordering": ["-registrada_en"],
                        "unique_together": {("sesion", "persona")},
                    },
                ),
                migrations.AddIndex(
                    model_name="sesionclase",
                    index=models.Index(fields=["fecha", "disciplina"], name="academia_se_fecha_15bde7_idx"),
                ),
            ],
        ),
    ]

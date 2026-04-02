import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("database", "0002_organizacion_es_exenta_iva"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.CreateModel(
                    name="Organizacion",
                    fields=[
                        ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                        ("nombre", models.CharField(max_length=255)),
                        ("razon_social", models.CharField(blank=True, max_length=255)),
                        ("rut", models.CharField(max_length=20, unique=True)),
                        (
                            "es_exenta_iva",
                            models.BooleanField(
                                default=False,
                                help_text="Marcar si la organizacion aplica exencion de IVA (Ley 21.622).",
                            ),
                        ),
                        ("email_contacto", models.EmailField(blank=True, max_length=254)),
                        ("telefono_contacto", models.CharField(blank=True, max_length=50)),
                        ("sitio_web", models.URLField(blank=True)),
                        ("direccion", models.CharField(blank=True, max_length=255)),
                        ("creada_en", models.DateTimeField(auto_now_add=True)),
                        ("actualizada_en", models.DateTimeField(auto_now=True)),
                    ],
                    options={
                        "verbose_name": "Organizacion",
                        "verbose_name_plural": "Organizaciones",
                        "db_table": "organizaciones_organizacion",
                        "ordering": ["nombre"],
                    },
                ),
                migrations.CreateModel(
                    name="Persona",
                    fields=[
                        ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                        ("nombres", models.CharField(max_length=150)),
                        ("apellidos", models.CharField(max_length=150)),
                        ("email", models.EmailField(blank=True, max_length=254, null=True, unique=True)),
                        ("telefono", models.CharField(blank=True, max_length=50)),
                        ("identificador", models.CharField(blank=True, max_length=50)),
                        ("fecha_nacimiento", models.DateField(blank=True, null=True)),
                        ("activo", models.BooleanField(default=True)),
                        ("creado_en", models.DateTimeField(auto_now_add=True)),
                        ("actualizado_en", models.DateTimeField(auto_now=True)),
                        (
                            "user",
                            models.OneToOneField(
                                blank=True,
                                null=True,
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name="persona",
                                to=settings.AUTH_USER_MODEL,
                            ),
                        ),
                    ],
                    options={
                        "verbose_name": "Persona",
                        "verbose_name_plural": "Personas",
                        "db_table": "cuentas_persona",
                        "ordering": ["apellidos", "nombres"],
                    },
                ),
                migrations.CreateModel(
                    name="Rol",
                    fields=[
                        ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                        ("nombre", models.CharField(max_length=100, unique=True)),
                        ("codigo", models.SlugField(max_length=50, unique=True)),
                        ("descripcion", models.TextField(blank=True)),
                        ("creado_en", models.DateTimeField(auto_now_add=True)),
                    ],
                    options={
                        "verbose_name": "Rol",
                        "verbose_name_plural": "Roles",
                        "db_table": "cuentas_rol",
                        "ordering": ["nombre"],
                    },
                ),
                migrations.CreateModel(
                    name="PersonaRol",
                    fields=[
                        ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                        ("activo", models.BooleanField(default=True)),
                        ("asignado_en", models.DateField(auto_now_add=True)),
                        (
                            "organizacion",
                            models.ForeignKey(
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name="persona_roles",
                                to="personas.organizacion",
                            ),
                        ),
                        (
                            "persona",
                            models.ForeignKey(
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name="roles",
                                to="personas.persona",
                            ),
                        ),
                        (
                            "rol",
                            models.ForeignKey(
                                on_delete=django.db.models.deletion.PROTECT,
                                related_name="personas",
                                to="personas.rol",
                            ),
                        ),
                    ],
                    options={
                        "verbose_name": "Rol asignado",
                        "verbose_name_plural": "Roles por persona",
                        "db_table": "cuentas_personarol",
                        "unique_together": {("persona", "rol", "organizacion")},
                    },
                ),
            ],
        ),
    ]

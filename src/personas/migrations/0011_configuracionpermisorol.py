from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("personas", "0010_organizacion_comuna_region")]

    operations = [
        migrations.CreateModel(
            name="ConfiguracionPermisoRol",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("capacidad", models.SlugField(max_length=80)),
                ("habilitado", models.BooleanField(default=True)),
                ("actualizado_en", models.DateTimeField(auto_now=True)),
                ("organizacion", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="permisos_por_rol", to="personas.organizacion")),
                ("rol", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="permisos_configurados", to="personas.rol")),
            ],
            options={"verbose_name": "Permiso de producto por rol", "verbose_name_plural": "Permisos de producto por rol", "db_table": "cuentas_configuracion_permisorol"},
        ),
        migrations.AddConstraint(
            model_name="configuracionpermisorol",
            constraint=models.UniqueConstraint(fields=("organizacion", "rol", "capacidad"), name="personas_permiso_rol_org_capacidad_uniq"),
        ),
    ]

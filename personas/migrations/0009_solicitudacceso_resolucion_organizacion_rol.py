from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("personas", "0008_solicitudacceso_excepcion_correo"),
    ]

    operations = [
        migrations.AddField(
            model_name="solicitudacceso",
            name="organizacion_resuelta",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="solicitudes_acceso_resueltas", to="personas.organizacion"),
        ),
        migrations.AddField(
            model_name="solicitudacceso",
            name="rol_resuelto",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="solicitudes_acceso_resueltas", to="personas.rol"),
        ),
    ]

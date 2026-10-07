from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("personas", "0009_solicitudacceso_resolucion_organizacion_rol"),
    ]

    operations = [
        migrations.AddField(
            model_name="organizacion",
            name="comuna",
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddField(
            model_name="organizacion",
            name="region",
            field=models.CharField(blank=True, max_length=120),
        ),
    ]

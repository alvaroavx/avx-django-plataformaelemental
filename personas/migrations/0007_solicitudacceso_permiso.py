from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("personas", "0006_solicitudacceso")]

    operations = [
        migrations.AlterModelOptions(
            name="solicitudacceso",
            options={
                "ordering": ["-creada_en"],
                "permissions": [("gestionar_solicitudes_acceso", "Puede gestionar solicitudes de acceso")],
                "verbose_name": "Solicitud de acceso",
                "verbose_name_plural": "Solicitudes de acceso",
            },
        ),
    ]

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("personas", "0007_solicitudacceso_permiso")]

    operations = [migrations.AddField(model_name="solicitudacceso", name="excepcion_correo_confirmada", field=models.BooleanField(default=False))]

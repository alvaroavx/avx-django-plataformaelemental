from django.db import migrations, models

import personas.validators


class Migration(migrations.Migration):

    dependencies = [
        ("personas", "0001_initial"),
    ]

    operations = [
        migrations.RenameField(
            model_name="persona",
            old_name="identificador",
            new_name="rut",
        ),
        migrations.AlterField(
            model_name="persona",
            name="rut",
            field=models.CharField(blank=True, default="", max_length=20, validators=[personas.validators.validar_rut_chileno]),
        ),
    ]

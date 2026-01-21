from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("academia", "0002_sesionclase_profesores_alter_sesionclase_cupo_maximo"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="sesionclase",
            name="profesor",
        ),
    ]

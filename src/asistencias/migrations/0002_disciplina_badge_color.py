from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("asistencias", "0001_move_models_from_database"),
    ]

    operations = [
        migrations.AddField(
            model_name="disciplina",
            name="badge_color",
            field=models.CharField(
                choices=[
                    ("rojo", "Rojo"),
                    ("naranjo", "Naranjo"),
                    ("azul", "Azul"),
                    ("celeste", "Celeste"),
                    ("amarillo", "Amarillo"),
                    ("verde", "Verde"),
                    ("cafe", "Cafe"),
                    ("morado", "Morado"),
                ],
                default="azul",
                max_length=20,
                verbose_name="color de badge",
            ),
        ),
    ]

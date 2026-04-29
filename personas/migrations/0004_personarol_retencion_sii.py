from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("database", "0005_personarol_retencion_sii"),
        ("personas", "0003_personarol_valor_clase"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.AddField(
                    model_name="personarol",
                    name="retencion_sii",
                    field=models.DecimalField(
                        blank=True,
                        decimal_places=2,
                        default=None,
                        help_text="Porcentaje de retencion SII para honorarios, cuando aplique al rol PROFESOR.",
                        max_digits=5,
                        null=True,
                    ),
                ),
            ],
        ),
    ]

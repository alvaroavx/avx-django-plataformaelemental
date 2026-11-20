from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("personas", "0003_personarol_valor_clase"),
    ]

    operations = [
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
    ]

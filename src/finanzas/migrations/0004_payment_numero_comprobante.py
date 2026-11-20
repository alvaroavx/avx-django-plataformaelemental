from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("finanzas", "0003_repair_missing_tables"),
    ]

    operations = [
        migrations.AddField(
            model_name="payment",
            name="numero_comprobante",
            field=models.CharField(blank=True, default="", max_length=100),
        ),
    ]

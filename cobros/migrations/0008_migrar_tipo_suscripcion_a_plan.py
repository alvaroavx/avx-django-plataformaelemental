from django.db import migrations


def migrar_tipo(apps, schema_editor):
    Pago = apps.get_model("cobros", "Pago")
    Pago.objects.filter(tipo="suscripcion").update(tipo="plan")


class Migration(migrations.Migration):
    dependencies = [
        ("cobros", "0007_alter_pago_tipo"),
    ]

    operations = [
        migrations.RunPython(migrar_tipo, migrations.RunPython.noop),
    ]

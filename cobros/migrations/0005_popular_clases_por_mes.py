from django.db import migrations


def popular_clases_por_mes(apps, schema_editor):
    Plan = apps.get_model("cobros", "Plan")
    for plan in Plan.objects.all():
        if not plan.clases_por_mes:
            plan.clases_por_mes = max(1, (plan.clases_por_semana or 1) * 4)
            plan.save(update_fields=["clases_por_mes"])


class Migration(migrations.Migration):
    dependencies = [
        ("cobros", "0004_pago_clases_total_pago_clases_usadas_pago_plan_and_more"),
    ]

    operations = [
        migrations.RunPython(popular_clases_por_mes, migrations.RunPython.noop),
    ]

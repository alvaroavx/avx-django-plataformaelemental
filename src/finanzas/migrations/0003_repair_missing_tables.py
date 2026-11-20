from django.db import migrations


def create_missing_finanzas_tables(apps, schema_editor):
    existing_tables = set(schema_editor.connection.introspection.table_names())

    model_names = [
        "PaymentPlan",
        "Invoice",
        "Category",
        "Payment",
        "AttendanceConsumption",
        "Transaction",
    ]

    for model_name in model_names:
        model = apps.get_model("finanzas", model_name)
        if model._meta.db_table in existing_tables:
            continue
        schema_editor.create_model(model)
        existing_tables.add(model._meta.db_table)


class Migration(migrations.Migration):
    dependencies = [
        ("finanzas", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(create_missing_finanzas_tables, migrations.RunPython.noop),
    ]

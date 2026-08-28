from django.db import migrations, models


RELACIONES = (
    "asistencias_asignacionprofesordisciplina",
    "asistencias_alumnodisciplina",
)


def reconciliar_relaciones_activas(apps, schema_editor):
    connection = schema_editor.connection
    quote = schema_editor.quote_name
    tablas = set(connection.introspection.table_names())
    for tabla in RELACIONES:
        if tabla not in tablas:
            continue
        with connection.cursor() as cursor:
            cursor.execute(
                f"UPDATE {quote(tabla)} SET {quote('origen')} = 'reconciliada' "
                f"WHERE {quote('activa')} AND {quote('origen')} = 'historica'"
            )


class Migration(migrations.Migration):
    dependencies = [("asistencias", "0006_merge_0004b_y_0005")]

    operations = [
        migrations.AlterField(
            model_name="asignacionprofesordisciplina",
            name="origen",
            field=models.CharField(
                choices=[
                    ("explicita", "Explícita"),
                    ("historica", "Inferida desde historia"),
                    ("reconciliada", "Reconciliada técnicamente"),
                ],
                default="explicita",
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name="alumnodisciplina",
            name="origen",
            field=models.CharField(
                choices=[
                    ("explicita", "Explícita"),
                    ("historica", "Inferida desde historia"),
                    ("reconciliada", "Reconciliada técnicamente"),
                ],
                default="explicita",
                max_length=20,
            ),
        ),
        migrations.RunPython(reconciliar_relaciones_activas, migrations.RunPython.noop),
    ]

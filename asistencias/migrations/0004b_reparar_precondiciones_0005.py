from django.db import migrations


RELACIONES = (
    "asistencias_asignacionprofesordisciplina",
    "asistencias_alumnodisciplina",
)


def _columnas(connection, cursor, tabla):
    return {
        columna.name
        for columna in connection.introspection.get_table_description(cursor, tabla)
    }


def reparar_precondiciones_0005(apps, schema_editor):
    """Normaliza un esquema parcialmente preparado sin activar relaciones."""

    connection = schema_editor.connection
    quote = schema_editor.quote_name
    tablas = set(connection.introspection.table_names())

    for tabla in RELACIONES:
        if tabla not in tablas:
            continue

        with connection.cursor() as cursor:
            columnas = _columnas(connection, cursor, tabla)
            if "origen" not in columnas:
                cursor.execute(
                    f"ALTER TABLE {quote(tabla)} ADD COLUMN {quote('origen')} varchar(20)"
                )

            # Las relaciones activas históricas se conservan operativas y se
            # identifican honestamente como reconciliadas por esta reparación.
            # Las inactivas permanecen históricas; nunca se inventa un actor.
            cursor.execute(
                f"""
                UPDATE {quote(tabla)}
                   SET {quote('origen')} = CASE
                       WHEN {quote('asignada_por_id')} IS NOT NULL THEN 'explicita'
                       WHEN {quote('activa')} THEN 'reconciliada'
                       ELSE 'historica'
                   END
                 WHERE {quote('origen')} IS NULL
                    OR {quote('origen')} NOT IN ('historica', 'explicita')
                    OR ({quote('origen')} = 'explicita'
                        AND {quote('asignada_por_id')} IS NULL)
                """
            )
            cursor.execute(
                f"ALTER TABLE {quote(tabla)} ALTER COLUMN {quote('origen')} "
                "SET DEFAULT 'explicita'"
            )
            cursor.execute(
                f"ALTER TABLE {quote(tabla)} ALTER COLUMN {quote('origen')} SET NOT NULL"
            )


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("asistencias", "0004_alter_sesionclase_estado_liberacionsesion_and_more"),
    ]

    operations = [
        migrations.RunPython(reparar_precondiciones_0005, migrations.RunPython.noop),
    ]

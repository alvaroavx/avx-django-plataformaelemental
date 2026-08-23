"""Replacement forward migration that orders the published 0005 after 0004b."""

from django.conf import settings
from django.db import migrations


RELACIONES = (
    ("asistencias_asignacionprofesordisciplina", "asist_asig_prof"),
    ("asistencias_alumnodisciplina", "asist_alumno_disc"),
)


def _columnas(connection, cursor, tabla):
    return {
        columna.name
        for columna in connection.introspection.get_table_description(cursor, tabla)
    }


def _constraints(connection, cursor, tabla):
    return connection.introspection.get_constraints(cursor, tabla)


def reparar_schema_0004_precommit(apps, schema_editor):
    User = apps.get_model(*settings.AUTH_USER_MODEL.split("."))
    connection = schema_editor.connection
    quote = schema_editor.quote_name
    tablas = set(connection.introspection.table_names())
    for tabla, prefijo in RELACIONES:
        if tabla not in tablas:
            continue
        with connection.cursor() as cursor:
            columnas = _columnas(connection, cursor, tabla)
            if "origen" not in columnas:
                cursor.execute(f"ALTER TABLE {quote(tabla)} ADD COLUMN {quote('origen')} varchar(20)")
                cursor.execute(
                    f"UPDATE {quote(tabla)} SET {quote('origen')} = CASE WHEN {quote('asignada_por_id')} IS NOT NULL THEN 'explicita' ELSE 'historica' END"
                )
                cursor.execute(f"UPDATE {quote(tabla)} SET {quote('activa')} = false WHERE {quote('origen')} = 'historica'")
                cursor.execute(f"ALTER TABLE {quote(tabla)} ALTER COLUMN {quote('origen')} SET DEFAULT 'explicita'")
                cursor.execute(f"ALTER TABLE {quote(tabla)} ALTER COLUMN {quote('origen')} SET NOT NULL")
            if "revisada_en" not in columnas:
                cursor.execute(f"ALTER TABLE {quote(tabla)} ADD COLUMN {quote('revisada_en')} timestamp with time zone NULL")
            if "revisada_por_id" not in columnas:
                cursor.execute(f"ALTER TABLE {quote(tabla)} ADD COLUMN {quote('revisada_por_id')} integer NULL")
            constraints = _constraints(connection, cursor, tabla)
            indice = f"{prefijo}_revisada_por_idx"
            if not any(data.get("index") and data.get("columns") == ["revisada_por_id"] for data in constraints.values()):
                cursor.execute(f"CREATE INDEX {quote(indice)} ON {quote(tabla)} ({quote('revisada_por_id')})")
            foreign_key = f"{prefijo}_revisada_por_fk"
            if not any(
                data.get("foreign_key") == (User._meta.db_table, "id")
                and data.get("columns") == ["revisada_por_id"]
                for data in constraints.values()
            ):
                cursor.execute(
                    f"ALTER TABLE {quote(tabla)} ADD CONSTRAINT {quote(foreign_key)} "
                    f"FOREIGN KEY ({quote('revisada_por_id')}) REFERENCES {quote(User._meta.db_table)} ({quote('id')}) "
                    "DEFERRABLE INITIALLY DEFERRED"
                )


class Migration(migrations.Migration):
    atomic = False
    replaces = [("asistencias", "0005_reparar_schema_0004_aplicada_precommit")]
    dependencies = [("asistencias", "0004b_reparar_precondiciones_0005")]
    operations = [migrations.RunPython(reparar_schema_0004_precommit, migrations.RunPython.noop)]

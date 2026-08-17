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


def _reparar_relacion(*, schema_editor, tabla, prefijo, tabla_usuario):
    connection = schema_editor.connection
    qn = schema_editor.quote_name
    with connection.cursor() as cursor:
        columnas = _columnas(connection, cursor, tabla)
        origen_faltaba = "origen" not in columnas
        if origen_faltaba:
            cursor.execute(
                f"ALTER TABLE {qn(tabla)} ADD COLUMN {qn('origen')} varchar(20)"
            )
        if "revisada_en" not in columnas:
            cursor.execute(
                f"ALTER TABLE {qn(tabla)} ADD COLUMN {qn('revisada_en')} timestamp with time zone NULL"
            )
        if "revisada_por_id" not in columnas:
            cursor.execute(
                f"ALTER TABLE {qn(tabla)} ADD COLUMN {qn('revisada_por_id')} integer NULL"
            )

        if origen_faltaba:
            # La versión precommit de 0004 no guardaba origen. Solo una relación
            # con actor administrativo explícito puede conservarse operativa.
            cursor.execute(
                f"""
                UPDATE {qn(tabla)}
                   SET {qn('origen')} = CASE
                       WHEN {qn('asignada_por_id')} IS NOT NULL THEN 'explicita'
                       ELSE 'historica'
                   END
                """
            )
            cursor.execute(
                f"UPDATE {qn(tabla)} SET {qn('activa')} = false "
                f"WHERE {qn('origen')} = 'historica'"
            )
            cursor.execute(
                f"ALTER TABLE {qn(tabla)} ALTER COLUMN {qn('origen')} SET DEFAULT 'explicita'"
            )
            cursor.execute(
                f"ALTER TABLE {qn(tabla)} ALTER COLUMN {qn('origen')} SET NOT NULL"
            )

        constraints = _constraints(connection, cursor, tabla)
        indice = f"{prefijo}_revisada_por_idx"
        if not any(
            datos.get("index") and datos.get("columns") == ["revisada_por_id"]
            for datos in constraints.values()
        ):
            cursor.execute(
                f"CREATE INDEX {qn(indice)} ON {qn(tabla)} ({qn('revisada_por_id')})"
            )
        foreign_key = f"{prefijo}_revisada_por_fk"
        if not any(
            datos.get("foreign_key") == (tabla_usuario, "id")
            and datos.get("columns") == ["revisada_por_id"]
            for datos in constraints.values()
        ):
            cursor.execute(
                f"ALTER TABLE {qn(tabla)} ADD CONSTRAINT {qn(foreign_key)} "
                f"FOREIGN KEY ({qn('revisada_por_id')}) REFERENCES {qn(tabla_usuario)} ({qn('id')}) "
                "DEFERRABLE INITIALLY DEFERRED"
            )


def reparar_schema_0004_precommit(apps, schema_editor):
    User = apps.get_model(*settings.AUTH_USER_MODEL.split("."))
    tablas = set(schema_editor.connection.introspection.table_names())
    for tabla, prefijo in RELACIONES:
        if tabla not in tablas:
            continue
        _reparar_relacion(
            schema_editor=schema_editor,
            tabla=tabla,
            prefijo=prefijo,
            tabla_usuario=User._meta.db_table,
        )


class Migration(migrations.Migration):
    # PostgreSQL no permite ALTER TABLE después de UPDATEs que dejaron eventos
    # de FK diferidos en la misma transacción. Las operaciones son idempotentes,
    # por lo que un fallo intermedio puede corregirse y reintentarse.
    atomic = False

    dependencies = [
        ("asistencias", "0004_alter_sesionclase_estado_liberacionsesion_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RunPython(
            reparar_schema_0004_precommit,
            migrations.RunPython.noop,
        ),
    ]

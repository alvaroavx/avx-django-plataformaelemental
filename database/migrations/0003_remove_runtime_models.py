from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("personas", "0001_initial"),
        ("asistencias", "0001_move_models_from_database"),
        ("finanzas", "0008_move_relations_to_domain_apps"),
        ("database", "0002_organizacion_es_exenta_iva"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.DeleteModel(name="Asistencia"),
                migrations.DeleteModel(name="SesionClase"),
                migrations.DeleteModel(name="BloqueHorario"),
                migrations.DeleteModel(name="Disciplina"),
                migrations.DeleteModel(name="PersonaRol"),
                migrations.DeleteModel(name="Rol"),
                migrations.DeleteModel(name="Persona"),
                migrations.DeleteModel(name="Organizacion"),
            ],
        ),
    ]

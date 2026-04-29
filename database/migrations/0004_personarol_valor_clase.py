from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("database", "0003_remove_runtime_models"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql="ALTER TABLE cuentas_personarol ADD COLUMN valor_clase decimal(12,2) NULL;",
                    reverse_sql=migrations.RunSQL.noop,
                )
            ],
            state_operations=[],
        ),
    ]

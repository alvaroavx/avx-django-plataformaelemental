from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("database", "0004_personarol_valor_clase"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql="ALTER TABLE cuentas_personarol ADD COLUMN retencion_sii decimal(5,2) NULL;",
                    reverse_sql=migrations.RunSQL.noop,
                )
            ],
            state_operations=[],
        ),
    ]

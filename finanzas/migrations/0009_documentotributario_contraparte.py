from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("personas", "0002_persona_rut"),
        ("finanzas", "0008_move_relations_to_domain_apps"),
    ]

    operations = [
        migrations.AddField(
            model_name="documentotributario",
            name="organizacion_relacionada",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.SET_NULL,
                related_name="documentos_tributarios_relacionados",
                to="personas.organizacion",
            ),
        ),
        migrations.AddField(
            model_name="documentotributario",
            name="persona_relacionada",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.SET_NULL,
                related_name="documentos_tributarios_relacionados",
                to="personas.persona",
            ),
        ),
    ]

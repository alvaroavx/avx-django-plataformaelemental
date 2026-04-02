import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("personas", "0001_initial"),
        ("asistencias", "0001_move_models_from_database"),
        ("finanzas", "0007_paymentplan_es_por_defecto"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.AlterField(
                    model_name="attendanceconsumption",
                    name="asistencia",
                    field=models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="consumo_financiero",
                        to="asistencias.asistencia",
                    ),
                ),
                migrations.AlterField(
                    model_name="attendanceconsumption",
                    name="persona",
                    field=models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="consumos_asistencia",
                        to="personas.persona",
                    ),
                ),
                migrations.AlterField(
                    model_name="documentotributario",
                    name="organizacion",
                    field=models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="documentos_tributarios",
                        to="personas.organizacion",
                    ),
                ),
                migrations.AlterField(
                    model_name="payment",
                    name="organizacion",
                    field=models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="pagos_financieros",
                        to="personas.organizacion",
                    ),
                ),
                migrations.AlterField(
                    model_name="payment",
                    name="persona",
                    field=models.ForeignKey(
                        limit_choices_to={"roles__activo": True, "roles__rol__codigo__iexact": "ESTUDIANTE"},
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="pagos_financieros",
                        to="personas.persona",
                    ),
                ),
                migrations.AlterField(
                    model_name="paymentplan",
                    name="organizacion",
                    field=models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="planes_pago",
                        to="personas.organizacion",
                    ),
                ),
                migrations.AlterField(
                    model_name="transaction",
                    name="organizacion",
                    field=models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="transacciones_financieras",
                        to="personas.organizacion",
                    ),
                ),
            ],
        ),
    ]

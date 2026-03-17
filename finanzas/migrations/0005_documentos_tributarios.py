# Generated manually to preserve existing financial documents while generalizing the model.

import django.db.models.deletion
from decimal import Decimal
from django.db import migrations, models


def migrar_tipos_documento(apps, schema_editor):
    DocumentoTributario = apps.get_model("finanzas", "DocumentoTributario")
    equivalencias = {
        "boleta_servicios": "boleta_venta_afecta",
        "boleta_exenta": "boleta_venta_exenta",
        "factura": "factura_afecta",
        "otro": "otro",
    }
    for documento in DocumentoTributario.objects.all().only("id", "tipo_documento"):
        documento.tipo_documento = equivalencias.get(documento.tipo_documento, documento.tipo_documento)
        documento.save(update_fields=["tipo_documento"])


class Migration(migrations.Migration):

    dependencies = [
        ("database", "0002_organizacion_es_exenta_iva"),
        ("finanzas", "0004_payment_numero_comprobante"),
    ]

    operations = [
        migrations.RenameModel(
            old_name="Invoice",
            new_name="DocumentoTributario",
        ),
        migrations.RenameField(
            model_name="payment",
            old_name="boleta",
            new_name="documento_tributario",
        ),
        migrations.RenameField(
            model_name="documentotributario",
            old_name="tipo",
            new_name="tipo_documento",
        ),
        migrations.RenameField(
            model_name="documentotributario",
            old_name="cliente",
            new_name="nombre_receptor",
        ),
        migrations.RenameField(
            model_name="documentotributario",
            old_name="archivo",
            new_name="archivo_pdf",
        ),
        migrations.AddField(
            model_name="documentotributario",
            name="archivo_xml",
            field=models.FileField(blank=True, null=True, upload_to="finanzas/documentos/xml/"),
        ),
        migrations.AddField(
            model_name="documentotributario",
            name="documento_relacionado",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="documentos_hijos",
                to="finanzas.documentotributario",
            ),
        ),
        migrations.AddField(
            model_name="documentotributario",
            name="fuente",
            field=models.CharField(
                choices=[("manual", "Carga manual"), ("sii", "Importado desde SII")],
                default="manual",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="documentotributario",
            name="iva_tasa",
            field=models.DecimalField(decimal_places=2, default=Decimal("19.00"), max_digits=5),
        ),
        migrations.AddField(
            model_name="documentotributario",
            name="metadata_extra",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="documentotributario",
            name="monto_exento",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=12),
        ),
        migrations.AddField(
            model_name="documentotributario",
            name="nombre_emisor",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="documentotributario",
            name="retencion_monto",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=12),
        ),
        migrations.AddField(
            model_name="documentotributario",
            name="retencion_tasa",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=5),
        ),
        migrations.AddField(
            model_name="documentotributario",
            name="rut_emisor",
            field=models.CharField(blank=True, max_length=20),
        ),
        migrations.AddField(
            model_name="documentotributario",
            name="rut_receptor",
            field=models.CharField(blank=True, max_length=20),
        ),
        migrations.AddField(
            model_name="transaction",
            name="documentos_tributarios",
            field=models.ManyToManyField(blank=True, related_name="transacciones_asociadas", to="finanzas.documentotributario"),
        ),
        migrations.AlterField(
            model_name="documentotributario",
            name="archivo_pdf",
            field=models.FileField(blank=True, null=True, upload_to="finanzas/documentos/pdf/"),
        ),
        migrations.AlterField(
            model_name="documentotributario",
            name="nombre_receptor",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AlterField(
            model_name="documentotributario",
            name="organizacion",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="documentos_tributarios",
                to="database.organizacion",
            ),
        ),
        migrations.AlterField(
            model_name="documentotributario",
            name="tipo_documento",
            field=models.CharField(
                choices=[
                    ("factura_afecta", "Factura afecta"),
                    ("factura_exenta", "Factura exenta"),
                    ("boleta_venta_afecta", "Boleta de venta afecta"),
                    ("boleta_venta_exenta", "Boleta de venta exenta"),
                    ("boleta_honorarios", "Boleta de honorarios"),
                    ("nota_credito", "Nota de credito"),
                    ("nota_debito", "Nota de debito"),
                    ("otro", "Otro"),
                ],
                default="factura_afecta",
                max_length=40,
            ),
        ),
        migrations.AlterField(
            model_name="payment",
            name="documento_tributario",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="pagos_asociados",
                to="finanzas.documentotributario",
            ),
        ),
        migrations.AlterModelOptions(
            name="documentotributario",
            options={
                "verbose_name": "Documento tributario",
                "verbose_name_plural": "Documentos tributarios",
                "ordering": ["-fecha_emision", "-id"],
            },
        ),
        migrations.AlterUniqueTogether(
            name="documentotributario",
            unique_together={("organizacion", "tipo_documento", "folio")},
        ),
        migrations.RunPython(migrar_tipos_documento, migrations.RunPython.noop),
    ]

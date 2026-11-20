import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("personas", "0005_organizacion_logo"),
    ]

    operations = [
        migrations.CreateModel(
            name="SolicitudAcceso",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("provider", models.CharField(default="google", max_length=30)),
                ("provider_subject", models.CharField(max_length=255)),
                ("email", models.EmailField(max_length=254)),
                ("email_normalizado", models.EmailField(max_length=254)),
                ("nombre", models.CharField(blank=True, max_length=255)),
                ("estado", models.CharField(choices=[("PENDIENTE", "Pendiente"), ("APROBADA", "Aprobada"), ("RECHAZADA", "Rechazada")], default="PENDIENTE", max_length=20)),
                ("tipo_resolucion", models.CharField(blank=True, choices=[("USUARIO_EXISTENTE", "Usuario existente"), ("PERSONA_EXISTENTE", "Persona existente"), ("USUARIO_NUEVO", "Usuario nuevo")], max_length=30)),
                ("creada_en", models.DateTimeField(auto_now_add=True)),
                ("resuelta_en", models.DateTimeField(blank=True, null=True)),
                ("nota_interna", models.TextField(blank=True)),
                ("motivo_rechazo", models.TextField(blank=True)),
                ("resuelta_por", models.ForeignKey(blank=True, null=True, on_delete=models.deletion.SET_NULL, related_name="solicitudes_acceso_gestionadas", to=settings.AUTH_USER_MODEL)),
                ("usuario_resuelto", models.ForeignKey(blank=True, null=True, on_delete=models.deletion.SET_NULL, related_name="solicitudes_acceso_resueltas", to=settings.AUTH_USER_MODEL)),
            ],
            options={"verbose_name": "Solicitud de acceso", "verbose_name_plural": "Solicitudes de acceso", "ordering": ["-creada_en"]},
        ),
        migrations.AddIndex(model_name="solicitudacceso", index=models.Index(fields=["estado", "creada_en"], name="solacceso_estado_fecha_idx")),
        migrations.AddIndex(model_name="solicitudacceso", index=models.Index(fields=["provider", "provider_subject"], name="solacceso_provider_sub_idx")),
        migrations.AddIndex(model_name="solicitudacceso", index=models.Index(fields=["email_normalizado"], name="solacceso_email_norm_idx")),
        migrations.AddConstraint(model_name="solicitudacceso", constraint=models.UniqueConstraint(condition=models.Q(("estado", "PENDIENTE")), fields=("provider", "provider_subject"), name="solicitud_acceso_pendiente_provider_subject")),
        migrations.AddConstraint(model_name="solicitudacceso", constraint=models.UniqueConstraint(condition=models.Q(("estado", "PENDIENTE")), fields=("email_normalizado",), name="solicitud_acceso_pendiente_email_normalizado")),
    ]

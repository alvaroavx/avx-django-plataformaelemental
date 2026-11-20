from django.conf import settings
from django.db import models


class AuditLog(models.Model):
    ACCION_CREAR = "crear"
    ACCION_EDITAR = "editar"
    ACCION_ELIMINAR = "eliminar"
    ACCION_ASOCIAR = "asociar"
    ACCION_CAMBIAR_ESTADO = "cambiar_estado"
    ACCION_IMPORTAR = "importar"
    ACCION_AGREGAR_ASISTENTES = "agregar_asistentes"

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="audit_logs",
    )
    fecha = models.DateTimeField(auto_now_add=True)
    accion = models.CharField(max_length=50)
    dominio = models.CharField(max_length=50)
    modelo = models.CharField(max_length=100)
    objeto_id = models.CharField(max_length=100)
    organizacion = models.ForeignKey(
        "personas.Organizacion",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="audit_logs",
    )
    resumen = models.TextField()
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-fecha"]
        indexes = [
            models.Index(fields=["dominio", "modelo", "objeto_id"]),
            models.Index(fields=["organizacion", "fecha"]),
            models.Index(fields=["usuario", "fecha"]),
        ]
        verbose_name = "registro de auditoria"
        verbose_name_plural = "registros de auditoria"

    def __str__(self):
        return f"{self.fecha:%Y-%m-%d %H:%M} {self.dominio}.{self.accion} {self.modelo}:{self.objeto_id}"

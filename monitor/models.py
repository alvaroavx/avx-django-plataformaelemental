from urllib.parse import urlparse

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class Proyecto(models.Model):
    nombre = models.CharField(max_length=200)
    descripcion = models.TextField(blank=True)
    organizacion = models.ForeignKey(
        "personas.Organizacion",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="monitor_proyectos",
    )
    activo = models.BooleanField(default=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Proyecto"
        verbose_name_plural = "Proyectos"
        ordering = ["nombre"]

    def __str__(self) -> str:
        return self.nombre


class Sitio(models.Model):
    ESTADO_PENDIENTE = "pendiente"
    ESTADO_ACTIVO = "activo"
    ESTADO_ADVERTENCIA = "advertencia"
    ESTADO_ERROR = "error"
    ESTADOS = [
        (ESTADO_PENDIENTE, "Pendiente"),
        (ESTADO_ACTIVO, "Activo"),
        (ESTADO_ADVERTENCIA, "Advertencia"),
        (ESTADO_ERROR, "Error"),
    ]

    proyecto = models.ForeignKey(Proyecto, on_delete=models.CASCADE, related_name="sitios")
    nombre = models.CharField(max_length=200)
    url = models.URLField(max_length=500)
    dominio = models.CharField(max_length=255, blank=True)
    activo = models.BooleanField(default=True)
    ultimo_estado = models.CharField(
        max_length=20,
        choices=ESTADOS,
        default=ESTADO_PENDIENTE,
    )
    ultimo_check_en = models.DateTimeField(null=True, blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Sitio"
        verbose_name_plural = "Sitios"
        ordering = ["nombre"]
        constraints = [
            models.UniqueConstraint(
                fields=["proyecto", "url"],
                name="monitor_sitio_unico_por_proyecto_url",
            ),
        ]

    def __str__(self) -> str:
        return self.nombre

    def save(self, *args, **kwargs):
        self.dominio = urlparse(self.url).netloc.lower()
        super().save(*args, **kwargs)


class ConfiguracionMonitor(models.Model):
    timeout_segundos = models.PositiveSmallIntegerField(
        default=10,
        validators=[MinValueValidator(1), MaxValueValidator(60)],
    )
    frecuencia_minutos = models.PositiveSmallIntegerField(
        default=60,
        validators=[MinValueValidator(5), MaxValueValidator(1440)],
    )
    seguir_redirecciones = models.BooleanField(default=True)
    user_agent = models.CharField(
        max_length=200,
        default="Plataforma Elemental Monitor/1.0",
    )
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Configuracion de monitor"
        verbose_name_plural = "Configuracion de monitor"

    def __str__(self) -> str:
        return "Configuracion global de monitor"

    @classmethod
    def actual(cls):
        configuracion, _ = cls.objects.get_or_create(pk=1)
        return configuracion


class ConfiguracionSitio(models.Model):
    sitio = models.OneToOneField(Sitio, on_delete=models.CASCADE, related_name="configuracion")
    timeout_segundos = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(60)],
    )
    frecuencia_minutos = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(5), MaxValueValidator(1440)],
    )
    seguir_redirecciones = models.BooleanField(null=True, blank=True)
    activo = models.BooleanField(default=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Configuracion de sitio"
        verbose_name_plural = "Configuraciones de sitio"

    def __str__(self) -> str:
        return f"Configuracion de {self.sitio}"

    def timeout_resuelto(self, global_config: ConfiguracionMonitor) -> int:
        return self.timeout_segundos or global_config.timeout_segundos

    def frecuencia_resuelta(self, global_config: ConfiguracionMonitor) -> int:
        return self.frecuencia_minutos or global_config.frecuencia_minutos

    def seguir_redirecciones_resuelto(self, global_config: ConfiguracionMonitor) -> bool:
        if self.seguir_redirecciones is None:
            return global_config.seguir_redirecciones
        return self.seguir_redirecciones


class DiscoverySitio(models.Model):
    sitio = models.ForeignKey(Sitio, on_delete=models.CASCADE, related_name="discoveries")
    estado_http = models.PositiveSmallIntegerField(null=True, blank=True)
    url_final = models.URLField(max_length=500, blank=True)
    titulo = models.CharField(max_length=255, blank=True)
    meta_description = models.TextField(blank=True)
    ssl_valido = models.BooleanField(null=True, blank=True)
    tiempo_respuesta_ms = models.PositiveIntegerField(null=True, blank=True)
    error = models.TextField(blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Discovery de sitio"
        verbose_name_plural = "Discoveries de sitio"
        ordering = ["-creado_en"]

    def __str__(self) -> str:
        return f"Discovery de {self.sitio} ({self.creado_en:%Y-%m-%d %H:%M})"

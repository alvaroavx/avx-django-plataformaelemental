from django.db import models


class Organizacion(models.Model):
    nombre = models.CharField(max_length=255)
    razon_social = models.CharField(max_length=255, blank=True)
    rut = models.CharField(max_length=20, unique=True)
    email_contacto = models.EmailField(blank=True)
    telefono_contacto = models.CharField(max_length=50, blank=True)
    sitio_web = models.URLField(blank=True)
    direccion = models.CharField(max_length=255, blank=True)
    creada_en = models.DateTimeField(auto_now_add=True)
    actualizada_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Organizacion"
        verbose_name_plural = "Organizaciones"
        ordering = ["nombre"]

    def __str__(self) -> str:
        return self.nombre

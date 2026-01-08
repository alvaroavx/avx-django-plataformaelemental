from django.conf import settings
from django.db import models


class Persona(models.Model):
    nombres = models.CharField(max_length=150)
    apellidos = models.CharField(max_length=150)
    email = models.EmailField(unique=True)
    telefono = models.CharField(max_length=50, blank=True)
    identificador = models.CharField(max_length=50, blank=True)
    fecha_nacimiento = models.DateField(null=True, blank=True)
    activo = models.BooleanField(default=True)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="persona",
    )
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Persona"
        verbose_name_plural = "Personas"
        ordering = ["apellidos", "nombres"]

    def __str__(self) -> str:
        return f"{self.nombres} {self.apellidos}".strip()

    @property
    def roles_activos(self):
        return self.roles.filter(activo=True).values_list("rol__codigo", flat=True)

    def tiene_rol(self, codigo):
        return codigo in self.roles.filter(activo=True).values_list("rol__codigo", flat=True)


class Rol(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    codigo = models.SlugField(max_length=50, unique=True)
    descripcion = models.TextField(blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Rol"
        verbose_name_plural = "Roles"
        ordering = ["nombre"]

    def __str__(self) -> str:
        return self.nombre


class PersonaRol(models.Model):
    persona = models.ForeignKey(Persona, on_delete=models.CASCADE, related_name="roles")
    rol = models.ForeignKey(Rol, on_delete=models.PROTECT, related_name="personas")
    organizacion = models.ForeignKey(
        "organizaciones.Organizacion",
        on_delete=models.CASCADE,
        related_name="persona_roles",
    )
    activo = models.BooleanField(default=True)
    asignado_en = models.DateField(auto_now_add=True)

    class Meta:
        verbose_name = "Rol asignado"
        verbose_name_plural = "Roles por persona"
        unique_together = ("persona", "rol", "organizacion")

    def __str__(self) -> str:
        return f"{self.persona} - {self.rol} ({self.organizacion})"

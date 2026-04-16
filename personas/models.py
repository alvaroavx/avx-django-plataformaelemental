from django.conf import settings
from django.db import models

from .validators import formatear_rut_chileno, validar_rut_chileno


class Organizacion(models.Model):
    nombre = models.CharField(max_length=255)
    razon_social = models.CharField(max_length=255, blank=True)
    rut = models.CharField(max_length=20, unique=True)
    es_exenta_iva = models.BooleanField(
        default=False,
        help_text="Marcar si la organizacion aplica exencion de IVA (Ley 21.622).",
    )
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
        db_table = "organizaciones_organizacion"

    def __str__(self) -> str:
        return self.nombre


class Persona(models.Model):
    nombres = models.CharField(max_length=150)
    apellidos = models.CharField(max_length=150)
    email = models.EmailField(unique=True, null=True, blank=True)
    telefono = models.CharField(max_length=50, blank=True)
    rut = models.CharField(
        max_length=20,
        blank=True,
        default="",
        validators=[validar_rut_chileno],
    )
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
        db_table = "cuentas_persona"

    def __str__(self) -> str:
        return f"{self.nombres} {self.apellidos}".strip()

    @property
    def nombre_completo(self) -> str:
        return f"{self.nombres} {self.apellidos}".strip()

    @property
    def roles_activos(self):
        return self.roles.filter(activo=True).values_list("rol__codigo", flat=True)

    def tiene_rol(self, codigo):
        return codigo in self.roles.filter(activo=True).values_list("rol__codigo", flat=True)

    def save(self, *args, **kwargs):
        self.rut = formatear_rut_chileno(self.rut)
        super().save(*args, **kwargs)


class Rol(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    codigo = models.SlugField(max_length=50, unique=True)
    descripcion = models.TextField(blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Rol"
        verbose_name_plural = "Roles"
        ordering = ["nombre"]
        db_table = "cuentas_rol"

    def __str__(self) -> str:
        return self.nombre


class PersonaRol(models.Model):
    persona = models.ForeignKey(Persona, on_delete=models.CASCADE, related_name="roles")
    rol = models.ForeignKey(Rol, on_delete=models.PROTECT, related_name="personas")
    organizacion = models.ForeignKey(
        Organizacion,
        on_delete=models.CASCADE,
        related_name="persona_roles",
    )
    activo = models.BooleanField(default=True)
    asignado_en = models.DateField(auto_now_add=True)

    class Meta:
        verbose_name = "Rol asignado"
        verbose_name_plural = "Roles por persona"
        unique_together = ("persona", "rol", "organizacion")
        db_table = "cuentas_personarol"

    def __str__(self) -> str:
        return f"{self.persona} - {self.rol} ({self.organizacion})"

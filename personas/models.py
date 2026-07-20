from decimal import Decimal
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from .utils import normalizar_telefono, tiene_identidad_minima
from .validators import formatear_rut_chileno, validar_rut_chileno


class Organizacion(models.Model):
    nombre = models.CharField(max_length=255)
    razon_social = models.CharField(max_length=255, blank=True)
    rut = models.CharField(max_length=20, unique=True)
    logo = models.ImageField(upload_to="organizaciones/logos/", blank=True, null=True)
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

    @property
    def iniciales(self) -> str:
        partes = [parte[0] for parte in self.nombre.split() if parte]
        return "".join(partes[:2]).upper() or "EA"


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

    def clean(self):
        super().clean()
        rut = formatear_rut_chileno(self.rut)
        telefono = normalizar_telefono(self.telefono)
        if not tiene_identidad_minima(rut=rut, email=self.email, telefono=telefono):
            raise ValidationError("Debes registrar al menos RUT, email o telefono.")
        if rut and Persona.objects.filter(rut__iexact=rut).exclude(pk=self.pk).exists():
            raise ValidationError({"rut": "Ya existe una persona con este RUT."})

    def save(self, *args, **kwargs):
        self.rut = formatear_rut_chileno(self.rut)
        self.telefono = normalizar_telefono(self.telefono)
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
    valor_clase = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        default=None,
        help_text="Tarifa por asistencia/clase para roles donde aplique, como PROFESOR.",
    )
    retencion_sii = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        default=None,
        help_text="Porcentaje de retencion SII para honorarios, cuando aplique al rol PROFESOR.",
    )
    asignado_en = models.DateField(auto_now_add=True)

    class Meta:
        verbose_name = "Rol asignado"
        verbose_name_plural = "Roles por persona"
        unique_together = ("persona", "rol", "organizacion")
        db_table = "cuentas_personarol"

    def __str__(self) -> str:
        return f"{self.persona} - {self.rol} ({self.organizacion})"

    @property
    def valor_clase_normalizado(self):
        return self.valor_clase if self.valor_clase is not None else Decimal("0")


class SolicitudAcceso(models.Model):
    class Estado(models.TextChoices):
        PENDIENTE = "PENDIENTE", "Pendiente"
        APROBADA = "APROBADA", "Aprobada"
        RECHAZADA = "RECHAZADA", "Rechazada"

    class TipoResolucion(models.TextChoices):
        USUARIO_EXISTENTE = "USUARIO_EXISTENTE", "Usuario existente"
        PERSONA_EXISTENTE = "PERSONA_EXISTENTE", "Persona existente"
        USUARIO_NUEVO = "USUARIO_NUEVO", "Usuario nuevo"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    provider = models.CharField(max_length=30, default="google")
    provider_subject = models.CharField(max_length=255)
    email = models.EmailField()
    email_normalizado = models.EmailField()
    nombre = models.CharField(max_length=255, blank=True)
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.PENDIENTE)
    tipo_resolucion = models.CharField(max_length=30, choices=TipoResolucion.choices, blank=True)
    usuario_resuelto = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="solicitudes_acceso_resueltas"
    )
    organizacion_resuelta = models.ForeignKey(
        Organizacion,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="solicitudes_acceso_resueltas",
    )
    rol_resuelto = models.ForeignKey(
        Rol,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="solicitudes_acceso_resueltas",
    )
    resuelta_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="solicitudes_acceso_gestionadas"
    )
    creada_en = models.DateTimeField(auto_now_add=True)
    resuelta_en = models.DateTimeField(null=True, blank=True)
    nota_interna = models.TextField(blank=True)
    excepcion_correo_confirmada = models.BooleanField(default=False)
    motivo_rechazo = models.TextField(blank=True)

    class Meta:
        verbose_name = "Solicitud de acceso"
        verbose_name_plural = "Solicitudes de acceso"
        ordering = ["-creada_en"]
        constraints = [
            models.UniqueConstraint(
                fields=["provider", "provider_subject"], condition=models.Q(estado="PENDIENTE"), name="solicitud_acceso_pendiente_provider_subject"
            ),
            models.UniqueConstraint(
                fields=["email_normalizado"], condition=models.Q(estado="PENDIENTE"), name="solicitud_acceso_pendiente_email_normalizado"
            ),
        ]
        indexes = [
            models.Index(fields=["estado", "creada_en"], name="solacceso_estado_fecha_idx"),
            models.Index(fields=["provider", "provider_subject"], name="solacceso_provider_sub_idx"),
            models.Index(fields=["email_normalizado"], name="solacceso_email_norm_idx"),
        ]
        permissions = [
            ("gestionar_solicitudes_acceso", "Puede gestionar solicitudes de acceso"),
        ]

    def __str__(self):
        return f"Solicitud {self.provider} {self.estado}"

    def clean(self):
        super().clean()
        self.email_normalizado = (self.email or "").strip().lower()

    def save(self, *args, **kwargs):
        self.email_normalizado = (self.email or "").strip().lower()
        super().save(*args, **kwargs)

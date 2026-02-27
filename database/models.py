from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.db import models
from django.utils import timezone


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


class Disciplina(models.Model):
    organizacion = models.ForeignKey(
        Organizacion,
        on_delete=models.CASCADE,
        related_name="disciplinas",
    )
    nombre = models.CharField(max_length=150)
    descripcion = models.TextField(blank=True)
    nivel = models.CharField(max_length=100, blank=True)
    activa = models.BooleanField(default=True)
    creada_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Disciplina"
        verbose_name_plural = "Disciplinas"
        unique_together = ("organizacion", "nombre", "nivel")
        ordering = ["nombre"]
        db_table = "academia_disciplina"

    def __str__(self) -> str:
        return self.nombre


class BloqueHorario(models.Model):
    class Dia(models.IntegerChoices):
        LUNES = 0, "Lunes"
        MARTES = 1, "Martes"
        MIERCOLES = 2, "Miercoles"
        JUEVES = 3, "Jueves"
        VIERNES = 4, "Viernes"
        SABADO = 5, "Sabado"
        DOMINGO = 6, "Domingo"

    organizacion = models.ForeignKey(
        Organizacion,
        on_delete=models.CASCADE,
        related_name="bloques_horarios",
    )
    nombre = models.CharField(max_length=150)
    dia_semana = models.IntegerField(choices=Dia.choices)
    hora_inicio = models.TimeField()
    hora_fin = models.TimeField()
    disciplina = models.ForeignKey(
        Disciplina,
        on_delete=models.SET_NULL,
        related_name="bloques",
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = "Bloque horario"
        verbose_name_plural = "Bloques horarios"
        ordering = ["dia_semana", "hora_inicio"]
        db_table = "academia_bloquehorario"

    def __str__(self) -> str:
        return f"{self.nombre} ({self.get_dia_semana_display()})"


class SesionClase(models.Model):
    class Estado(models.TextChoices):
        PROGRAMADA = "programada", "Programada"
        COMPLETADA = "completada", "Completada"
        CANCELADA = "cancelada", "Cancelada"

    disciplina = models.ForeignKey(
        Disciplina,
        on_delete=models.CASCADE,
        related_name="sesiones",
    )
    bloque = models.ForeignKey(
        BloqueHorario,
        on_delete=models.SET_NULL,
        related_name="sesiones",
        null=True,
        blank=True,
    )
    profesores = models.ManyToManyField(
        Persona,
        related_name="sesiones_en_equipo",
        blank=True,
        db_table="academia_sesionclase_profesores",
    )
    fecha = models.DateField()
    estado = models.CharField(
        max_length=20,
        choices=Estado.choices,
        default=Estado.PROGRAMADA,
    )
    cupo_maximo = models.PositiveIntegerField(null=True, blank=True)
    notas = models.TextField(blank=True)
    creada_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Sesion de clase"
        verbose_name_plural = "Sesiones de clase"
        ordering = ["-fecha"]
        db_table = "academia_sesionclase"
        indexes = [
            models.Index(fields=["fecha", "disciplina"]),
        ]

    def __str__(self) -> str:
        return f"{self.disciplina} - {self.fecha}"

    @property
    def profesores_resumen(self):
        return ", ".join([str(persona) for persona in self.profesores.all()])


class Asistencia(models.Model):
    class Estado(models.TextChoices):
        PRESENTE = "presente", "Presente"
        AUSENTE = "ausente", "Ausente"
        JUSTIFICADA = "justificada", "Justificada"

    sesion = models.ForeignKey(
        SesionClase,
        on_delete=models.CASCADE,
        related_name="asistencias",
    )
    persona = models.ForeignKey(
        Persona,
        on_delete=models.CASCADE,
        related_name="asistencias",
    )
    estado = models.CharField(
        max_length=20,
        choices=Estado.choices,
        default=Estado.PRESENTE,
    )
    comentario = models.TextField(blank=True)
    registrada_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Asistencia"
        verbose_name_plural = "Asistencias"
        unique_together = ("sesion", "persona")
        ordering = ["-registrada_en"]
        db_table = "asistencias_asistencia"

    def __str__(self) -> str:
        return f"{self.persona} - {self.sesion} ({self.estado})"


IVA_RATE = Decimal("0.19")


def _money(value: Decimal) -> Decimal:
    return (value or Decimal("0")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class TimeStampedModel(models.Model):
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class PaymentPlan(TimeStampedModel):
    organizacion = models.ForeignKey(
        Organizacion,
        on_delete=models.CASCADE,
        related_name="planes_pago",
    )
    nombre = models.CharField(max_length=150)
    num_clases = models.PositiveIntegerField(default=1)
    precio = models.DecimalField(max_digits=12, decimal_places=2)
    precio_incluye_iva = models.BooleanField(default=False)
    fecha_inicio = models.DateField(null=True, blank=True)
    fecha_fin = models.DateField(null=True, blank=True)
    descripcion = models.TextField(blank=True)
    activo = models.BooleanField(default=True)

    class Meta:
        app_label = "finanzas"
        verbose_name = "Plan de pago"
        verbose_name_plural = "Planes de pago"
        ordering = ["organizacion__nombre", "nombre"]
        db_table = "finanzas_paymentplan"
        unique_together = ("organizacion", "nombre")

    def __str__(self) -> str:
        return f"{self.nombre} ({self.organizacion})"

    def calcular_montos(self):
        precio = _money(Decimal(self.precio or 0))
        if self.organizacion.es_exenta_iva:
            return precio, Decimal("0.00"), precio
        if self.precio_incluye_iva:
            total = precio
            neto = _money(total / (Decimal("1.00") + IVA_RATE))
            iva = _money(total - neto)
            return neto, iva, total
        neto = precio
        iva = _money(neto * IVA_RATE)
        total = _money(neto + iva)
        return neto, iva, total


class Invoice(TimeStampedModel):
    class Tipo(models.TextChoices):
        BOLETA_SERVICIOS = "boleta_servicios", "Boleta de servicios"
        BOLETA_EXENTA = "boleta_exenta", "Boleta exenta"
        FACTURA = "factura", "Factura"
        OTRO = "otro", "Otro"

    organizacion = models.ForeignKey(
        Organizacion,
        on_delete=models.CASCADE,
        related_name="boletas_facturas",
    )
    tipo = models.CharField(max_length=30, choices=Tipo.choices, default=Tipo.BOLETA_SERVICIOS)
    folio = models.CharField(max_length=100)
    fecha_emision = models.DateField(default=timezone.localdate)
    cliente = models.CharField(max_length=255, blank=True)
    monto_neto = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    monto_iva = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    monto_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    archivo = models.FileField(upload_to="finanzas/invoices/", null=True, blank=True)
    enlace_sii = models.URLField(blank=True)
    observaciones = models.TextField(blank=True)

    class Meta:
        app_label = "finanzas"
        verbose_name = "Boleta o factura"
        verbose_name_plural = "Boletas y facturas"
        ordering = ["-fecha_emision", "-id"]
        db_table = "finanzas_invoice"
        unique_together = ("organizacion", "tipo", "folio")

    def __str__(self) -> str:
        return f"{self.get_tipo_display()} #{self.folio}"


class Category(TimeStampedModel):
    class Tipo(models.TextChoices):
        INGRESO = "ingreso", "Ingreso"
        EGRESO = "egreso", "Egreso"

    nombre = models.CharField(max_length=150, unique=True)
    tipo = models.CharField(max_length=20, choices=Tipo.choices)
    activa = models.BooleanField(default=True)

    class Meta:
        app_label = "finanzas"
        verbose_name = "Categoria"
        verbose_name_plural = "Categorias"
        ordering = ["tipo", "nombre"]
        db_table = "finanzas_category"

    def __str__(self) -> str:
        return f"{self.nombre} ({self.get_tipo_display()})"


class Payment(TimeStampedModel):
    class Metodo(models.TextChoices):
        EFECTIVO = "efectivo", "Efectivo"
        TRANSFERENCIA = "transferencia", "Transferencia"
        TARJETA = "tarjeta", "Tarjeta"
        OTRO = "otro", "Otro"

    persona = models.ForeignKey(
        Persona,
        on_delete=models.PROTECT,
        related_name="pagos_financieros",
        limit_choices_to={"roles__rol__codigo__iexact": "ESTUDIANTE", "roles__activo": True},
    )
    organizacion = models.ForeignKey(
        Organizacion,
        on_delete=models.CASCADE,
        related_name="pagos_financieros",
    )
    plan = models.ForeignKey(
        PaymentPlan,
        on_delete=models.SET_NULL,
        related_name="pagos",
        null=True,
        blank=True,
    )
    boleta = models.ForeignKey(
        Invoice,
        on_delete=models.SET_NULL,
        related_name="pagos",
        null=True,
        blank=True,
    )
    fecha_pago = models.DateField(default=timezone.localdate)
    metodo_pago = models.CharField(max_length=20, choices=Metodo.choices, default=Metodo.TRANSFERENCIA)
    numero_comprobante = models.CharField(max_length=100, blank=True, default="")
    aplica_iva = models.BooleanField(default=True)
    monto_incluye_iva = models.BooleanField(default=False)
    monto_referencia = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    monto_neto = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    monto_iva = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    monto_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    clases_asignadas = models.PositiveIntegerField(default=0)
    observaciones = models.TextField(blank=True)

    class Meta:
        app_label = "finanzas"
        verbose_name = "Pago"
        verbose_name_plural = "Pagos"
        ordering = ["-fecha_pago", "-id"]
        db_table = "finanzas_payment"
        indexes = [
            models.Index(fields=["fecha_pago", "organizacion"]),
            models.Index(fields=["persona", "fecha_pago"]),
        ]

    def __str__(self) -> str:
        return f"Pago {self.persona} - {self.fecha_pago}"

    def calcular_montos(self):
        base = Decimal(self.monto_referencia or 0)
        if self.plan_id and not base:
            base = Decimal(self.plan.precio)
        base = _money(base)

        aplica_iva = bool(self.aplica_iva) and not self.organizacion.es_exenta_iva
        if not aplica_iva:
            neto = base
            iva = Decimal("0.00")
            total = base
        elif self.monto_incluye_iva or (self.plan_id and self.plan.precio_incluye_iva):
            total = base
            neto = _money(total / (Decimal("1.00") + IVA_RATE))
            iva = _money(total - neto)
        else:
            neto = base
            iva = _money(neto * IVA_RATE)
            total = _money(neto + iva)
        return neto, iva, total

    @property
    def clases_consumidas(self):
        return self.consumos.filter(estado=AttendanceConsumption.Estado.CONSUMIDO).count()

    @property
    def saldo_clases(self):
        return self.clases_asignadas - self.clases_consumidas

    def save(self, *args, **kwargs):
        if self.plan_id and not self.clases_asignadas:
            self.clases_asignadas = self.plan.num_clases
        if self.organizacion.es_exenta_iva:
            self.aplica_iva = False
        neto, iva, total = self.calcular_montos()
        self.monto_neto = neto
        self.monto_iva = iva
        self.monto_total = total
        super().save(*args, **kwargs)


class AttendanceConsumption(TimeStampedModel):
    class Estado(models.TextChoices):
        CONSUMIDO = "consumido", "Consumido"
        PENDIENTE = "pendiente", "Pendiente"
        DEUDA = "deuda", "Deuda"

    asistencia = models.OneToOneField(
        Asistencia,
        on_delete=models.CASCADE,
        related_name="consumo_financiero",
    )
    persona = models.ForeignKey(
        Persona,
        on_delete=models.CASCADE,
        related_name="consumos_asistencia",
    )
    clase_fecha = models.DateField()
    pago = models.ForeignKey(
        Payment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="consumos",
    )
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.PENDIENTE)
    observaciones = models.TextField(blank=True)

    class Meta:
        app_label = "finanzas"
        verbose_name = "Consumo de asistencia"
        verbose_name_plural = "Consumos de asistencia"
        ordering = ["-clase_fecha", "-id"]
        db_table = "finanzas_attendanceconsumption"
        indexes = [
            models.Index(fields=["persona", "clase_fecha"]),
            models.Index(fields=["estado", "clase_fecha"]),
        ]

    def __str__(self) -> str:
        return f"{self.persona} - {self.clase_fecha} ({self.get_estado_display()})"


class Transaction(TimeStampedModel):
    class Tipo(models.TextChoices):
        INGRESO = "ingreso", "Ingreso"
        EGRESO = "egreso", "Egreso"

    organizacion = models.ForeignKey(
        Organizacion,
        on_delete=models.CASCADE,
        related_name="transacciones_financieras",
    )
    categoria = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="transacciones",
    )
    fecha = models.DateField(default=timezone.localdate)
    tipo = models.CharField(max_length=20, choices=Tipo.choices)
    monto = models.DecimalField(max_digits=12, decimal_places=2)
    descripcion = models.TextField(blank=True)
    archivo = models.FileField(upload_to="finanzas/transactions/", null=True, blank=True)

    class Meta:
        app_label = "finanzas"
        verbose_name = "Transaccion"
        verbose_name_plural = "Transacciones"
        ordering = ["-fecha", "-id"]
        db_table = "finanzas_transaction"
        indexes = [
            models.Index(fields=["fecha", "organizacion"]),
            models.Index(fields=["tipo", "fecha"]),
        ]

    def __str__(self) -> str:
        return f"{self.get_tipo_display()} {self.monto} ({self.categoria})"

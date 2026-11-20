import hashlib
import secrets

from django.db import models
from django.utils import timezone


class ApiAccessKey(models.Model):
    nombre = models.CharField(max_length=150, unique=True)
    prefijo = models.CharField(max_length=16, unique=True, editable=False)
    hash_clave = models.CharField(max_length=64, unique=True, editable=False)
    activa = models.BooleanField(default=True)
    descripcion = models.TextField(blank=True)
    creada_en = models.DateTimeField(auto_now_add=True)
    ultimo_uso_en = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "API key"
        verbose_name_plural = "API keys"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre

    @staticmethod
    def construir_hash(clave_plana):
        return hashlib.sha256(clave_plana.encode("utf-8")).hexdigest()

    @classmethod
    def generar_clave_plana(cls):
        prefijo = secrets.token_hex(4)
        secreto = secrets.token_hex(20)
        return f"elm_{prefijo}_{secreto}", prefijo

    @classmethod
    def crear_con_clave(cls, nombre, descripcion=""):
        clave_plana, prefijo = cls.generar_clave_plana()
        instancia = cls.objects.create(
            nombre=nombre,
            descripcion=descripcion,
            prefijo=prefijo,
            hash_clave=cls.construir_hash(clave_plana),
        )
        return instancia, clave_plana

    @classmethod
    def desde_clave_plana(cls, clave_plana):
        if not clave_plana:
            return None
        return cls.objects.filter(
            hash_clave=cls.construir_hash(clave_plana),
            activa=True,
        ).first()

    def registrar_uso(self):
        marca_tiempo = timezone.now()
        self.ultimo_uso_en = marca_tiempo
        self.__class__.objects.filter(pk=self.pk).update(ultimo_uso_en=marca_tiempo)

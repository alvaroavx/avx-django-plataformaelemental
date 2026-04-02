from django.db.models.signals import post_save
from django.dispatch import receiver

from asistencias.models import Asistencia

from .models import Payment
from .services import asignar_consumo_asistencia, imputar_pago_a_deudas


@receiver(post_save, sender=Asistencia)
def crear_consumo_financiero(sender, instance, created, **kwargs):
    if not created:
        return
    asignar_consumo_asistencia(instance)


@receiver(post_save, sender=Payment)
def aplicar_pago_a_consumos_deuda(sender, instance, created, **kwargs):
    if not created:
        return
    imputar_pago_a_deudas(instance)

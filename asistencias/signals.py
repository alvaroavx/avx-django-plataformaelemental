from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import AlumnoDisciplina, Asistencia


@receiver(post_save, sender=Asistencia)
def mantener_matricula_operativa(sender, instance, raw=False, **kwargs):
    """Conserva trazabilidad histórica sin convertir asistencia en matrícula vigente."""
    if raw:
        return
    AlumnoDisciplina.objects.get_or_create(
        disciplina=instance.sesion.disciplina,
        alumno=instance.persona,
        defaults={
            "activa": False,
            "origen": AlumnoDisciplina.Origen.HISTORICA,
        },
    )

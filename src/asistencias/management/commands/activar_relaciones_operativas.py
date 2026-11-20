from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from asistencias.models import AlumnoDisciplina, AsignacionProfesorDisciplina
from asistencias.services import (
    activar_asignaciones_profesor_en_lote,
    activar_matriculas_alumno_en_lote,
)


CONFIRMACION = "ACTIVAR_RELACIONES_REVISADAS"


class Command(BaseCommand):
    help = (
        "Previsualiza o activa por ID relaciones profesor/alumno revisadas. "
        "La activación es atómica, autorizada por organización y auditada."
    )

    def add_arguments(self, parser):
        parser.add_argument("--tipo", choices=("profesor", "alumno"), required=True)
        parser.add_argument("--ids", type=int, nargs="+", required=True)
        parser.add_argument(
            "--actor-username",
            required=True,
            help="Usuario administrador que quedará registrado como actor y revisor.",
        )
        parser.add_argument(
            "--confirmar",
            help=f"Para escribir debe ser exactamente {CONFIRMACION}; sin esta opción solo previsualiza.",
        )

    def handle(self, *args, **options):
        ids = sorted(set(options["ids"]))
        if any(item < 1 for item in ids):
            raise CommandError("Todos los IDs deben ser enteros positivos.")

        if options["tipo"] == "profesor":
            modelo = AsignacionProfesorDisciplina
            servicio = activar_asignaciones_profesor_en_lote
        else:
            modelo = AlumnoDisciplina
            servicio = activar_matriculas_alumno_en_lote

        relaciones = modelo.objects.filter(pk__in=ids)
        encontradas = relaciones.count()
        if encontradas != len(ids):
            raise CommandError(
                f"Se solicitaron {len(ids)} relaciones y solo existen {encontradas}; no se aplicó nada."
            )

        confirmacion = options.get("confirmar")
        if not confirmacion:
            self.stdout.write(
                self.style.WARNING(
                    f"PREVIEW: {encontradas} relaciones tipo={options['tipo']}; no se modificaron datos."
                )
            )
            return
        if confirmacion != CONFIRMACION:
            raise CommandError(f"Confirmación inválida; use exactamente {CONFIRMACION}.")

        User = get_user_model()
        try:
            actor = User.objects.get(username=options["actor_username"], is_active=True)
        except User.DoesNotExist as exc:
            raise CommandError("El actor indicado no existe o no está activo.") from exc

        activadas = servicio(user=actor, relaciones=relaciones)
        self.stdout.write(
            self.style.SUCCESS(
                f"Activación completada: {activadas} relaciones quedaron operativas y auditadas."
            )
        )

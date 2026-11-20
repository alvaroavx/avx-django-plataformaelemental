from django.core.management.base import BaseCommand, CommandError

from finanzas.services.reconciliacion import reconciliar_integridad_dominio


class Command(BaseCommand):
    help = "Diagnostica inconsistencias entre asistencias, consumos y pagos sin modificar datos."

    def handle(self, *args, **options):
        resultado = reconciliar_integridad_dominio()
        self.stdout.write("Reconciliación de integridad de dominio (solo lectura)")
        for tipo, total in resultado["resumen"].items():
            self.stdout.write(f"{tipo}: {total}")
            for referencia in resultado["detalle"][tipo]:
                campos = ", ".join(
                    f"{clave}={valor}" for clave, valor in referencia.items()
                )
                self.stdout.write(f"  - {campos}")
        if not resultado["ok"]:
            raise CommandError("Se encontraron inconsistencias de dominio.")
        self.stdout.write(self.style.SUCCESS("Sin inconsistencias de dominio."))

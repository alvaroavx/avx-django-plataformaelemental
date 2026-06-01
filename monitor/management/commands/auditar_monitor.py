from django.core.management.base import BaseCommand

from monitor.models import ConfiguracionMonitor, ConfiguracionSitio, DiscoverySitio, Proyecto, Sitio


class Command(BaseCommand):
    help = "Cuenta registros de la app monitor archivada sin modificar datos."

    def handle(self, *args, **options):
        modelos = [
            Proyecto,
            Sitio,
            ConfiguracionMonitor,
            ConfiguracionSitio,
            DiscoverySitio,
        ]

        self.stdout.write("Inventario read-only de monitor:")
        for modelo in modelos:
            self.stdout.write(f"- {modelo._meta.label}: {modelo.objects.count()}")

from django.core.management.base import BaseCommand, CommandError

from api.models import ApiAccessKey


class Command(BaseCommand):
    help = "Crea una API key para consultas externas."

    def add_arguments(self, parser):
        parser.add_argument("nombre", type=str)
        parser.add_argument("--descripcion", default="", type=str)

    def handle(self, *args, **options):
        nombre = options["nombre"].strip()
        if not nombre:
            raise CommandError("El nombre es obligatorio.")
        if ApiAccessKey.objects.filter(nombre=nombre).exists():
            raise CommandError("Ya existe una API key con ese nombre.")

        _, clave_plana = ApiAccessKey.crear_con_clave(
            nombre=nombre,
            descripcion=options["descripcion"].strip(),
        )
        self.stdout.write(self.style.SUCCESS("API key creada correctamente."))
        self.stdout.write(clave_plana)

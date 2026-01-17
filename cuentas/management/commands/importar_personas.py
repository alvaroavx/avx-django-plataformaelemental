import re
import unicodedata
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from cuentas.models import Persona


def normalizar_texto(valor: str) -> str:
    valor = unicodedata.normalize("NFKD", valor)
    valor = valor.encode("ascii", "ignore").decode("ascii")
    return valor


def construir_local_part(nombres: str, apellidos: str) -> str:
    base = f"{nombres} {apellidos}".strip().lower()
    base = normalizar_texto(base)
    base = re.sub(r"[^a-z0-9]+", ".", base)
    base = re.sub(r"\.+", ".", base).strip(".")
    return base or "persona"


class Command(BaseCommand):
    help = "Importa personas desde un archivo de texto (una persona por linea)."

    def add_arguments(self, parser):
        parser.add_argument("archivo", help="Ruta al archivo .txt con nombres.")
        parser.add_argument("--dominio", default="example.com", help="Dominio para generar correos.")
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Simula el proceso sin escribir en la base de datos.",
        )

    def handle(self, *args, **options):
        archivo = Path(options["archivo"])
        if not archivo.exists():
            raise CommandError(f"No existe el archivo: {archivo}")

        lineas = [line.strip() for line in archivo.read_text(encoding="utf-8").splitlines()]
        lineas = [re.sub(r"\s+", " ", line) for line in lineas if line]
        if not lineas:
            self.stdout.write("No se encontraron lineas validas para importar.")
            return

        dominio = options["dominio"]
        existentes = set(Persona.objects.values_list("email", flat=True))
        nuevos = []
        emails_generados = []

        for linea in lineas:
            partes = linea.split(" ")
            if len(partes) == 1:
                nombres = partes[0]
                apellidos = ""
            else:
                nombres = " ".join(partes[:-1])
                apellidos = partes[-1]

            local_part = construir_local_part(nombres, apellidos)
            email = f"{local_part}@{dominio}"
            contador = 2
            while email in existentes:
                email = f"{local_part}{contador}@{dominio}"
                contador += 1

            existentes.add(email)
            emails_generados.append(email)
            nuevos.append(
                Persona(
                    nombres=nombres,
                    apellidos=apellidos,
                    email=email,
                    telefono="",
                    identificador="",
                    activo=True,
                )
            )

        total = len(nuevos)
        if options["dry_run"]:
            self.stdout.write(f"Se crearian {total} personas.")
            for email in emails_generados[:10]:
                self.stdout.write(f"- {email}")
            return

        with transaction.atomic():
            Persona.objects.bulk_create(nuevos, batch_size=1000)
        self.stdout.write(f"Personas creadas: {total}")

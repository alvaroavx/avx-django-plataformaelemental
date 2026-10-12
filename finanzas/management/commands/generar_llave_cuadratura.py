import base64
import os
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
)
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = (
        "Genera el par de llaves Ed25519 con que Elemental firma sus envíos a Cuadratura. "
        "Guarda la llave privada (permisos 600) y muestra la pública para registrarla en Cuadratura."
    )

    def add_arguments(self, parser):
        parser.add_argument("--salida", required=True, help="Ruta del archivo PEM de la llave privada (fuera del repo).")
        parser.add_argument("--reemplazar", action="store_true", help="Sobrescribe una llave existente.")

    def handle(self, *args, **options):
        ruta = Path(options["salida"]).expanduser().resolve()
        repo = Path(__file__).resolve().parents[3]
        if ruta.is_relative_to(repo):
            raise CommandError("La llave privada no puede quedar dentro del repositorio.")
        if ruta.exists() and not options["reemplazar"]:
            raise CommandError(f"{ruta} ya existe; use --reemplazar para generar una nueva.")
        llave = Ed25519PrivateKey.generate()
        pem = llave.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption())
        ruta.parent.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(ruta, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(descriptor, "wb") as archivo:
            archivo.write(pem)
        os.chmod(ruta, 0o600)
        publica = base64.b64encode(llave.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)).decode()
        self.stdout.write(f"Llave privada guardada en {ruta} (permisos 600). Configure CUADRATURA_API_PRIVATE_KEY_FILE.")
        self.stdout.write("Llave pública (regístrela en Cuadratura con set_api_client_public_key o create_api_client):")
        self.stdout.write(publica)

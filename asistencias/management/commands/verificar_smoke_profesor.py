import json

from django.conf import settings
from django.contrib.auth import (
    BACKEND_SESSION_KEY,
    HASH_SESSION_KEY,
    SESSION_KEY,
    get_user_model,
)
from django.core.management.base import BaseCommand, CommandError
from django.test import Client, override_settings
from django.urls import reverse

from asistencias.services import rol_profesor_activo
from personas.models import Organizacion


class Command(BaseCommand):
    help = (
        "Verifica sin escrituras persistentes que un usuario PROFESOR obtiene "
        "200 en su organización y 404 en una organización ajena."
    )

    def add_arguments(self, parser):
        parser.add_argument("--username", required=True)
        parser.add_argument("--organizacion-id", required=True, type=int)
        parser.add_argument("--organizacion-ajena-id", required=True, type=int)
        parser.add_argument("--host", required=True)

    def handle(self, *args, **options):
        organizacion_id = options["organizacion_id"]
        organizacion_ajena_id = options["organizacion_ajena_id"]
        host = options["host"].strip().lower()
        if organizacion_id == organizacion_ajena_id:
            raise CommandError("La organización autorizada y la ajena deben ser distintas.")
        if not host or "/" in host or "://" in host:
            raise CommandError("--host debe contener solo el host público, sin esquema ni ruta.")

        user = (
            get_user_model()
            .objects.select_related("persona")
            .filter(username=options["username"], is_active=True)
            .first()
        )
        if not user or not hasattr(user, "persona"):
            raise CommandError("La cuenta de smoke no existe, está inactiva o no tiene Persona.")
        if not Organizacion.objects.filter(pk=organizacion_id).exists():
            raise CommandError("La organización autorizada configurada no existe.")
        if not Organizacion.objects.filter(pk=organizacion_ajena_id).exists():
            raise CommandError("La organización ajena configurada no existe.")
        if not rol_profesor_activo(user, organizacion_id=organizacion_id):
            raise CommandError("La cuenta de smoke no tiene rol PROFESOR activo en la organización autorizada.")
        if rol_profesor_activo(user, organizacion_id=organizacion_ajena_id):
            raise CommandError("La organización configurada como ajena también está autorizada para la cuenta de smoke.")

        with override_settings(
            ALLOWED_HOSTS=[host],
            SESSION_ENGINE="django.contrib.sessions.backends.signed_cookies",
        ):
            client = Client(HTTP_HOST=host)
            session = client.session
            session[SESSION_KEY] = str(user.pk)
            session[BACKEND_SESSION_KEY] = "django.contrib.auth.backends.ModelBackend"
            session[HASH_SESSION_KEY] = user.get_session_auth_hash()
            session.save()
            client.cookies[settings.SESSION_COOKIE_NAME] = session.session_key
            ruta = reverse("profesor:sesiones")
            autorizada = client.get(
                ruta,
                {"organizacion": organizacion_id},
                secure=True,
            )
            ajena = client.get(
                ruta,
                {"organizacion": organizacion_ajena_id},
                secure=True,
            )

        resultado = {
            "ok": autorizada.status_code == 200 and ajena.status_code == 404,
            "ruta": ruta,
            "organizacion_autorizada_status": autorizada.status_code,
            "organizacion_ajena_status": ajena.status_code,
            "sesion_persistente_creada": False,
        }
        self.stdout.write(json.dumps(resultado, sort_keys=True))
        if not resultado["ok"]:
            raise CommandError(
                "Smoke Profesor falló: se esperaba organización autorizada=200 y ajena=404."
            )

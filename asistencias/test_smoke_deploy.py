import io
import json

from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from personas.models import Organizacion, Persona, PersonaRol, Rol


class VerificarSmokeProfesorTests(TestCase):
    def setUp(self):
        self.organizacion = Organizacion.objects.create(
            nombre="Organización smoke autorizada",
            razon_social="Organización smoke autorizada",
            rut="75.810.001-7",
        )
        self.organizacion_ajena = Organizacion.objects.create(
            nombre="Organización smoke ajena",
            razon_social="Organización smoke ajena",
            rut="75.810.002-5",
        )
        self.rol_profesor = Rol.objects.create(
            nombre="Profesor smoke deploy",
            codigo="PROFESOR",
        )
        self.user = get_user_model().objects.create_user("profesor.smoke")
        persona = Persona.objects.create(
            nombres="Profesor",
            apellidos="Smoke",
            email="profesor.smoke@example.test",
            user=self.user,
        )
        PersonaRol.objects.create(
            persona=persona,
            rol=self.rol_profesor,
            organizacion=self.organizacion,
            activo=True,
        )

    def _argumentos(self):
        return {
            "username": self.user.username,
            "organizacion_id": self.organizacion.pk,
            "organizacion_ajena_id": self.organizacion_ajena.pk,
            "host": "apps.example.test",
        }

    def test_smoke_confirma_200_autorizado_y_404_ajeno(self):
        salida = io.StringIO()

        call_command("verificar_smoke_profesor", stdout=salida, **self._argumentos())

        resultado = json.loads(salida.getvalue())
        self.assertTrue(resultado["ok"])
        self.assertEqual(resultado["organizacion_autorizada_status"], 200)
        self.assertEqual(resultado["organizacion_ajena_status"], 404)
        self.assertFalse(resultado["sesion_persistente_creada"])
        self.user.refresh_from_db()
        self.assertIsNone(self.user.last_login)
        self.assertFalse(Session.objects.exists())

    def test_smoke_rechaza_organizacion_ajena_que_tambien_esta_autorizada(self):
        PersonaRol.objects.create(
            persona=self.user.persona,
            rol=self.rol_profesor,
            organizacion=self.organizacion_ajena,
            activo=True,
        )

        with self.assertRaisesMessage(CommandError, "también está autorizada"):
            call_command("verificar_smoke_profesor", **self._argumentos())

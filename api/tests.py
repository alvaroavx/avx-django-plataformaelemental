from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from academia.models import Disciplina, SesionClase
from asistencias.models import Asistencia
from cobros.models import Plan, Suscripcion
from cuentas.models import Persona
from finanzas.models import MovimientoCaja
from organizaciones.models import Organizacion


class HealthEndpointTests(APITestCase):
    def test_health_returns_ok(self):
        url = reverse("api-health")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "ok")
        self.assertIn("timestamp", response.data)


class AuthenticationFlowTests(APITestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username="martina",
            email="martina@example.com",
            password="clave-secreta",
            first_name="Martina",
            last_name="Rios",
        )
        self.login_url = reverse("auth-login")
        self.refresh_url = reverse("auth-refresh")
        self.logout_url = reverse("auth-logout")

    def test_login_returns_token_and_user_payload(self):
        response = self.client.post(
            self.login_url,
            {"username": "martina", "password": "clave-secreta"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("token", response.data)
        self.assertEqual(response.data["user"]["email"], "martina@example.com")

    def test_login_with_invalid_credentials_fails(self):
        response = self.client.post(
            self.login_url,
            {"username": "martina", "password": "otra-clave"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_refresh_rotates_token(self):
        login_response = self.client.post(
            self.login_url,
            {"username": "martina", "password": "clave-secreta"},
            format="json",
        )
        old_token = login_response.data["token"]

        refresh_response = self.client.post(
            self.refresh_url,
            {},
            format="json",
            HTTP_AUTHORIZATION=f"Token {old_token}",
        )

        self.assertEqual(refresh_response.status_code, status.HTTP_200_OK)
        self.assertNotEqual(refresh_response.data["token"], old_token)
        self.assertFalse(Token.objects.filter(key=old_token).exists())

    def test_logout_revokes_token(self):
        login_response = self.client.post(
            self.login_url,
            {"username": "martina", "password": "clave-secreta"},
            format="json",
        )
        token = login_response.data["token"]

        logout_response = self.client.post(
            self.logout_url,
            {},
            format="json",
            HTTP_AUTHORIZATION=f"Token {token}",
        )

        self.assertEqual(logout_response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Token.objects.filter(key=token).exists())


class ApiDataTests(APITestCase):
    def setUp(self):
        self.organizacion = Organizacion.objects.create(
            nombre="Org",
            razon_social="Org SpA",
            rut="44.444.444-4",
        )
        self.profesor = Persona.objects.create(
            nombres="Camila",
            apellidos="Gonzalez",
            email="profe@example.com",
        )
        self.estudiante = Persona.objects.create(
            nombres="Alumno",
            apellidos="Demo",
            email="alumno@example.com",
        )
        self.plan = Plan.objects.create(
            organizacion=self.organizacion,
            nombre="Plan Demo",
            precio=10000,
            duracion_dias=30,
            clases_por_semana=1,
        )
        self.suscripcion = Suscripcion.objects.create(
            persona=self.estudiante,
            plan=self.plan,
            fecha_inicio="2025-01-01",
            fecha_fin="2025-01-30",
        )
        self.disciplina = Disciplina.objects.create(
            organizacion=self.organizacion,
            nombre="Flex",
        )
        self.sesion = SesionClase.objects.create(
            disciplina=self.disciplina,
            profesor=self.profesor,
            fecha="2025-01-15",
        )
        self.asistencia = Asistencia.objects.create(
            sesion=self.sesion,
            persona=self.estudiante,
        )
        MovimientoCaja.objects.create(
            organizacion=self.organizacion,
            tipo=MovimientoCaja.Tipo.INGRESO,
            fecha="2025-01-20",
            monto_total=10000,
            afecta_iva=False,
            categoria=MovimientoCaja.Categoria.TALLERES,
            glosa="Pago demo",
        )
        User = get_user_model()
        self.user = User.objects.create_user(username="apiuser", password="123456")
        token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    def test_list_sesiones(self):
        response = self.client.get("/api/sesiones/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data), 1)

    def test_registrar_asistencia_via_api(self):
        response = self.client.post(
            f"/api/sesiones/{self.sesion.pk}/asistencias/",
            {"persona": self.estudiante.pk, "estado": "presente"},
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_estado_estudiante(self):
        response = self.client.get(f"/api/estudiantes/{self.estudiante.pk}/estado/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("clases_asignadas", response.data)

    def test_reporte_resumen(self):
        response = self.client.get("/api/reportes/resumen/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("total_sesiones", response.data)

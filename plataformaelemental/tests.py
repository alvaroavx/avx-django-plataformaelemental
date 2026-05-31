from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from personas.models import Organizacion, Persona, PersonaRol, Rol


class ElementalAppsUXTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.organizacion = Organizacion.objects.create(
            nombre="Org UX",
            razon_social="Org UX SPA",
            rut="66.666.666-6",
        )
        self.rol_admin = Rol.objects.create(nombre="Administrador", codigo="ADMINISTRADOR")
        self.rol_finanzas = Rol.objects.create(nombre="Finanzas", codigo="FINANZAS")
        self.rol_profesor = Rol.objects.create(nombre="Profesor", codigo="PROFESOR")

        self.user_admin = User.objects.create_user("ux_admin", password="secret123")
        self.persona_admin = Persona.objects.create(
            nombres="Admin",
            apellidos="UX",
            email="uxadmin@example.com",
            user=self.user_admin,
        )
        PersonaRol.objects.create(
            persona=self.persona_admin,
            rol=self.rol_admin,
            organizacion=self.organizacion,
            activo=True,
        )

        self.user_finanzas = User.objects.create_user("ux_finanzas", password="secret123")
        self.persona_finanzas = Persona.objects.create(
            nombres="Finanzas",
            apellidos="UX",
            email="uxfinanzas@example.com",
            user=self.user_finanzas,
        )
        PersonaRol.objects.create(
            persona=self.persona_finanzas,
            rol=self.rol_finanzas,
            organizacion=self.organizacion,
            activo=True,
        )

        self.user_profesor = User.objects.create_user("ux_profesor", password="secret123")
        self.persona_profesor = Persona.objects.create(
            nombres="Profesor",
            apellidos="UX",
            email="uxprofesor@example.com",
            user=self.user_profesor,
        )
        PersonaRol.objects.create(
            persona=self.persona_profesor,
            rol=self.rol_profesor,
            organizacion=self.organizacion,
            activo=True,
        )

        self.user_staff = User.objects.create_user("ux_staff", password="secret123", is_staff=True)
        self.user_sin_roles = User.objects.create_user("ux_sin_roles", password="secret123")

    def test_login_get_renderiza_elemental_apps(self):
        response = self.client.get(reverse("login"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Elemental Apps")
        self.assertContains(response, "Plataforma Elemental")

    def test_login_post_valido_respeta_next(self):
        response = self.client.post(
            f"{reverse('login')}?next=/finanzas/",
            {"username": "ux_admin", "password": "secret123"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/finanzas/")

    def test_login_post_invalido_muestra_error(self):
        response = self.client.post(
            reverse("login"),
            {"username": "ux_admin", "password": "incorrecta"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors)
        self.assertContains(response, "Ingresar")

    def test_dashboard_general_requiere_autenticacion(self):
        response = self.client.get(reverse("elemental_apps"))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)

    def test_dashboard_general_admin_ve_apps_principales(self):
        self.client.force_login(self.user_admin)
        response = self.client.get(
            reverse("elemental_apps"),
            {"periodo_mes": 2, "periodo_anio": 2026, "organizacion": self.organizacion.pk},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Elemental Apps")
        self.assertContains(response, "Personas")
        self.assertContains(response, "Asistencias")
        self.assertContains(response, "Finanzas")
        self.assertNotContains(response, "Monitor")
        self.assertNotContains(response, "API")
        self.assertContains(response, "periodo_mes=2")
        self.assertContains(response, "periodo_anio=2026")
        self.assertContains(response, f"organizacion={self.organizacion.pk}")

    def test_dashboard_general_finanzas_no_ve_admin_ni_personas(self):
        self.client.force_login(self.user_finanzas)
        response = self.client.get(reverse("elemental_apps"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Finanzas")
        self.assertNotContains(response, "Admin")
        self.assertNotContains(response, "Personas")
        self.assertNotContains(response, "Asistencias")

    def test_dashboard_general_profesor_no_ve_finanzas(self):
        self.client.force_login(self.user_profesor)
        response = self.client.get(reverse("elemental_apps"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Finanzas")
        self.assertContains(response, "no tiene accesos operativos visibles")

    def test_dashboard_general_staff_ve_admin(self):
        self.client.force_login(self.user_staff)
        response = self.client.get(reverse("elemental_apps"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Admin")

    def test_sidebar_muestra_links_permitidos_y_preserva_filtros(self):
        self.client.force_login(self.user_admin)
        response = self.client.get(
            reverse("asistencias:dashboard"),
            {"periodo_mes": 3, "periodo_anio": 2026, "organizacion": self.organizacion.pk},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "elementalSidebar")
        self.assertContains(response, "Elemental Apps")
        self.assertContains(response, reverse("finanzas:dashboard"))
        self.assertContains(response, "periodo_mes=3")
        self.assertContains(response, "periodo_anio=2026")
        self.assertContains(response, f"organizacion={self.organizacion.pk}")

    def test_vistas_principales_renderizan_con_shell_responsive(self):
        self.client.force_login(self.user_admin)
        urls = [
            reverse("elemental_apps"),
            reverse("finanzas:dashboard"),
            reverse("asistencias:dashboard"),
            reverse("asistencias:estudiantes_list"),
        ]
        for url in urls:
            response = self.client.get(
                url,
                {"periodo_mes": 2, "periodo_anio": 2026, "organizacion": self.organizacion.pk},
            )
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, "Implementado por AVX")

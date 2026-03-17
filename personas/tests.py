from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from database.models import Disciplina, Organizacion, Payment, Persona, PersonaRol, Rol, SesionClase


class PersonasOrganizacionesTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.org = Organizacion.objects.create(
            nombre="Org Personas",
            razon_social="Org Personas SPA",
            rut="55.555.555-5",
        )
        self.rol_admin = Rol.objects.create(nombre="Administrador", codigo="ADMINISTRADOR")
        self.rol_estudiante = Rol.objects.create(nombre="Estudiante", codigo="ESTUDIANTE")
        self.rol_profesor = Rol.objects.create(nombre="Profesor", codigo="PROFESOR")

        self.user_admin = User.objects.create_user("admin_personas", password="secret123", is_staff=True)
        self.persona_admin = Persona.objects.create(
            nombres="Admin",
            apellidos="Personas",
            email="admin.personas@example.com",
            user=self.user_admin,
        )
        PersonaRol.objects.create(
            persona=self.persona_admin,
            rol=self.rol_admin,
            organizacion=self.org,
            activo=True,
        )
        self.client.force_login(self.user_admin)

        self.estudiante = Persona.objects.create(
            nombres="Ana",
            apellidos="Diaz",
            email="ana.personas@example.com",
        )
        self.profesor = Persona.objects.create(
            nombres="Luis",
            apellidos="Rojas",
            email="luis.personas@example.com",
        )
        PersonaRol.objects.create(
            persona=self.estudiante,
            rol=self.rol_estudiante,
            organizacion=self.org,
            activo=True,
        )
        PersonaRol.objects.create(
            persona=self.profesor,
            rol=self.rol_profesor,
            organizacion=self.org,
            activo=True,
        )
        self.disciplina = Disciplina.objects.create(organizacion=self.org, nombre="Yoga")
        SesionClase.objects.create(
            disciplina=self.disciplina,
            fecha="2026-03-05",
            estado=SesionClase.Estado.COMPLETADA,
        )
        Payment.objects.create(
            persona=self.estudiante,
            organizacion=self.org,
            fecha_pago="2026-03-06",
            metodo_pago=Payment.Metodo.EFECTIVO,
            aplica_iva=False,
            monto_referencia=12000,
            clases_asignadas=2,
        )

    def test_organizaciones_list_muestra_metricas(self):
        response = self.client.get(
            reverse("personas:organizaciones_list"),
            {"periodo_mes": 3, "periodo_anio": 2026, "organizacion": self.org.pk},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Org Personas")
        self.assertContains(response, "Ingresos periodo")
        self.assertEqual(len(response.context["organizaciones"]), 1)

    def test_organizacion_create_redirige_a_detalle_con_filtros(self):
        query = "periodo_mes=3&periodo_anio=2026&organizacion=1"
        response = self.client.post(
            f"{reverse('personas:organizacion_create')}?{query}",
            {
                "nombre": "Org Nueva",
                "razon_social": "Org Nueva SPA",
                "rut": "66.666.666-6",
                "email_contacto": "org@example.com",
                "telefono_contacto": "123",
                "sitio_web": "",
                "direccion": "Direccion 123",
            },
        )

        self.assertEqual(response.status_code, 302)
        nueva = Organizacion.objects.get(nombre="Org Nueva")
        self.assertEqual(
            response.url,
            f"{reverse('personas:organizacion_detail', kwargs={'pk': nueva.pk})}?{query}",
        )

    def test_ruta_organizaciones_sale_de_asistencias(self):
        response = self.client.get("/asistencias/organizaciones/")
        self.assertEqual(response.status_code, 404)

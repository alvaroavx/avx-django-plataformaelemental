from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from asistencias.models import Disciplina, SesionClase
from finanzas.models import Payment

from .forms import PersonaCRMForm
from .models import Organizacion, Persona, PersonaRol, Rol


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
        self.persona_rol_profesor = PersonaRol.objects.create(
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
        self.sesion_profesor = SesionClase.objects.create(
            disciplina=self.disciplina,
            fecha="2026-03-12",
            estado=SesionClase.Estado.COMPLETADA,
        )
        self.sesion_profesor.profesores.set([self.profesor])

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

    def test_persona_detail_estudiante_oculta_bloque_profesor(self):
        response = self.client.get(
            reverse("personas:persona_detail", kwargs={"pk": self.estudiante.pk}),
            {"periodo_mes": 3, "periodo_anio": 2026, "organizacion": self.org.pk},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Perfil estudiante")
        self.assertNotContains(response, "Perfil profesor")
        self.assertContains(response, "Resumen financiero del estudiante")

    def test_persona_detail_profesor_oculta_bloque_estudiante(self):
        self.persona_rol_profesor.valor_clase = 5000
        self.persona_rol_profesor.retencion_sii = 15.25
        self.persona_rol_profesor.save(update_fields=["valor_clase", "retencion_sii"])
        response = self.client.get(
            reverse("personas:persona_detail", kwargs={"pk": self.profesor.pk}),
            {"periodo_mes": 3, "periodo_anio": 2026, "organizacion": self.org.pk},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Perfil profesor")
        self.assertNotContains(response, "Perfil estudiante")
        self.assertContains(response, "Sesiones como profesor")
        self.assertContains(response, "Sesiones completadas")
        self.assertContains(response, "1/1")
        self.assertContains(response, "Pago bruto")
        self.assertContains(response, "$ 0")
        self.assertContains(response, "Retención SII")
        self.assertContains(response, "Monto neto")

    def test_persona_detail_permite_guardar_valor_clase_en_rol_profesor(self):
        query = f"periodo_mes=3&periodo_anio=2026&organizacion={self.org.pk}"
        response = self.client.post(
            f"{reverse('personas:persona_detail', kwargs={'pk': self.profesor.pk})}?{query}",
            {
                "accion": "guardar_configuracion_profesor",
                "persona_rol_id": self.persona_rol_profesor.pk,
                "valor_clase": "5000",
                "retencion_sii": "15.25",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.url,
            f"{reverse('personas:persona_detail', kwargs={'pk': self.profesor.pk})}?{query}",
        )
        self.persona_rol_profesor.refresh_from_db()
        self.assertEqual(self.persona_rol_profesor.valor_clase, 5000)
        self.assertEqual(self.persona_rol_profesor.retencion_sii, 15.25)

    def test_personas_list_filtra_profesor_inactivo_por_persona(self):
        self.profesor.activo = False
        self.profesor.save(update_fields=["activo"])
        self.persona_rol_profesor.activo = False
        self.persona_rol_profesor.save(update_fields=["activo"])

        response = self.client.get(
            reverse("personas:personas_list"),
            {
                "periodo_mes": 3,
                "periodo_anio": 2026,
                "organizacion": self.org.pk,
                "rol": "PROFESOR",
                "estado": "inactivas",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Luis Rojas")
        self.assertContains(response, "Profesor")
        self.assertContains(response, "Inactivo")


class PersonasRutFormTests(TestCase):
    def test_persona_form_valida_y_formatea_rut_chileno(self):
        form = PersonaCRMForm(
            data={
                "nombres": "Julia",
                "apellidos": "Perez",
                "email": "",
                "telefono": "",
                "rut": "12345678-5",
                "fecha_nacimiento": "",
                "activo": "on",
                "user": "",
            }
        )

        self.assertTrue(form.is_valid(), form.errors)
        persona = form.save()
        self.assertEqual(persona.rut, "12.345.678-5")

    def test_persona_form_rechaza_rut_chileno_invalido(self):
        form = PersonaCRMForm(
            data={
                "nombres": "Julia",
                "apellidos": "Perez",
                "email": "",
                "telefono": "",
                "rut": "12.345.678-9",
                "fecha_nacimiento": "",
                "activo": "on",
                "user": "",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("rut", form.errors)

from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from asistencias.forms import PersonaRapidaForm
from asistencias.models import Asistencia, Disciplina, SesionClase
from finanzas.models import AttendanceConsumption, Payment

from .forms import PersonaCRMForm
from .models import Organizacion, Persona, PersonaRol, Rol


TEST_PASSWORD = "not-a-real-test-password"


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

        self.user_admin = User.objects.create_user("admin_personas", password=TEST_PASSWORD, is_staff=True)
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

    def test_logo_organizacion_es_opcional(self):
        field = Organizacion._meta.get_field("logo")

        self.assertTrue(field.blank)
        self.assertTrue(field.null)
        self.assertIsNone(self.org.logo.name)

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

    def test_persona_detail_estudiante_permite_asociar_pago_a_asistencia(self):
        sesion = SesionClase.objects.create(
            disciplina=self.disciplina,
            fecha="2026-03-15",
            estado=SesionClase.Estado.COMPLETADA,
        )
        asistencia = Asistencia.objects.create(sesion=sesion, persona=self.estudiante)
        pago_nuevo = Payment.objects.create(
            persona=self.estudiante,
            organizacion=self.org,
            fecha_pago="2026-03-16",
            metodo_pago=Payment.Metodo.TRANSFERENCIA,
            aplica_iva=False,
            monto_referencia=10000,
            clases_asignadas=1,
        )

        response = self.client.get(
            reverse("personas:persona_detail", kwargs={"pk": self.estudiante.pk}),
            {"periodo_mes": 3, "periodo_anio": 2026, "organizacion": self.org.pk},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Finanzas")
        self.assertContains(response, "Pagada")
        self.assertContains(response, "Asociar")
        self.assertContains(response, 'name="asociar_pago_asistencia" value="1"', html=False)

        query = f"periodo_mes=3&periodo_anio=2026&organizacion={self.org.pk}"
        post_response = self.client.post(
            f"{reverse('personas:persona_detail', kwargs={'pk': self.estudiante.pk})}?{query}",
            {
                "asociar_pago_asistencia": "1",
                "asistencia_id": asistencia.pk,
                "pago_id": pago_nuevo.pk,
            },
        )

        self.assertEqual(post_response.status_code, 302)
        self.assertEqual(
            post_response.url,
            f"{reverse('personas:persona_detail', kwargs={'pk': self.estudiante.pk})}?{query}",
        )
        consumo = AttendanceConsumption.objects.get(asistencia=asistencia)
        self.assertEqual(consumo.estado, AttendanceConsumption.Estado.CONSUMIDO)
        self.assertEqual(consumo.pago, pago_nuevo)

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
        detalle_sesion = (
            f'{reverse("asistencias:sesion_detail", kwargs={"pk": self.sesion_profesor.pk})}'
            f"?periodo_mes=3&periodo_anio=2026&organizacion={self.org.pk}"
        )
        agregar_asistentes = (
            f'{reverse("asistencias:asistencias_list")}'
            f"?periodo_mes=3&periodo_anio=2026&organizacion={self.org.pk}"
            f"&sesion_id={self.sesion_profesor.pk}&open=agregar_asistentes"
        )
        self.assertContains(response, "Acciones")
        self.assertContains(response, "Ver sesión")
        self.assertContains(response, "Agregar asistentes")
        self.assertContains(response, 'name="accion" value="cambiar_estado_sesion"', html=False)
        self.assertContains(response, 'onchange="this.form.submit()"', html=False)
        self.assertNotContains(response, ">Cambiar estado</span>", html=False)
        self.assertContains(response, f'href="{detalle_sesion}"', html=False)
        self.assertContains(response, f'href="{agregar_asistentes}"', html=False)

    def test_persona_detail_profesor_permite_cambiar_estado_de_sesion(self):
        query = f"periodo_mes=3&periodo_anio=2026&organizacion={self.org.pk}"
        response = self.client.post(
            f"{reverse('personas:persona_detail', kwargs={'pk': self.profesor.pk})}?{query}",
            {
                "accion": "cambiar_estado_sesion",
                "sesion_id": self.sesion_profesor.pk,
                "estado": SesionClase.Estado.CANCELADA,
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.url,
            f"{reverse('personas:persona_detail', kwargs={'pk': self.profesor.pk})}?{query}",
        )
        self.sesion_profesor.refresh_from_db()
        self.assertEqual(self.sesion_profesor.estado, SesionClase.Estado.CANCELADA)

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

    def test_personas_list_respeta_organizacion_activa(self):
        otra_org = Organizacion.objects.create(
            nombre="Otra Org Personas",
            razon_social="Otra Org Personas SPA",
            rut="77.777.777-7",
        )
        persona_otra_org = Persona.objects.create(
            nombres="Persona",
            apellidos="Externa",
            email="externa.personas@example.com",
        )
        PersonaRol.objects.create(
            persona=persona_otra_org,
            rol=self.rol_estudiante,
            organizacion=otra_org,
            activo=True,
        )

        response = self.client.get(
            reverse("personas:personas_list"),
            {"periodo_mes": 3, "periodo_anio": 2026, "organizacion": self.org.pk},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ana Diaz")
        self.assertNotContains(response, "Persona Externa")

    def test_personas_list_busqueda_funciona(self):
        response = self.client.get(
            reverse("personas:personas_list"),
            {
                "periodo_mes": 3,
                "periodo_anio": 2026,
                "organizacion": self.org.pk,
                "q": "ana.personas@example.com",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ana Diaz")
        self.assertNotContains(response, "Luis Rojas")
        self.assertEqual(response.context["q"], "ana.personas@example.com")

    def test_personas_list_paginate_en_servidor_y_preserva_filtros(self):
        for index in range(30):
            persona = Persona.objects.create(
                nombres=f"Estudiante {index:02d}",
                apellidos="Paginacion",
                email=f"paginacion{index:02d}@example.com",
            )
            PersonaRol.objects.create(
                persona=persona,
                rol=self.rol_estudiante,
                organizacion=self.org,
                activo=True,
            )

        response = self.client.get(
            reverse("personas:personas_list"),
            {
                "periodo_mes": 3,
                "periodo_anio": 2026,
                "organizacion": self.org.pk,
                "rol": "ESTUDIANTE",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["page_obj"].has_next())
        self.assertLessEqual(len(response.context["personas"]), 25)
        self.assertContains(response, "Siguiente")
        self.assertContains(response, "rol=ESTUDIANTE&amp;page=2", html=False)

    def test_personas_list_no_hace_prefetch_por_todo_el_resultado(self):
        for index in range(30):
            persona = Persona.objects.create(
                nombres=f"Query {index:02d}",
                apellidos="Control",
                email=f"querycontrol{index:02d}@example.com",
            )
            PersonaRol.objects.create(
                persona=persona,
                rol=self.rol_estudiante,
                organizacion=self.org,
                activo=True,
            )

        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(
                reverse("personas:personas_list"),
                {"periodo_mes": 3, "periodo_anio": 2026, "organizacion": self.org.pk},
            )

        self.assertEqual(response.status_code, 200)
        self.assertLessEqual(len(response.context["personas"]), 25)
        self.assertLessEqual(len(queries), 20)


class PersonasRutFormTests(TestCase):
    def _data_persona(self, **overrides):
        data = {
            "nombres": "Julia",
            "apellidos": "Perez",
            "email": "",
            "telefono": "",
            "rut": "",
            "fecha_nacimiento": "",
            "activo": "on",
            "user": "",
        }
        data.update(overrides)
        return data

    def test_persona_form_valida_y_formatea_rut_chileno(self):
        form = PersonaCRMForm(data=self._data_persona(rut="12345678-5"))

        self.assertTrue(form.is_valid(), form.errors)
        persona = form.save()
        self.assertEqual(persona.rut, "12.345.678-5")

    def test_persona_form_rechaza_rut_chileno_invalido(self):
        form = PersonaCRMForm(data=self._data_persona(rut="12.345.678-9"))

        self.assertFalse(form.is_valid())
        self.assertIn("rut", form.errors)

    def test_persona_form_rechaza_persona_sin_identidad_minima(self):
        form = PersonaCRMForm(data=self._data_persona())

        self.assertFalse(form.is_valid())
        self.assertIn("__all__", form.errors)

    def test_persona_form_acepta_solo_email(self):
        form = PersonaCRMForm(data=self._data_persona(email="julia@example.com"))

        self.assertTrue(form.is_valid(), form.errors)

    def test_persona_form_acepta_solo_telefono_y_normaliza(self):
        form = PersonaCRMForm(data=self._data_persona(telefono="(9) 1234-5678"))

        self.assertTrue(form.is_valid(), form.errors)
        persona = form.save()
        self.assertEqual(persona.telefono, "+56912345678")

    def test_persona_form_no_bloquea_telefono_repetido(self):
        Persona.objects.create(nombres="Ana", apellidos="Uno", telefono="+56911111111")
        form = PersonaCRMForm(data=self._data_persona(telefono="9 1111-1111"))

        self.assertTrue(form.is_valid(), form.errors)

    def test_persona_form_bloquea_rut_duplicado(self):
        Persona.objects.create(nombres="Ana", apellidos="Uno", rut="12.345.678-5")
        form = PersonaCRMForm(data=self._data_persona(rut="12345678-5"))

        self.assertFalse(form.is_valid())
        self.assertIn("rut", form.errors)

    def test_alta_rapida_exige_identidad_minima_y_normaliza_telefono(self):
        form = PersonaRapidaForm(data={"nombres": "Julia", "apellidos": "Perez", "telefono": ""})
        self.assertFalse(form.is_valid())
        self.assertIn("__all__", form.errors)

        form = PersonaRapidaForm(data={"nombres": "Julia", "apellidos": "Perez", "telefono": "(9) 1234-5678"})
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["telefono"], "+56912345678")


class AuditarDatosV1CommandTests(TestCase):
    def test_auditoria_corre_sin_modificar_datos(self):
        persona = Persona.objects.create(nombres="Sin", apellidos="Identidad")
        before = list(Persona.objects.values_list("id", "nombres", "apellidos", "telefono", "rut", "email"))
        out = StringIO()

        call_command("auditar_datos_v1", stdout=out)

        after = list(Persona.objects.values_list("id", "nombres", "apellidos", "telefono", "rut", "email"))
        self.assertEqual(before, after)
        self.assertIn("Personas sin RUT, email ni telefono: 1", out.getvalue())
        self.assertIn(str(persona.id), out.getvalue())
        self.assertIn("No se modificaron datos.", out.getvalue())

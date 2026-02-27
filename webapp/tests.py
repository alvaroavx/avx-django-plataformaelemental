from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from database.models import Asistencia, Disciplina, Organizacion, Persona, PersonaRol, Rol, SesionClase


class AsistenciasViewTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username="admin",
            password="secret123",
            is_superuser=True,
            is_staff=True,
        )
        self.client.force_login(self.user)

        self.organizacion = Organizacion.objects.create(
            nombre="Org Test",
            razon_social="Org Test SPA",
            rut="11.111.111-1",
        )
        self.disciplina = Disciplina.objects.create(
            organizacion=self.organizacion,
            nombre="Flexibilidad",
        )
        self.sesion = SesionClase.objects.create(
            disciplina=self.disciplina,
            fecha="2026-02-26",
            estado=SesionClase.Estado.PROGRAMADA,
        )
        self.estudiante = Persona.objects.create(
            nombres="Ana",
            apellidos="Diaz",
            email="ana@example.com",
        )
        rol_estudiante = Rol.objects.create(nombre="Estudiante", codigo="ESTUDIANTE")
        PersonaRol.objects.create(
            persona=self.estudiante,
            rol=rol_estudiante,
            organizacion=self.organizacion,
            activo=True,
        )

    def test_agregar_asistentes_cambia_estado_a_completada(self):
        response = self.client.post(
            reverse("webapp:asistencias_list"),
            {
                "agregar_asistentes": "1",
                "sesion_id": str(self.sesion.pk),
                "estudiantes": [str(self.estudiante.pk)],
            },
        )

        self.assertEqual(response.status_code, 302)
        self.sesion.refresh_from_db()
        self.assertEqual(self.sesion.estado, SesionClase.Estado.COMPLETADA)

    def test_asistencias_cambiar_estado_mantiene_filtros_en_redirect(self):
        url = f"{reverse('webapp:asistencias_list')}?periodo_mes=2&periodo_anio=2026&organizacion={self.organizacion.pk}"
        response = self.client.post(
            url,
            {
                "cambiar_estado": "1",
                "sesion_id": str(self.sesion.pk),
                "estado": SesionClase.Estado.CANCELADA,
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, url)
        self.sesion.refresh_from_db()
        self.assertEqual(self.sesion.estado, SesionClase.Estado.CANCELADA)

    def test_agregar_asistentes_desde_sesion_detail(self):
        url = reverse("webapp:sesion_detail", kwargs={"pk": self.sesion.pk})
        response = self.client.post(
            url,
            {
                "agregar_asistentes": "1",
                "estudiantes": [str(self.estudiante.pk)],
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, url)
        self.assertTrue(
            Asistencia.objects.filter(sesion=self.sesion, persona=self.estudiante).exists()
        )
        self.sesion.refresh_from_db()
        self.assertEqual(self.sesion.estado, SesionClase.Estado.COMPLETADA)

    def test_dashboard_estudiantes_activos_cuenta_personas_unicas_con_asistencia(self):
        sesion_extra = SesionClase.objects.create(
            disciplina=self.disciplina,
            fecha="2026-02-27",
            estado=SesionClase.Estado.PROGRAMADA,
        )
        otro_estudiante = Persona.objects.create(
            nombres="Luis",
            apellidos="Rojas",
            email="luis@example.com",
        )
        rol_estudiante = Rol.objects.get(codigo="ESTUDIANTE")
        PersonaRol.objects.create(
            persona=otro_estudiante,
            rol=rol_estudiante,
            organizacion=self.organizacion,
            activo=True,
        )
        Asistencia.objects.create(sesion=self.sesion, persona=self.estudiante)
        Asistencia.objects.create(sesion=sesion_extra, persona=self.estudiante)
        Asistencia.objects.create(sesion=sesion_extra, persona=otro_estudiante)

        response = self.client.get(
            reverse("webapp:dashboard"),
            {"periodo_mes": 2, "periodo_anio": 2026},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["estudiantes_activos_mes"], 2)

    def test_dashboard_sesiones_realizadas_cuenta_solo_completadas_del_mes(self):
        SesionClase.objects.create(
            disciplina=self.disciplina,
            fecha="2026-02-27",
            estado=SesionClase.Estado.COMPLETADA,
        )
        SesionClase.objects.create(
            disciplina=self.disciplina,
            fecha="2026-03-01",
            estado=SesionClase.Estado.COMPLETADA,
        )

        response = self.client.get(
            reverse("webapp:dashboard"),
            {"periodo_mes": 2, "periodo_anio": 2026},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["sesiones_realizadas_mes"], 1)

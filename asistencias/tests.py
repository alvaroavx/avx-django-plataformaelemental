from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from finanzas.models import AttendanceConsumption, Payment
from personas.models import Organizacion, Persona, PersonaRol, Rol

from .models import Asistencia, Disciplina, SesionClase


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
            reverse("asistencias:asistencias_list"),
            {
                "agregar_asistentes": "1",
                "sesion_id": str(self.sesion.pk),
                "estudiantes": [str(self.estudiante.pk)],
            },
        )

        self.assertEqual(response.status_code, 302)
        self.sesion.refresh_from_db()
        self.assertEqual(self.sesion.estado, SesionClase.Estado.COMPLETADA)

    def test_agregar_persona_desde_asistencias_usa_organizacion_filtrada(self):
        response = self.client.post(
            f"{reverse('asistencias:asistencias_list')}?periodo_mes=2&periodo_anio=2026&organizacion={self.organizacion.pk}",
            {
                "agregar_persona": "1",
                "nombres": "Nueva",
                "apellidos": "Persona",
                "telefono": "123456",
            },
        )

        self.assertEqual(response.status_code, 302)
        persona = Persona.objects.get(nombres="Nueva", apellidos="Persona")
        self.assertTrue(
            PersonaRol.objects.filter(
                persona=persona,
                organizacion=self.organizacion,
                rol__codigo="ESTUDIANTE",
            ).exists()
        )

    def test_agregar_persona_desde_asistencias_exige_organizacion_filtrada(self):
        response = self.client.post(
            reverse("asistencias:asistencias_list"),
            {
                "agregar_persona": "1",
                "nombres": "Sin",
                "apellidos": "Organizacion",
                "telefono": "123456",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "Debes seleccionar una organización en el filtro superior antes de crear a la persona.",
        )
        self.assertFalse(Persona.objects.filter(nombres="Sin", apellidos="Organizacion").exists())

    def test_asistencias_cambiar_estado_mantiene_filtros_en_redirect(self):
        url = f"{reverse('asistencias:asistencias_list')}?periodo_mes=2&periodo_anio=2026&organizacion={self.organizacion.pk}"
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
        url = reverse("asistencias:sesion_detail", kwargs={"pk": self.sesion.pk})
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

    def test_sesion_detail_crea_persona_en_organizacion_de_la_sesion(self):
        otra_organizacion = Organizacion.objects.create(
            nombre="Otra Org",
            razon_social="Otra Org SPA",
            rut="22.222.222-2",
        )
        url = (
            f"{reverse('asistencias:sesion_detail', kwargs={'pk': self.sesion.pk})}"
            f"?periodo_mes=2&periodo_anio=2026&organizacion={otra_organizacion.pk}"
        )

        response = self.client.post(
            url,
            {
                "crear_persona_estudiante": "1",
                "nombres": "Camila",
                "apellidos": "Nueva",
                "telefono": "555",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, url)
        persona = Persona.objects.get(nombres="Camila", apellidos="Nueva")
        self.assertTrue(
            PersonaRol.objects.filter(
                persona=persona,
                organizacion=self.organizacion,
                rol__codigo="ESTUDIANTE",
            ).exists()
        )
        self.assertFalse(
            PersonaRol.objects.filter(
                persona=persona,
                organizacion=otra_organizacion,
                rol__codigo="ESTUDIANTE",
            ).exists()
        )

    def test_sesion_detail_muestra_modal_para_crear_persona(self):
        response = self.client.get(
            reverse("asistencias:sesion_detail", kwargs={"pk": self.sesion.pk}),
            {"periodo_mes": 2, "periodo_anio": 2026, "organizacion": self.organizacion.pk},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Nueva persona")
        self.assertContains(response, 'data-bs-target="#nuevaPersonaSesionModal"', html=False)

    def test_sesion_detail_elimina_sesion_y_dependencias(self):
        asistencia = Asistencia.objects.create(sesion=self.sesion, persona=self.estudiante)
        self.assertEqual(AttendanceConsumption.objects.filter(asistencia=asistencia).count(), 1)
        url = (
            f"{reverse('asistencias:sesion_detail', kwargs={'pk': self.sesion.pk})}"
            f"?periodo_mes=2&periodo_anio=2026&organizacion={self.organizacion.pk}"
        )

        response = self.client.post(
            url,
            {
                "eliminar_sesion": "1",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.url,
            f"{reverse('asistencias:sesiones_list')}?periodo_mes=2&periodo_anio=2026&organizacion={self.organizacion.pk}",
        )
        self.assertFalse(SesionClase.objects.filter(pk=self.sesion.pk).exists())
        self.assertFalse(Asistencia.objects.filter(pk=asistencia.pk).exists())
        self.assertEqual(AttendanceConsumption.objects.count(), 0)

    def test_sesion_detail_permite_eliminar_asistente_individual(self):
        asistencia = Asistencia.objects.create(sesion=self.sesion, persona=self.estudiante)
        self.assertEqual(AttendanceConsumption.objects.filter(asistencia=asistencia).count(), 1)
        url = (
            f"{reverse('asistencias:sesion_detail', kwargs={'pk': self.sesion.pk})}"
            f"?periodo_mes=2&periodo_anio=2026&organizacion={self.organizacion.pk}"
        )

        response = self.client.post(
            url,
            {
                "eliminar_asistente": "1",
                "asistencia_id": asistencia.pk,
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, url)
        self.assertFalse(Asistencia.objects.filter(pk=asistencia.pk).exists())
        self.assertEqual(AttendanceConsumption.objects.count(), 0)

    def test_asistencias_list_muestra_checkboxes_marcados_para_asistentes_existentes(self):
        Asistencia.objects.create(sesion=self.sesion, persona=self.estudiante)

        response = self.client.get(
            reverse("asistencias:asistencias_list"),
            {
                "sesion_id": self.sesion.pk,
                "periodo_mes": 2,
                "periodo_anio": 2026,
                "organizacion": self.organizacion.pk,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            f'id="estudiante_{self.estudiante.pk}"',
            html=False,
        )
        self.assertContains(
            response,
            f'value="{self.estudiante.pk}"',
            html=False,
        )
        self.assertContains(response, "seleccionar_visibles", html=False)
        self.assertContains(response, "limpiar_seleccion", html=False)
        self.assertContains(response, "checked", html=False)

    def test_asistencias_list_muestra_total_por_disciplina_en_periodo(self):
        otra_disciplina = Disciplina.objects.create(
            organizacion=self.organizacion,
            nombre="Teatro",
        )
        otra_sesion_misma_disciplina = SesionClase.objects.create(
            disciplina=self.disciplina,
            fecha="2026-02-20",
            estado=SesionClase.Estado.COMPLETADA,
        )
        sesion_otra_disciplina = SesionClase.objects.create(
            disciplina=otra_disciplina,
            fecha="2026-02-21",
            estado=SesionClase.Estado.COMPLETADA,
        )
        segundo_estudiante = Persona.objects.create(
            nombres="Luis",
            apellidos="Rojas",
            email="luis@example.com",
        )
        rol_estudiante = Rol.objects.get(codigo="ESTUDIANTE")
        PersonaRol.objects.create(
            persona=segundo_estudiante,
            rol=rol_estudiante,
            organizacion=self.organizacion,
            activo=True,
        )
        Asistencia.objects.create(sesion=self.sesion, persona=self.estudiante)
        Asistencia.objects.create(sesion=otra_sesion_misma_disciplina, persona=segundo_estudiante)
        Asistencia.objects.create(sesion=sesion_otra_disciplina, persona=self.estudiante)

        response = self.client.get(
            reverse("asistencias:asistencias_list"),
            {
                "sesion_id": self.sesion.pk,
                "periodo_mes": 2,
                "periodo_anio": 2026,
                "organizacion": self.organizacion.pk,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Total asistencia a Flexibilidad: 2")

    def test_sesion_detail_enlaza_profesor_a_perfil_asistencias_con_filtros(self):
        profesor = Persona.objects.create(
            nombres="Paula",
            apellidos="Mora",
            email="paula.sesion@example.com",
        )
        rol_profesor = Rol.objects.create(nombre="Profesor", codigo="PROFESOR")
        PersonaRol.objects.create(
            persona=profesor,
            rol=rol_profesor,
            organizacion=self.organizacion,
            activo=True,
        )
        self.sesion.profesores.set([profesor])

        response = self.client.get(
            reverse("asistencias:sesion_detail", kwargs={"pk": self.sesion.pk}),
            {"periodo_mes": 2, "periodo_anio": 2026, "organizacion": self.organizacion.pk},
        )

        self.assertEqual(response.status_code, 200)
        enlace = (
            f'{reverse("asistencias:persona_detail", kwargs={"pk": profesor.pk})}'
            f"?periodo_mes=2&periodo_anio=2026&organizacion={self.organizacion.pk}"
        )
        self.assertContains(response, f'href="{enlace}"', html=False)

    def test_sesion_detail_muestra_estado_de_pago_del_asistente(self):
        pago = Payment.objects.create(
            persona=self.estudiante,
            organizacion=self.organizacion,
            fecha_pago="2026-02-20",
            metodo_pago=Payment.Metodo.EFECTIVO,
            aplica_iva=False,
            monto_referencia=10000,
            clases_asignadas=1,
        )
        asistencia = Asistencia.objects.create(sesion=self.sesion, persona=self.estudiante)
        consumo = AttendanceConsumption.objects.get(asistencia=asistencia)
        self.assertEqual(consumo.pago, pago)

        response = self.client.get(
            reverse("asistencias:sesion_detail", kwargs={"pk": self.sesion.pk}),
            {"periodo_mes": 2, "periodo_anio": 2026, "organizacion": self.organizacion.pk},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Estado de pago")
        self.assertContains(response, "Pagada")

    def test_sesion_detail_muestra_boton_editar_sesion_con_filtros(self):
        response = self.client.get(
            reverse("asistencias:sesion_detail", kwargs={"pk": self.sesion.pk}),
            {"periodo_mes": 2, "periodo_anio": 2026, "organizacion": self.organizacion.pk},
        )

        self.assertEqual(response.status_code, 200)
        enlace = (
            f'{reverse("asistencias:sesion_edit", kwargs={"pk": self.sesion.pk})}'
            f"?periodo_mes=2&periodo_anio=2026&organizacion={self.organizacion.pk}"
        )
        self.assertContains(response, f'href="{enlace}"', html=False)

    def test_sesion_edit_actualiza_datos_y_redirige_a_detalle(self):
        profesor = Persona.objects.create(
            nombres="Paula",
            apellidos="Edita",
            email="paula.edita@example.com",
        )
        rol_profesor = Rol.objects.create(nombre="Profesor", codigo="PROFESOR")
        PersonaRol.objects.create(
            persona=profesor,
            rol=rol_profesor,
            organizacion=self.organizacion,
            activo=True,
        )
        otra_disciplina = Disciplina.objects.create(
            organizacion=self.organizacion,
            nombre="Teatro",
        )
        url = (
            f"{reverse('asistencias:sesion_edit', kwargs={'pk': self.sesion.pk})}"
            f"?periodo_mes=2&periodo_anio=2026&organizacion={self.organizacion.pk}"
        )

        response = self.client.post(
            url,
            {
                "disciplina": otra_disciplina.pk,
                "fecha": "2026-02-27",
                "profesores": [profesor.pk],
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.url,
            f"{reverse('asistencias:sesion_detail', kwargs={'pk': self.sesion.pk})}?periodo_mes=2&periodo_anio=2026&organizacion={self.organizacion.pk}",
        )
        self.sesion.refresh_from_db()
        self.assertEqual(self.sesion.disciplina, otra_disciplina)
        self.assertEqual(str(self.sesion.fecha), "2026-02-27")
        self.assertEqual(list(self.sesion.profesores.all()), [profesor])

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
            reverse("asistencias:dashboard"),
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
            reverse("asistencias:dashboard"),
            {"periodo_mes": 2, "periodo_anio": 2026},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["sesiones_realizadas_mes"], 1)

    def test_dashboard_muestra_columnas_de_deuda_y_mas_asistencia(self):
        otro_estudiante = Persona.objects.create(
            nombres="Luis",
            apellidos="Rojas",
            email="luis.dashboard@example.com",
        )
        tercer_estudiante = Persona.objects.create(
            nombres="Marta",
            apellidos="Lopez",
            email="marta.dashboard@example.com",
        )
        rol_estudiante = Rol.objects.get(codigo="ESTUDIANTE")
        PersonaRol.objects.create(
            persona=otro_estudiante,
            rol=rol_estudiante,
            organizacion=self.organizacion,
            activo=True,
        )
        PersonaRol.objects.create(
            persona=tercer_estudiante,
            rol=rol_estudiante,
            organizacion=self.organizacion,
            activo=True,
        )
        sesion_dos = SesionClase.objects.create(
            disciplina=self.disciplina,
            fecha="2026-02-27",
            estado=SesionClase.Estado.COMPLETADA,
        )
        asistencia_ana_1 = Asistencia.objects.create(sesion=self.sesion, persona=self.estudiante)
        asistencia_ana_2 = Asistencia.objects.create(sesion=sesion_dos, persona=self.estudiante)
        asistencia_luis = Asistencia.objects.create(sesion=self.sesion, persona=otro_estudiante)
        consumo_luis = AttendanceConsumption.objects.get(asistencia=asistencia_luis)
        consumo_luis.estado = AttendanceConsumption.Estado.DEUDA
        consumo_luis.pago = None
        consumo_luis.save(update_fields=["estado", "pago", "actualizado_en"])

        response = self.client.get(
            reverse("asistencias:dashboard"),
            {"periodo_mes": 2, "periodo_anio": 2026, "organizacion": self.organizacion.pk},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Estudiantes con deuda")
        self.assertContains(response, "Estudiantes con más asistencia")
        self.assertContains(response, "Luis Rojas")
        self.assertContains(response, "(1 clases)")
        self.assertContains(response, "Ana Diaz")
        self.assertContains(response, "(2 clases)")
        self.assertIn(otro_estudiante, list(response.context["estudiantes_con_deuda"]))
        self.assertEqual(response.context["estudiantes_con_deuda"][0], self.estudiante)
        self.assertEqual(response.context["estudiantes_con_deuda"][0].clases_deuda, 2)
        self.assertEqual(response.context["estudiantes_con_deuda"][1], otro_estudiante)
        self.assertEqual(response.context["estudiantes_con_deuda"][1].clases_deuda, 1)
        self.assertEqual(response.context["estudiantes_con_mas_asistencia"][0], self.estudiante)
        self.assertEqual(response.context["estudiantes_con_mas_asistencia"][0].total_asistencias_mes, 2)

    def test_sesiones_list_muestra_mensaje_cancelada_en_vez_de_asistentes_cero(self):
        self.sesion.estado = SesionClase.Estado.CANCELADA
        self.sesion.save(update_fields=["estado"])

        response = self.client.get(
            reverse("asistencias:sesiones_list"),
            {"periodo_mes": 2, "periodo_anio": 2026, "organizacion": self.organizacion.pk},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "sesión cancelada")
        self.assertNotContains(response, "asistentes: 0")

    def test_disciplinas_list_muestra_resumen_operativo(self):
        sesion_realizada = SesionClase.objects.create(
            disciplina=self.disciplina,
            fecha="2026-02-27",
            estado=SesionClase.Estado.COMPLETADA,
        )
        otro_estudiante = Persona.objects.create(
            nombres="Luis",
            apellidos="Rojas",
            email="luis2@example.com",
        )
        rol_estudiante = Rol.objects.get(codigo="ESTUDIANTE")
        PersonaRol.objects.create(
            persona=otro_estudiante,
            rol=rol_estudiante,
            organizacion=self.organizacion,
            activo=True,
        )
        Asistencia.objects.create(sesion=self.sesion, persona=self.estudiante)
        Asistencia.objects.create(sesion=sesion_realizada, persona=self.estudiante)
        Asistencia.objects.create(sesion=sesion_realizada, persona=otro_estudiante)

        response = self.client.get(
            reverse("asistencias:disciplinas_list"),
            {"periodo_mes": 2, "periodo_anio": 2026, "organizacion": self.organizacion.pk},
        )

        self.assertEqual(response.status_code, 200)
        disciplina = response.context["disciplinas"].get(pk=self.disciplina.pk)
        self.assertEqual(disciplina.sesiones_realizadas, 1)
        self.assertEqual(disciplina.sesiones_periodo, 2)
        self.assertEqual(disciplina.asistencias_periodo, 3)
        self.assertEqual(disciplina.estudiantes_unicos, 2)

    def test_disciplinas_list_ordena_activas_primero_y_luego_alfabetico(self):
        disciplina_activa = Disciplina.objects.create(
            organizacion=self.organizacion,
            nombre="Zumba",
            activa=True,
        )
        disciplina_inactiva = Disciplina.objects.create(
            organizacion=self.organizacion,
            nombre="Acrobacia",
            activa=False,
        )

        response = self.client.get(
            reverse("asistencias:disciplinas_list"),
            {"periodo_mes": 2, "periodo_anio": 2026, "organizacion": self.organizacion.pk},
        )

        self.assertEqual(response.status_code, 200)
        disciplinas = list(response.context["disciplinas"])
        self.assertEqual(
            [disciplina.nombre for disciplina in disciplinas[:3]],
            ["Flexibilidad", "Zumba", "Acrobacia"],
        )
        self.assertTrue(disciplinas[0].activa)
        self.assertTrue(disciplinas[1].activa)
        self.assertFalse(disciplinas[2].activa)

    def test_disciplina_create_redirige_a_detalle_con_filtros(self):
        query = f"periodo_mes=2&periodo_anio=2026&organizacion={self.organizacion.pk}"
        url = f"{reverse('asistencias:disciplina_create')}?{query}"

        response = self.client.post(
            url,
            {
                "organizacion": self.organizacion.pk,
                "nombre": "Contemporaneo",
                "nivel": "Intermedio",
                "descripcion": "Taller de danza contemporanea",
                "activa": "on",
            },
        )

        self.assertEqual(response.status_code, 302)
        nueva = Disciplina.objects.get(nombre="Contemporaneo")
        self.assertEqual(
            response.url,
            f"{reverse('asistencias:disciplina_detail', kwargs={'pk': nueva.pk})}?{query}",
        )

    def test_disciplina_edit_actualiza_nombre(self):
        query = f"periodo_mes=2&periodo_anio=2026&organizacion={self.organizacion.pk}"
        url = f"{reverse('asistencias:disciplina_edit', kwargs={'pk': self.disciplina.pk})}?{query}"

        response = self.client.post(
            url,
            {
                "organizacion": self.organizacion.pk,
                "nombre": "Flexibilidad avanzada",
                "nivel": "",
                "descripcion": "Actualizada",
                "activa": "on",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.disciplina.refresh_from_db()
        self.assertEqual(self.disciplina.nombre, "Flexibilidad avanzada")

    def test_disciplina_detail_muestra_profesores_en_descripcion_y_asistentes_en_tabla(self):
        profesor = Persona.objects.create(
            nombres="Paula",
            apellidos="Mora",
            email="paula.disciplina@example.com",
        )
        rol_profesor = Rol.objects.create(nombre="Profesor", codigo="PROFESOR")
        PersonaRol.objects.create(
            persona=profesor,
            rol=rol_profesor,
            organizacion=self.organizacion,
            activo=True,
        )
        self.sesion.profesores.set([profesor])
        Asistencia.objects.create(sesion=self.sesion, persona=self.estudiante)

        response = self.client.get(
            reverse("asistencias:disciplina_detail", kwargs={"pk": self.disciplina.pk}),
            {"periodo_mes": 2, "periodo_anio": 2026, "organizacion": self.organizacion.pk},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Profesores del período")
        self.assertContains(response, "Paula Mora")
        self.assertContains(response, 'id="tabla-sesiones-disciplina"', html=False)
        self.assertContains(response, "<th>Asistentes</th>", html=False)
        self.assertContains(response, "<th>Asistencias</th>", html=False)
        self.assertContains(response, "<th>Estado</th>", html=False)
        self.assertContains(response, "Ana Diaz")
        self.assertNotContains(response, "<th>Profesores</th>", html=False)
        self.assertNotContains(response, "<th>Presentes</th>", html=False)
        self.assertNotContains(response, "<th>Ausentes</th>", html=False)
        self.assertNotContains(response, "<th>Justificadas</th>", html=False)

    def test_profesores_list_boton_ver_perfil_envia_filtros_a_personas(self):
        profesor = Persona.objects.create(
            nombres="Paula",
            apellidos="Mora",
            email="paula@example.com",
        )
        rol_profesor = Rol.objects.create(nombre="Profesor", codigo="PROFESOR")
        PersonaRol.objects.create(
            persona=profesor,
            rol=rol_profesor,
            organizacion=self.organizacion,
            activo=True,
        )
        self.sesion.profesores.set([profesor])

        response = self.client.get(
            reverse("asistencias:profesores_list"),
            {"periodo_mes": 2, "periodo_anio": 2026, "organizacion": self.organizacion.pk},
        )

        self.assertEqual(response.status_code, 200)
        enlace = (
            f'{reverse("personas:persona_detail", kwargs={"pk": profesor.pk})}'
            f"?periodo_mes=2&periodo_anio=2026&organizacion={self.organizacion.pk}"
        )
        self.assertContains(response, f'href="{enlace}"', html=False)
        self.assertNotContains(response, 'id="filtro-organizacion"', html=False)

    def test_profesores_list_oculta_profesores_sin_asistencias_ni_sesiones_activas(self):
        rol_profesor = Rol.objects.create(nombre="Profesor", codigo="PROFESOR")
        profesor_inactivo = Persona.objects.create(
            nombres="Pedro",
            apellidos="Silva",
            email="pedro@example.com",
        )
        profesor_con_sesion = Persona.objects.create(
            nombres="Laura",
            apellidos="Torres",
            email="laura@example.com",
        )
        PersonaRol.objects.create(
            persona=profesor_inactivo,
            rol=rol_profesor,
            organizacion=self.organizacion,
            activo=True,
        )
        PersonaRol.objects.create(
            persona=profesor_con_sesion,
            rol=rol_profesor,
            organizacion=self.organizacion,
            activo=True,
        )
        self.sesion.profesores.set([profesor_con_sesion])

        response = self.client.get(
            reverse("asistencias:profesores_list"),
            {"periodo_mes": 2, "periodo_anio": 2026, "organizacion": self.organizacion.pk},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Laura Torres")
        self.assertNotContains(response, "Pedro Silva")

    def test_profesores_list_oculta_profesor_con_solo_sesiones_canceladas(self):
        rol_profesor = Rol.objects.create(nombre="Profesor", codigo="PROFESOR")
        profesor = Persona.objects.create(
            nombres="Mario",
            apellidos="Cancelado",
            email="mario@example.com",
        )
        PersonaRol.objects.create(
            persona=profesor,
            rol=rol_profesor,
            organizacion=self.organizacion,
            activo=True,
        )
        sesion_cancelada = SesionClase.objects.create(
            disciplina=self.disciplina,
            fecha="2026-02-27",
            estado=SesionClase.Estado.CANCELADA,
        )
        sesion_cancelada.profesores.set([profesor])

        response = self.client.get(
            reverse("asistencias:profesores_list"),
            {"periodo_mes": 2, "periodo_anio": 2026, "organizacion": self.organizacion.pk},
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Mario Cancelado")

    def test_profesores_list_muestra_cards_resumen_del_periodo(self):
        profesor = Persona.objects.create(
            nombres="Paula",
            apellidos="Mora",
            email="paula.cards@example.com",
        )
        rol_profesor = Rol.objects.create(nombre="Profesor", codigo="PROFESOR")
        PersonaRol.objects.create(
            persona=profesor,
            rol=rol_profesor,
            organizacion=self.organizacion,
            activo=True,
        )
        self.sesion.estado = SesionClase.Estado.COMPLETADA
        self.sesion.save(update_fields=["estado"])
        self.sesion.profesores.set([profesor])
        Asistencia.objects.create(sesion=self.sesion, persona=self.estudiante)

        segundo_estudiante = Persona.objects.create(
            nombres="Luis",
            apellidos="Rojas",
            email="luis.cards@example.com",
        )
        PersonaRol.objects.create(
            persona=segundo_estudiante,
            rol=Rol.objects.get(codigo="ESTUDIANTE"),
            organizacion=self.organizacion,
            activo=True,
        )
        sesion_dos = SesionClase.objects.create(
            disciplina=self.disciplina,
            fecha="2026-02-27",
            estado=SesionClase.Estado.COMPLETADA,
        )
        sesion_dos.profesores.set([profesor])
        Asistencia.objects.create(sesion=sesion_dos, persona=segundo_estudiante)

        response = self.client.get(
            reverse("asistencias:profesores_list"),
            {"periodo_mes": 2, "periodo_anio": 2026, "organizacion": self.organizacion.pk},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context["resumen_profesores"],
            {
                "alumnos_unicos": 2,
                "sesiones_realizadas": 2,
                "asistencias_mes": 2,
                "profesores_activos": 1,
            },
        )
        self.assertContains(response, "Total alumnos únicos")
        self.assertContains(response, "Total sesiones realizadas")
        self.assertContains(response, "Total general de asistencias del mes")
        self.assertContains(response, "Total de profesores activos")

    def test_persona_detail_estudiante_resumen_respeta_periodo_y_organizacion(self):
        otra_org = Organizacion.objects.create(
            nombre="Org Dos",
            razon_social="Org Dos SPA",
            rut="22.222.222-2",
        )
        PersonaRol.objects.create(
            persona=self.estudiante,
            rol=Rol.objects.get(codigo="ESTUDIANTE"),
            organizacion=otra_org,
            activo=True,
        )
        otra_disciplina = Disciplina.objects.create(
            organizacion=otra_org,
            nombre="Pilates",
        )
        sesion_marzo = SesionClase.objects.create(
            disciplina=self.disciplina,
            fecha="2026-03-03",
            estado=SesionClase.Estado.PROGRAMADA,
        )
        sesion_otra_org = SesionClase.objects.create(
            disciplina=otra_disciplina,
            fecha="2026-02-20",
            estado=SesionClase.Estado.PROGRAMADA,
        )
        Payment.objects.create(
            persona=self.estudiante,
            organizacion=self.organizacion,
            fecha_pago="2026-02-25",
            metodo_pago=Payment.Metodo.EFECTIVO,
            aplica_iva=False,
            monto_referencia=10000,
            clases_asignadas=1,
        )
        Payment.objects.create(
            persona=self.estudiante,
            organizacion=self.organizacion,
            fecha_pago="2026-03-05",
            metodo_pago=Payment.Metodo.EFECTIVO,
            aplica_iva=False,
            monto_referencia=12000,
            clases_asignadas=1,
        )
        Payment.objects.create(
            persona=self.estudiante,
            organizacion=otra_org,
            fecha_pago="2026-02-18",
            metodo_pago=Payment.Metodo.EFECTIVO,
            aplica_iva=False,
            monto_referencia=9000,
            clases_asignadas=1,
        )

        Asistencia.objects.create(sesion=self.sesion, persona=self.estudiante)
        Asistencia.objects.create(sesion=sesion_marzo, persona=self.estudiante)
        Asistencia.objects.create(sesion=sesion_otra_org, persona=self.estudiante)

        response = self.client.get(
            reverse("asistencias:persona_detail", kwargs={"pk": self.estudiante.pk}),
            {"periodo_mes": 2, "periodo_anio": 2026, "organizacion": self.organizacion.pk},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["asistencias_mes"], 1)
        self.assertEqual(len(response.context["asistencias"]), 1)
        self.assertEqual(len(response.context["pagos_estudiante"]), 1)
        self.assertEqual(response.context["finanzas_resumen"]["clases_pagadas"], 1)
        self.assertEqual(response.context["finanzas_resumen"]["clases_consumidas"], 1)
        self.assertContains(response, "Pagada")
        self.assertContains(response, "Asociar")
        self.assertNotContains(response, "Pilates")

    def test_persona_detail_permite_reasociar_asistencia_a_pago_existente(self):
        pago_inicial = Payment.objects.create(
            persona=self.estudiante,
            organizacion=self.organizacion,
            fecha_pago="2026-02-20",
            metodo_pago=Payment.Metodo.EFECTIVO,
            aplica_iva=False,
            monto_referencia=10000,
            clases_asignadas=1,
        )
        pago_destino = Payment.objects.create(
            persona=self.estudiante,
            organizacion=self.organizacion,
            fecha_pago="2026-02-24",
            metodo_pago=Payment.Metodo.TRANSFERENCIA,
            numero_comprobante="TRX-1",
            aplica_iva=False,
            monto_referencia=12000,
            clases_asignadas=1,
        )
        asistencia = Asistencia.objects.create(sesion=self.sesion, persona=self.estudiante)
        consumo = AttendanceConsumption.objects.get(asistencia=asistencia)
        self.assertEqual(consumo.pago, pago_inicial)

        query = f"periodo_mes=2&periodo_anio=2026&organizacion={self.organizacion.pk}"
        response = self.client.post(
            f"{reverse('asistencias:persona_detail', kwargs={'pk': self.estudiante.pk})}?{query}",
            {
                "asociar_pago_asistencia": "1",
                "asistencia_id": asistencia.pk,
                "pago_id": pago_destino.pk,
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.url,
            f"{reverse('asistencias:persona_detail', kwargs={'pk': self.estudiante.pk})}?{query}",
        )
        consumo.refresh_from_db()
        self.assertEqual(consumo.pago, pago_destino)
        self.assertEqual(consumo.estado, AttendanceConsumption.Estado.CONSUMIDO)

    def test_asistencias_list_colorea_asistentes_por_estado_financiero(self):
        rol_estudiante = Rol.objects.get(codigo="ESTUDIANTE")
        estudiante_pagado = Persona.objects.create(
            nombres="Luis",
            apellidos="Pagado",
            email="luis.pagado@example.com",
        )
        estudiante_liberado = Persona.objects.create(
            nombres="Marta",
            apellidos="Liberada",
            email="marta.liberada@example.com",
        )
        PersonaRol.objects.create(
            persona=estudiante_pagado,
            rol=rol_estudiante,
            organizacion=self.organizacion,
            activo=True,
        )
        PersonaRol.objects.create(
            persona=estudiante_liberado,
            rol=rol_estudiante,
            organizacion=self.organizacion,
            activo=True,
        )
        Payment.objects.create(
            persona=estudiante_pagado,
            organizacion=self.organizacion,
            fecha_pago="2026-02-25",
            metodo_pago=Payment.Metodo.EFECTIVO,
            aplica_iva=False,
            monto_referencia=10000,
            clases_asignadas=1,
        )

        asistencia_deuda = Asistencia.objects.create(sesion=self.sesion, persona=self.estudiante)
        asistencia_pagada = Asistencia.objects.create(sesion=self.sesion, persona=estudiante_pagado)
        asistencia_liberada = Asistencia.objects.create(sesion=self.sesion, persona=estudiante_liberado)
        consumo_liberado = AttendanceConsumption.objects.get(asistencia=asistencia_liberada)
        consumo_liberado.estado = AttendanceConsumption.Estado.PENDIENTE
        consumo_liberado.pago = None
        consumo_liberado.save(update_fields=["estado", "pago", "actualizado_en"])

        response = self.client.get(
            reverse("asistencias:asistencias_list"),
            {"periodo_mes": 2, "periodo_anio": 2026, "organizacion": self.organizacion.pk},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            f'class="badge text-bg-warning me-1 text-decoration-none"',
            html=False,
        )
        self.assertContains(response, "Ana Diaz")
        self.assertContains(
            response,
            f'class="badge text-bg-success me-1 text-decoration-none"',
            html=False,
        )
        self.assertContains(response, "Luis Pagado")
        self.assertContains(
            response,
            f'class="badge text-bg-primary me-1 text-decoration-none"',
            html=False,
        )
        self.assertContains(response, "Marta Liberada")

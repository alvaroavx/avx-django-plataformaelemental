from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from asistencias.models import Asistencia, Disciplina, SesionClase
from auditoria.models import AuditLog
from finanzas.models import AttendanceConsumption, Category, DocumentoTributario, Payment, Transaction
from personas.models import Organizacion, Persona, PersonaRol, Rol, SolicitudAcceso


TEST_PASSWORD = "not-a-real-test-password"
TEST_INVALID_PASSWORD = "not-a-real-invalid-password"
TEST_ADMIN_USERNAME = "elemental_admin_test_user"


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

        self.user_admin = User.objects.create_user(TEST_ADMIN_USERNAME, password=TEST_PASSWORD)
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

        self.user_finanzas = User.objects.create_user("ux_finanzas_test_user", password=TEST_PASSWORD)
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

        self.user_profesor = User.objects.create_user("ux_profesor_test_user", password=TEST_PASSWORD)
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

        self.user_staff = User.objects.create_user("ux_staff_test_user", password=TEST_PASSWORD, is_staff=True)
        self.user_sin_roles = User.objects.create_user("ux_sin_roles_test_user", password=TEST_PASSWORD)

    def test_login_get_renderiza_elemental_apps(self):
        response = self.client.get(reverse("login"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Elemental Apps")
        self.assertContains(response, "Plataforma Elemental")

    @override_settings(GOOGLE_AUTH_ENFORCED=False)
    def test_login_post_valido_respeta_next(self):
        response = self.client.post(
            f"{reverse('login')}?next=/finanzas/",
            {"username": TEST_ADMIN_USERNAME, "password": TEST_PASSWORD},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/finanzas/")

    @override_settings(GOOGLE_AUTH_ENFORCED=False)
    def test_login_post_invalido_muestra_error(self):
        response = self.client.post(
            reverse("login"),
            {"username": TEST_ADMIN_USERNAME, "password": TEST_INVALID_PASSWORD},
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
        response = self.client.get(
            reverse("elemental_apps"),
            {"organizacion": self.organizacion.pk},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Finanzas")
        self.assertNotContains(response, "Admin")
        self.assertNotContains(response, "Personas")
        self.assertNotContains(response, "Asistencias")

    def test_rol_organizacional_sin_organizacion_no_recibe_enlaces_que_responden_403(self):
        self.client.force_login(self.user_admin)

        response = self.client.get(reverse("elemental_apps"))

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context["dashboard_academico"])
        self.assertIsNone(response.context["dashboard_financiero"])
        self.assertNotContains(response, reverse("asistencias:dashboard"))
        self.assertNotContains(response, reverse("finanzas:dashboard"))
        self.assertNotContains(response, reverse("personas:personas_list"))
        self.assertContains(response, "Revisa la organización seleccionada")

    @override_settings(ACCESS_REQUESTS_ENABLED=True)
    def test_gestor_solo_de_solicitudes_ve_pendiente_en_home(self):
        User = get_user_model()
        gestor = User.objects.create_user("gestor_solicitudes_home", password=TEST_PASSWORD)
        gestor.user_permissions.add(Permission.objects.get(codename="gestionar_solicitudes_acceso"))
        SolicitudAcceso.objects.create(
            provider="google",
            provider_subject="solicitud-home-pendiente",
            email="pendiente.home@example.com",
        )
        self.client.force_login(gestor)

        response = self.client.get(reverse("elemental_apps"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "solicitudes de acceso pendientes")
        self.assertContains(response, reverse("personas:solicitudes_acceso_list"))

    def test_dashboard_general_profesor_redirige_a_operacion_acotada(self):
        self.client.force_login(self.user_profesor)
        response = self.client.get(reverse("elemental_apps"))

        self.assertRedirects(response, reverse("profesor:inicio"))

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

    def test_sidebar_usa_dominios_como_encabezados_y_marca_pagina_actual(self):
        self.client.force_login(self.user_admin)

        response = self.client.get(
            reverse("asistencias:dashboard"),
            {"organizacion": self.organizacion.pk},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="elemental-nav-heading active"', html=False)
        self.assertContains(response, 'aria-current="page"', html=False)
        self.assertContains(response, "Sesiones")
        self.assertContains(response, "data-elemental-sidebar-toggle", html=False)
        self.assertContains(response, "plataformaelemental/js/shell.js")
        self.assertContains(response, "Resumen de operación")
        self.assertContains(response, 'aria-label="Menú principal"', html=False)
        self.assertContains(response, 'aria-label="Cerrar menú"', html=False)
        self.assertNotContains(response, 'id="elementalSidebarLabel"', html=False)
        self.assertContains(response, reverse("asistencias:sesiones_list"))
        self.assertContains(response, reverse("finanzas:pagos_list"))

    def test_dashboard_general_calcula_metricas_con_semantica_explicita(self):
        estudiante = Persona.objects.create(
            nombres="Ana",
            apellidos="Métrica",
            email="ana.metrica@example.com",
        )
        rol_estudiante = Rol.objects.create(nombre="Estudiante", codigo="ESTUDIANTE")
        PersonaRol.objects.create(
            persona=estudiante,
            rol=rol_estudiante,
            organizacion=self.organizacion,
            activo=True,
        )
        disciplina = Disciplina.objects.create(organizacion=self.organizacion, nombre="Danza")
        sesion = SesionClase.objects.create(
            disciplina=disciplina,
            fecha="2026-02-12",
            estado=SesionClase.Estado.COMPLETADA,
        )
        asistencia = Asistencia.objects.create(sesion=sesion, persona=estudiante)
        AttendanceConsumption.objects.filter(asistencia=asistencia).update(
            estado=AttendanceConsumption.Estado.DEUDA,
        )
        otra_sesion = SesionClase.objects.create(
            disciplina=disciplina,
            fecha="2026-02-19",
            estado=SesionClase.Estado.COMPLETADA,
        )
        otra_asistencia = Asistencia.objects.create(sesion=otra_sesion, persona=estudiante)
        AttendanceConsumption.objects.filter(asistencia=otra_asistencia).update(
            estado=AttendanceConsumption.Estado.CONSUMIDO,
        )
        categoria = Category.objects.create(nombre="Ingreso MVP", tipo=Category.Tipo.INGRESO)
        ingreso = Transaction.objects.create(
            organizacion=self.organizacion,
            categoria=categoria,
            fecha="2026-02-13",
            tipo=Transaction.Tipo.INGRESO,
            monto=25000,
            descripcion="Ingreso dashboard",
        )
        Transaction.objects.create(
            organizacion=self.organizacion,
            categoria=categoria,
            fecha="2026-02-14",
            tipo=Transaction.Tipo.EGRESO,
            monto=7000,
            descripcion="Egreso que no compone el indicador",
        )
        self.client.force_login(self.user_admin)

        response = self.client.get(
            reverse("elemental_apps"),
            {"periodo_mes": 2, "periodo_anio": 2026, "organizacion": self.organizacion.pk},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["dashboard_academico"]["sesiones_completadas"], 2)
        self.assertEqual(response.context["dashboard_academico"]["personas_con_asistencia"], 1)
        self.assertEqual(response.context["dashboard_financiero"]["clases_en_deuda"], 1)
        self.assertEqual(response.context["dashboard_financiero"]["ingresos_contables"], 25000)
        self.assertContains(response, "Personas con asistencia registrada")
        self.assertContains(response, "Ingresos contables")

        parametros = {"periodo_mes": 2, "periodo_anio": 2026, "organizacion": self.organizacion.pk}
        detalle_sesiones = self.client.get(
            reverse("elemental_apps_detalle_metrica", args=["sesiones-completadas"]),
            parametros,
        )
        self.assertEqual(detalle_sesiones.status_code, 200)
        self.assertEqual(detalle_sesiones.context["valor"], 2)
        self.assertEqual(list(detalle_sesiones.context["page_obj"]), [otra_sesion, sesion])

        detalle_personas = self.client.get(
            reverse("elemental_apps_detalle_metrica", args=["personas-con-asistencia"]),
            parametros,
        )
        self.assertEqual(detalle_personas.status_code, 200)
        self.assertEqual(detalle_personas.context["valor"], 1)
        persona_fila = list(detalle_personas.context["page_obj"])[0]
        self.assertEqual(persona_fila["persona_id"], estudiante.pk)
        self.assertEqual(persona_fila["registros_total"], 2)

        detalle_deuda = self.client.get(
            reverse("elemental_apps_detalle_metrica", args=["clases-en-deuda"]),
            parametros,
        )
        self.assertEqual(detalle_deuda.status_code, 200)
        self.assertEqual(detalle_deuda.context["valor"], 1)
        self.assertEqual(list(detalle_deuda.context["page_obj"])[0].asistencia_id, asistencia.pk)

        detalle_ingresos = self.client.get(
            reverse("elemental_apps_detalle_metrica", args=["ingresos-contables"]),
            parametros,
        )
        self.assertEqual(detalle_ingresos.status_code, 200)
        self.assertEqual(detalle_ingresos.context["valor"], 25000)
        self.assertEqual(detalle_ingresos.context["cantidad_registros"], 1)
        self.assertEqual(list(detalle_ingresos.context["page_obj"]), [ingreso])
        self.assertContains(
            response,
            reverse("elemental_apps_detalle_metrica", args=["sesiones-completadas"]),
        )

    def test_detalle_metrica_rechaza_tipo_desconocido_y_permiso_ajeno(self):
        self.client.force_login(self.user_finanzas)
        parametros = {"organizacion": self.organizacion.pk}

        desconocida = self.client.get(
            reverse("elemental_apps_detalle_metrica", args=["no-existe"]),
            parametros,
        )
        academica = self.client.get(
            reverse("elemental_apps_detalle_metrica", args=["sesiones-completadas"]),
            parametros,
        )

        self.assertEqual(desconocida.status_code, 404)
        self.assertEqual(academica.status_code, 403)

    def test_consulta_persona_no_expone_otra_organizacion(self):
        otra_organizacion = Organizacion.objects.create(
            nombre="Otra Org",
            razon_social="Otra Org SPA",
            rut="55.555.555-5",
        )
        rol_estudiante = Rol.objects.create(nombre="Estudiante", codigo="ESTUDIANTE")
        visible = Persona.objects.create(nombres="Elena", apellidos="Visible", email="elena@example.com")
        oculta = Persona.objects.create(nombres="Elena", apellidos="Oculta", email="oculta@example.com")
        PersonaRol.objects.create(persona=visible, rol=rol_estudiante, organizacion=self.organizacion, activo=True)
        PersonaRol.objects.create(persona=oculta, rol=rol_estudiante, organizacion=otra_organizacion, activo=True)
        self.client.force_login(self.user_admin)

        response = self.client.get(
            reverse("elemental_apps"),
            {"organizacion": self.organizacion.pk, "persona_q": "Elena"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Elena Visible")
        self.assertNotContains(response, "Elena Oculta")

        seleccion_forzada = self.client.get(
            reverse("elemental_apps"),
            {"organizacion": self.organizacion.pk, "persona_id": oculta.pk},
        )
        self.assertIsNone(seleccion_forzada.context["consulta_persona"]["persona"])

        seleccion_invalida = self.client.get(
            reverse("elemental_apps"),
            {"organizacion": self.organizacion.pk, "persona_id": "valor-invalido"},
        )
        self.assertEqual(seleccion_invalida.status_code, 200)
        self.assertIsNone(seleccion_invalida.context["consulta_persona"]["persona"])

    def test_consulta_persona_entrega_resumen_operacional_360(self):
        rol_estudiante = Rol.objects.create(nombre="Estudiante", codigo="ESTUDIANTE")
        estudiante = Persona.objects.create(
            nombres="Camila",
            apellidos="Resumen",
            email="camila.resumen@example.com",
        )
        PersonaRol.objects.create(
            persona=estudiante,
            rol=rol_estudiante,
            organizacion=self.organizacion,
            activo=True,
        )
        pago = Payment.objects.create(
            persona=estudiante,
            organizacion=self.organizacion,
            fecha_pago="2026-09-03",
            metodo_pago=Payment.Metodo.TRANSFERENCIA,
            aplica_iva=False,
            monto_referencia=18000,
            clases_asignadas=1,
        )
        disciplina = Disciplina.objects.create(organizacion=self.organizacion, nombre="Danza resumen")
        for dia in (5, 12):
            sesion = SesionClase.objects.create(
                disciplina=disciplina,
                fecha=f"2026-09-{dia:02d}",
                estado=SesionClase.Estado.COMPLETADA,
            )
            Asistencia.objects.create(sesion=sesion, persona=estudiante, estado=Asistencia.Estado.PRESENTE)

        self.client.force_login(self.user_admin)
        response = self.client.get(
            reverse("elemental_apps"),
            {
                "periodo_mes": 9,
                "periodo_anio": 2026,
                "organizacion": self.organizacion.pk,
                "persona_id": estudiante.pk,
            },
        )

        resumen = response.context["consulta_persona"]["persona"]
        self.assertEqual(response.status_code, 200)
        self.assertEqual(resumen["asistencias_registradas"], 2)
        self.assertEqual(resumen["pagos_registrados"], 1)
        self.assertEqual(resumen["monto_pagado"], pago.monto_total)
        self.assertEqual(resumen["resumen_periodo"]["clases_pagadas"], 1)
        self.assertEqual(resumen["resumen_periodo"]["clases_consumidas"], 1)
        self.assertEqual(resumen["resumen_periodo"]["deuda_pendiente"], 1)
        self.assertEqual(resumen["resumen_actual"]["saldo_clases"], 0)
        self.assertIn(f"persona={estudiante.pk}", resumen["pagos_url"])
        self.assertContains(response, "Situación actual")
        self.assertContains(response, "Danza resumen")

    def test_consulta_persona_no_agrega_saldo_actual_entre_organizaciones(self):
        rol_estudiante = Rol.objects.create(nombre="Estudiante", codigo="ESTUDIANTE")
        estudiante = Persona.objects.create(nombres="Saldo", apellidos="Multi Org")
        PersonaRol.objects.create(
            persona=estudiante,
            rol=rol_estudiante,
            organizacion=self.organizacion,
            activo=True,
        )
        self.client.force_login(self.user_staff)

        response = self.client.get(
            reverse("elemental_apps"),
            {"periodo_mes": 9, "periodo_anio": 2026, "persona_id": estudiante.pk},
        )

        self.assertIsNone(response.context["consulta_persona"]["persona"]["resumen_actual"])
        self.assertContains(response, "Selecciona una organización para calcular un saldo de clases comparable.")

    def test_proximas_sesiones_excluye_completadas(self):
        hoy = timezone.localdate()
        disciplina = Disciplina.objects.create(organizacion=self.organizacion, nombre="Agenda")
        completada = SesionClase.objects.create(
            disciplina=disciplina,
            fecha=hoy,
            estado=SesionClase.Estado.COMPLETADA,
        )
        programada = SesionClase.objects.create(
            disciplina=disciplina,
            fecha=hoy,
            estado=SesionClase.Estado.PROGRAMADA,
        )
        self.client.force_login(self.user_admin)

        response = self.client.get(
            reverse("elemental_apps"),
            {
                "periodo_mes": hoy.month,
                "periodo_anio": hoy.year,
                "organizacion": self.organizacion.pk,
            },
        )

        proximas = list(response.context["dashboard_academico"]["proximas_sesiones"])
        self.assertIn(programada, proximas)
        self.assertNotIn(completada, proximas)

    def test_topbar_muestra_logo_de_organizacion_seleccionada(self):
        self.organizacion.logo = "organizaciones/logos/org-ux.png"
        self.organizacion.save(update_fields=["logo"])
        self.client.force_login(self.user_admin)

        response = self.client.get(
            reverse("elemental_apps"),
            {"periodo_mes": 2, "periodo_anio": 2026, "organizacion": self.organizacion.pk},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="elemental-org-logo"', html=False)
        self.assertContains(response, "/media/organizaciones/logos/org-ux.png")
        self.assertContains(response, "Org UX")

    def test_topbar_muestra_fallback_si_organizacion_no_tiene_logo(self):
        self.client.force_login(self.user_admin)

        response = self.client.get(
            reverse("elemental_apps"),
            {"periodo_mes": 2, "periodo_anio": 2026, "organizacion": self.organizacion.pk},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="elemental-org-fallback"', html=False)
        self.assertContains(response, ">OU<", html=False)

    def test_topbar_con_todas_las_organizaciones_muestra_elemental_apps_sin_logo(self):
        self.client.force_login(self.user_admin)

        response = self.client.get(
            reverse("elemental_apps"),
            {"periodo_mes": 2, "periodo_anio": 2026},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Elemental Apps")
        self.assertContains(response, "Cambiar período y organización")
        self.assertContains(response, 'id="elementalContextControls"', html=False)
        self.assertNotContains(response, 'class="elemental-org-logo"', html=False)
        self.assertNotContains(response, 'class="elemental-org-fallback"', html=False)

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


class DjangoAdminSupportTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.superuser = User.objects.create_superuser(
            "admin_support_test_user",
            email="admin.support@example.com",
            password=TEST_PASSWORD,
        )
        self.no_staff_user = User.objects.create_user("admin_no_staff_test_user", password=TEST_PASSWORD)
        self.organizacion = Organizacion.objects.create(
            nombre="Org Admin",
            razon_social="Org Admin SPA",
            rut="77.777.777-7",
        )
        self.rol = Rol.objects.create(nombre="Estudiante", codigo="ESTUDIANTE")
        self.persona = Persona.objects.create(
            nombres="Admin",
            apellidos="Soporte",
            email="admin.soporte@example.com",
            rut="12.345.678-5",
        )
        PersonaRol.objects.create(persona=self.persona, rol=self.rol, organizacion=self.organizacion, activo=True)
        self.disciplina = Disciplina.objects.create(organizacion=self.organizacion, nombre="Admin Disciplina")
        self.sesion = SesionClase.objects.create(disciplina=self.disciplina, fecha="2026-05-01")
        self.asistencia = Asistencia.objects.create(sesion=self.sesion, persona=self.persona)
        self.documento = DocumentoTributario.objects.create(
            organizacion=self.organizacion,
            tipo_documento=DocumentoTributario.TipoDocumento.FACTURA_AFECTA,
            folio="ADM-1",
            fecha_emision="2026-05-01",
            nombre_emisor="Emisor Admin",
            rut_emisor="11.111.111-1",
            nombre_receptor="Receptor Admin",
            rut_receptor="22.222.222-2",
            monto_total=10000,
        )
        self.pago = Payment.objects.create(
            persona=self.persona,
            organizacion=self.organizacion,
            documento_tributario=self.documento,
            fecha_pago="2026-05-01",
            metodo_pago=Payment.Metodo.EFECTIVO,
            aplica_iva=False,
            monto_referencia=10000,
            clases_asignadas=1,
        )
        self.categoria = Category.objects.create(nombre="Ingreso admin", tipo=Category.Tipo.INGRESO)
        self.transaccion = Transaction.objects.create(
            organizacion=self.organizacion,
            categoria=self.categoria,
            fecha="2026-05-01",
            tipo=Transaction.Tipo.INGRESO,
            monto=10000,
            descripcion="Transaccion admin",
        )
        self.transaccion.documentos_tributarios.add(self.documento)
        self.audit_log = AuditLog.objects.create(
            usuario=self.superuser,
            accion=AuditLog.ACCION_CREAR,
            dominio="personas",
            modelo="personas.Persona",
            objeto_id=str(self.persona.pk),
            organizacion=self.organizacion,
            resumen="Persona creada",
            metadata={"persona_id": self.persona.pk},
        )

    def test_superuser_carga_changelists_modelos_criticos(self):
        self.client.force_login(self.superuser)
        admin_names = [
            "admin:personas_persona_changelist",
            "admin:personas_personarol_changelist",
            "admin:personas_organizacion_changelist",
            "admin:asistencias_sesionclase_changelist",
            "admin:asistencias_asistencia_changelist",
            "admin:finanzas_payment_changelist",
            "admin:finanzas_transaction_changelist",
            "admin:finanzas_documentotributario_changelist",
            "admin:auditoria_auditlog_changelist",
        ]

        for admin_name in admin_names:
            response = self.client.get(reverse(admin_name))
            self.assertEqual(response.status_code, 200, admin_name)

    def test_usuario_no_staff_no_entra_al_admin(self):
        self.client.force_login(self.no_staff_user)

        response = self.client.get(reverse("admin:index"))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("admin:login"), response.url)

    def test_monitor_no_aparece_en_admin_index(self):
        self.client.force_login(self.superuser)

        response = self.client.get(reverse("admin:index"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Monitor")

    def test_delete_selected_no_disponible_en_modelos_criticos(self):
        self.client.force_login(self.superuser)
        admin_names = [
            "admin:personas_persona_changelist",
            "admin:personas_personarol_changelist",
            "admin:personas_organizacion_changelist",
            "admin:asistencias_sesionclase_changelist",
            "admin:asistencias_asistencia_changelist",
            "admin:finanzas_payment_changelist",
            "admin:finanzas_transaction_changelist",
            "admin:finanzas_documentotributario_changelist",
            "admin:auditoria_auditlog_changelist",
        ]

        for admin_name in admin_names:
            response = self.client.get(reverse(admin_name))
            self.assertNotContains(response, 'value="delete_selected"', html=False)

    def test_busquedas_admin_basicas_no_rompen(self):
        self.client.force_login(self.superuser)
        casos = [
            ("admin:personas_persona_changelist", "Soporte"),
            ("admin:finanzas_payment_changelist", "Soporte"),
            ("admin:finanzas_documentotributario_changelist", "ADM-1"),
        ]

        for admin_name, query in casos:
            response = self.client.get(reverse(admin_name), {"q": query})
            self.assertEqual(response.status_code, 200, admin_name)

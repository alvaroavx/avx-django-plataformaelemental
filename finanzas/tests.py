import csv
from io import BytesIO, StringIO
from datetime import date
from urllib.parse import urlencode
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone
from decimal import Decimal
from openpyxl import load_workbook

from auditoria.models import AuditLog
from finanzas.forms import PaymentForm, TransactionForm
from finanzas.services import asociar_asistencia_a_pago, resumen_financiero_estudiante
from finanzas.services.reconciliacion import reconciliar_integridad_dominio
from finanzas.services.reversas import revertir_pago
from finanzas.services.cuadratura_v1 import prepare_month
from finanzas.services.pagos import (
    confirmar_lote_pagos,
    crear_persona_estudiante_desde_modal,
    enriquecer_pagos_para_listado,
    resumen_consumos_pago,
    texto_copiable_operativo_pago,
)

from asistencias.forms import PersonaRapidaForm
from asistencias.models import Asistencia, ClaseLiberada, Disciplina, SesionClase
from personas.models import Organizacion, Persona, PersonaRol, Rol
from personas.test_factories import crear_usuario_con_rol

from finanzas.models import (
    AttendanceConsumption,
    Category,
    Payment,
    PaymentPlan,
    Transaction,
    LotePago,
)


TEST_PASSWORD = "not-a-real-test-password"


class FinanzasServicesCompatibilityTests(SimpleTestCase):
    def test_imports_publicos_antiguos_siguen_disponibles(self):
        from finanzas.services import (
            asignar_consumo_asistencia,
            asociar_asistencia_a_pago,
            imputar_pago_a_deudas,
            resumen_financiero_estudiante,
            resumen_financiero_estudiante_periodo,
        )

        self.assertTrue(callable(asignar_consumo_asistencia))
        self.assertTrue(callable(asociar_asistencia_a_pago))
        self.assertTrue(callable(imputar_pago_a_deudas))
        self.assertTrue(callable(resumen_financiero_estudiante))
        self.assertTrue(callable(resumen_financiero_estudiante_periodo))


class FinanzasAccessTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.org = Organizacion.objects.create(
            nombre="Org Finanzas",
            razon_social="Org Finanzas SPA",
            rut="22.222.222-2",
        )
        self.rol_admin = Rol.objects.create(nombre="Administrador", codigo="ADMINISTRADOR")
        self.rol_estudiante = Rol.objects.create(nombre="Estudiante", codigo="ESTUDIANTE")
        self.rol_finanzas = Rol.objects.create(nombre="Finanzas", codigo="FINANZAS")
        self.rol_profesor = Rol.objects.create(nombre="Profesor", codigo="PROFESOR")
        self.rol_solo_lectura = Rol.objects.create(nombre="Solo lectura", codigo="SOLO_LECTURA")

        self.user_admin = User.objects.create_user("admin_fin", password=TEST_PASSWORD)
        self.persona_admin = Persona.objects.create(
            nombres="Admin",
            apellidos="Fin",
            email="adminfin@example.com",
            user=self.user_admin,
        )
        PersonaRol.objects.create(
            persona=self.persona_admin,
            rol=self.rol_admin,
            organizacion=self.org,
            activo=True,
        )

        self.user_no_admin = User.objects.create_user("noadmin_fin", password=TEST_PASSWORD)
        self.persona_no_admin = Persona.objects.create(
            nombres="No",
            apellidos="Admin",
            email="noadmin@example.com",
            user=self.user_no_admin,
        )
        PersonaRol.objects.create(
            persona=self.persona_no_admin,
            rol=self.rol_estudiante,
            organizacion=self.org,
            activo=True,
        )
        self.user_finanzas = User.objects.create_user("finanzas_user", password=TEST_PASSWORD)
        self.persona_finanzas = Persona.objects.create(
            nombres="Finanzas",
            apellidos="User",
            email="finanzas@example.com",
            user=self.user_finanzas,
        )
        PersonaRol.objects.create(
            persona=self.persona_finanzas,
            rol=self.rol_finanzas,
            organizacion=self.org,
            activo=True,
        )
        self.user_profesor = User.objects.create_user("profesor_fin", password=TEST_PASSWORD)
        self.persona_profesor = Persona.objects.create(
            nombres="Profesor",
            apellidos="Fin",
            email="profesorfin@example.com",
            user=self.user_profesor,
        )
        PersonaRol.objects.create(
            persona=self.persona_profesor,
            rol=self.rol_profesor,
            organizacion=self.org,
            activo=True,
        )
        self.user_solo_lectura = User.objects.create_user("lectura_fin", password=TEST_PASSWORD)
        self.persona_solo_lectura = Persona.objects.create(
            nombres="Lectura",
            apellidos="Fin",
            email="lecturafin@example.com",
            user=self.user_solo_lectura,
        )
        PersonaRol.objects.create(
            persona=self.persona_solo_lectura,
            rol=self.rol_solo_lectura,
            organizacion=self.org,
            activo=True,
        )
        self.user_sin_rol = User.objects.create_user("sinrol_fin", password=TEST_PASSWORD)
        self.persona_sin_rol = Persona.objects.create(
            nombres="Sin",
            apellidos="Rol",
            email="sinrolfin@example.com",
            user=self.user_sin_rol,
        )

    def _url_con_organizacion(self, url, **params):
        return f"{url}?{urlencode({'organizacion': self.org.pk, **params})}"

    def test_finanzas_dashboard_requiere_admin(self):
        self.client.force_login(self.user_no_admin)
        response = self.client.get(reverse("finanzas:dashboard"))
        self.assertEqual(response.status_code, 403)

    def test_finanzas_dashboard_admin_ok(self):
        self.client.force_login(self.user_admin)
        response = self.client.get(reverse("finanzas:dashboard"), {"organizacion": self.org.pk})
        self.assertEqual(response.status_code, 200)

    def test_preparar_mes_exporta_operacion_y_pago_sin_mutar_registros(self):
        estudiante = Persona.objects.create(nombres="Alumna", apellidos="Ficticia", email="alumna-ficticia@example.com")
        PersonaRol.objects.create(persona=estudiante, rol=self.rol_estudiante, organizacion=self.org, activo=True)
        categoria = Category.objects.create(nombre="Cobranza ficticia", tipo=Category.Tipo.INGRESO)
        transaction = Transaction.objects.create(
            organizacion=self.org, categoria=categoria, fecha=date(2026, 8, 28),
            tipo=Transaction.Tipo.INGRESO, monto=Decimal("50000"), descripcion="Taller ficticio",
        )
        payment = Payment.objects.create(
            persona=estudiante, organizacion=self.org, fecha_pago=date(2026, 9, 2),
            aplica_iva=False, monto_referencia=Decimal("50000"), transaccion=transaction,
        )
        payload = prepare_month(organization=self.org, year=2026, month=9)
        self.assertEqual((payload["summary"]["operations"], payload["summary"]["payments"], payload["summary"]["total_payments"]), (1, 1, 50000))
        self.assertEqual(payload["operations"][0]["operation_date"], "2026-08-28")
        self.assertEqual(payload["operations"][0]["service_period"], "2026-09")
        self.client.force_login(self.user_finanzas)
        params = {"organizacion": self.org.pk, "periodo_mes": 9, "periodo_anio": 2026}
        self.assertContains(self.client.get(reverse("finanzas:preparar_mes"), params), "Descargar para Cuadratura")
        response = self.client.get(reverse("finanzas:descargar_cuadratura"), params)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Payment.objects.get(pk=payment.pk).transaccion_id, transaction.pk)

    def test_preparar_mes_declara_pagos_no_elegibles(self):
        estudiante = Persona.objects.create(nombres="Otra", apellidos="Ficticia", email="otra-ficticia@example.com")
        PersonaRol.objects.create(persona=estudiante, rol=self.rol_estudiante, organizacion=self.org, activo=True)
        Payment.objects.create(persona=estudiante, organizacion=self.org, fecha_pago=date(2026, 9, 3), aplica_iva=False, monto_referencia=Decimal("10000"))
        payload = prepare_month(organization=self.org, year=2026, month=9)
        self.assertEqual((payload["summary"]["operations"], payload["summary"]["pending"]), (0, 1))
        self.assertIn("missing_linked_transaction", payload["pending_records"][0]["reasons"])


    def test_listado_pagos_busca_persona_por_fragmentos_sin_tildes(self):
        persona = Persona.objects.create(
            nombres="Bárbara Inés",
            apellidos="Muñoz Cáceres",
            email="barbara.munoz@example.com",
        )
        PersonaRol.objects.create(
            persona=persona,
            rol=self.rol_estudiante,
            organizacion=self.org,
            activo=True,
        )
        Payment.objects.create(
            persona=persona,
            organizacion=self.org,
            fecha_pago="2026-08-10",
            metodo_pago=Payment.Metodo.EFECTIVO,
            aplica_iva=False,
            monto_referencia=10000,
        )
        self.client.force_login(self.user_finanzas)

        response = self.client.get(
            reverse("finanzas:pagos_list"),
            {
                "organizacion": self.org.pk,
                "periodo_mes": 8,
                "periodo_anio": 2026,
                "q": "barbara munoz",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Bárbara Inés Muñoz Cáceres")

    def test_profesor_no_accede_a_finanzas_completa(self):
        self.client.force_login(self.user_profesor)
        response = self.client.get(reverse("finanzas:dashboard"), {"organizacion": self.org.pk})
        self.assertEqual(response.status_code, 403)

    def test_solo_lectura_no_puede_hacer_post_sensible(self):
        self.client.force_login(self.user_solo_lectura)
        response = self.client.post(reverse("finanzas:pagos_list"), {"organizacion": self.org.pk})
        self.assertEqual(response.status_code, 403)

    def test_usuario_sin_rol_no_accede_a_vistas_sensibles(self):
        self.client.force_login(self.user_sin_rol)
        response = self.client.get(reverse("finanzas:pagos_list"), {"organizacion": self.org.pk})
        self.assertEqual(response.status_code, 403)

    def test_permiso_finanzas_considera_organizacion_filtrada(self):
        otra_org = Organizacion.objects.create(
            nombre="Org Sin Permiso",
            razon_social="Org Sin Permiso SPA",
            rut="99.999.999-9",
        )
        self.client.force_login(self.user_finanzas)
        response = self.client.get(reverse("finanzas:pagos_list"), {"organizacion": otra_org.pk})
        self.assertEqual(response.status_code, 403)

    def test_dashboard_mensual_usa_transacciones_como_fuente_contable(self):
        categoria_ingreso = Category.objects.create(nombre="Ingreso dashboard", tipo=Category.Tipo.INGRESO, activa=True)
        categoria_egreso = Category.objects.create(nombre="Egreso dashboard", tipo=Category.Tipo.EGRESO, activa=True)
        Payment.objects.create(
            persona=self.persona_no_admin,
            organizacion=self.org,
            fecha_pago="2026-02-10",
            metodo_pago=Payment.Metodo.EFECTIVO,
            aplica_iva=False,
            monto_referencia=100000,
            clases_asignadas=4,
        )
        Transaction.objects.create(
            organizacion=self.org,
            categoria=categoria_ingreso,
            fecha="2026-02-10",
            tipo=Transaction.Tipo.INGRESO,
            monto=25000,
            descripcion="Ingreso contable",
        )
        Transaction.objects.create(
            organizacion=self.org,
            categoria=categoria_egreso,
            fecha="2026-02-11",
            tipo=Transaction.Tipo.EGRESO,
            monto=5000,
            descripcion="Egreso contable",
        )

        self.client.force_login(self.user_finanzas)
        response = self.client.get(
            reverse("finanzas:dashboard"),
            {"periodo_mes": 2, "periodo_anio": 2026, "organizacion": self.org.pk},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["ingresos_contables"], 25000)
        self.assertEqual(response.context["egresos_contables"], 5000)
        self.assertEqual(response.context["saldo_contable"], 20000)
        self.assertEqual(response.context["pagos_operacionales_monto"], 100000)
        self.assertEqual(response.context["total_transacciones"], 2)

    def test_dashboard_mensual_respeta_organizacion_y_periodo(self):
        categoria = Category.objects.create(nombre="Ingreso filtro dashboard", tipo=Category.Tipo.INGRESO, activa=True)
        otra_org = Organizacion.objects.create(nombre="Org Dashboard", razon_social="Org Dashboard SPA", rut="98.888.888-8")
        Transaction.objects.create(
            organizacion=self.org,
            categoria=categoria,
            fecha="2026-02-10",
            tipo=Transaction.Tipo.INGRESO,
            monto=25000,
            descripcion="Incluida",
        )
        Transaction.objects.create(
            organizacion=self.org,
            categoria=categoria,
            fecha="2026-03-10",
            tipo=Transaction.Tipo.INGRESO,
            monto=99999,
            descripcion="Fuera periodo",
        )
        Transaction.objects.create(
            organizacion=otra_org,
            categoria=categoria,
            fecha="2026-02-10",
            tipo=Transaction.Tipo.INGRESO,
            monto=99999,
            descripcion="Fuera organizacion",
        )

        self.client.force_login(self.user_admin)
        response = self.client.get(
            reverse("finanzas:dashboard"),
            {"periodo_mes": 2, "periodo_anio": 2026, "organizacion": self.org.pk},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["ingresos_contables"], 25000)
        self.assertEqual(response.context["total_transacciones"], 1)


    def test_dashboard_finanzas_solo_lectura_no_ve_acciones_mutables(self):
        self.client.force_login(self.user_solo_lectura)
        response = self.client.get(
            reverse("finanzas:dashboard"),
            {"periodo_mes": 2, "periodo_anio": 2026, "organizacion": self.org.pk},
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Agregar pago")
        self.assertNotContains(response, "Agregar documento")
        self.assertNotContains(response, "Agregar transacción")

    def test_dashboard_finanzas_profesor_no_accede_a_acciones_financieras(self):
        self.client.force_login(self.user_profesor)
        response = self.client.get(
            reverse("finanzas:dashboard"),
            {"periodo_mes": 2, "periodo_anio": 2026, "organizacion": self.org.pk},
        )

        self.assertEqual(response.status_code, 403)

    def test_transacciones_list_abre_modal_desde_dashboard(self):
        self.client.force_login(self.user_finanzas)
        response = self.client.get(
            reverse("finanzas:transacciones_list"),
            {
                "periodo_mes": 2,
                "periodo_anio": 2026,
                "organizacion": self.org.pk,
                "open": "nueva_transaccion",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["open_nueva_transaccion"])



    def test_libro_caja_csv_respeta_organizacion_y_periodo(self):
        categoria = Category.objects.create(nombre="Ingreso libro filtros", tipo=Category.Tipo.INGRESO, activa=True)
        otra_org = Organizacion.objects.create(nombre="Org Libro", razon_social="Org Libro SPA", rut="97.777.777-7")
        Transaction.objects.create(
            organizacion=self.org,
            categoria=categoria,
            fecha="2026-02-02",
            tipo=Transaction.Tipo.INGRESO,
            monto=15000,
            descripcion="Incluida",
        )
        Transaction.objects.create(
            organizacion=self.org,
            categoria=categoria,
            fecha="2026-03-02",
            tipo=Transaction.Tipo.INGRESO,
            monto=99000,
            descripcion="Fuera periodo",
        )
        Transaction.objects.create(
            organizacion=otra_org,
            categoria=categoria,
            fecha="2026-02-02",
            tipo=Transaction.Tipo.INGRESO,
            monto=88000,
            descripcion="Fuera organizacion",
        )

        self.client.force_login(self.user_admin)
        response = self.client.get(
            reverse("finanzas:export_libro_caja_csv"),
            {"periodo_mes": 2, "periodo_anio": 2026, "organizacion": self.org.pk},
        )

        contenido = response.content.decode("utf-8-sig")
        rows = list(csv.reader(contenido.splitlines()))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(rows), 2)
        self.assertIn("Incluida", contenido)
        self.assertNotIn("Fuera periodo", contenido)
        self.assertNotIn("Fuera organizacion", contenido)

    def test_libro_caja_csv_bloquea_periodo_todos(self):
        self.client.force_login(self.user_admin)
        response = self.client.get(
            reverse("finanzas:export_libro_caja_csv"),
            {"periodo_mes": "todos", "periodo_anio": 2026, "organizacion": self.org.pk},
        )

        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "requiere seleccionar un mes y un año", status_code=400)

    def test_libro_caja_csv_permisos(self):
        self.client.force_login(self.user_sin_rol)
        response = self.client.get(
            reverse("finanzas:export_libro_caja_csv"),
            {"periodo_mes": 2, "periodo_anio": 2026, "organizacion": self.org.pk},
        )
        self.assertEqual(response.status_code, 403)

        self.client.force_login(self.user_profesor)
        response = self.client.get(
            reverse("finanzas:export_libro_caja_csv"),
            {"periodo_mes": 2, "periodo_anio": 2026, "organizacion": self.org.pk},
        )
        self.assertEqual(response.status_code, 403)

        self.client.force_login(self.user_finanzas)
        response = self.client.get(
            reverse("finanzas:export_libro_caja_csv"),
            {"periodo_mes": 2, "periodo_anio": 2026, "organizacion": self.org.pk},
        )
        self.assertEqual(response.status_code, 200)

    def _xlsx_rows(self, response):
        workbook = load_workbook(BytesIO(response.content))
        return list(workbook.active.iter_rows(values_only=True))

    def test_export_pagos_alumnos_xlsx_respeta_periodo_organizacion_y_no_es_contable(self):
        otra_org = Organizacion.objects.create(nombre="Org Pagos XLSX", razon_social="Org Pagos XLSX SPA", rut="76.111.111-1")
        Payment.objects.create(
            persona=self.persona_no_admin,
            organizacion=self.org,
            fecha_pago="2026-02-04",
            metodo_pago=Payment.Metodo.TRANSFERENCIA,
            aplica_iva=False,
            monto_referencia=45000,
            clases_asignadas=4,
            observaciones="Pago incluido",
        )
        Payment.objects.create(
            persona=self.persona_no_admin,
            organizacion=self.org,
            fecha_pago="2026-03-04",
            metodo_pago=Payment.Metodo.TRANSFERENCIA,
            aplica_iva=False,
            monto_referencia=99000,
            clases_asignadas=4,
            observaciones="Fuera periodo",
        )
        Payment.objects.create(
            persona=self.persona_no_admin,
            organizacion=otra_org,
            fecha_pago="2026-02-04",
            metodo_pago=Payment.Metodo.TRANSFERENCIA,
            aplica_iva=False,
            monto_referencia=88000,
            clases_asignadas=4,
            observaciones="Fuera organizacion",
        )

        self.client.force_login(self.user_finanzas)
        response = self.client.get(
            reverse("finanzas:export_pagos_alumnos_xlsx"),
            {"periodo_mes": 2, "periodo_anio": 2026, "organizacion": self.org.pk},
        )

        rows = self._xlsx_rows(response)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(rows[0][0], "Fecha pago")
        self.assertIn("Estado", rows[0])
        contenido = str(rows)
        self.assertIn("Pago incluido", contenido)
        self.assertNotIn("Fuera periodo", contenido)
        self.assertNotIn("Fuera organizacion", contenido)

    def test_export_transacciones_xlsx_es_contable_y_no_duplica_pagos(self):
        categoria = Category.objects.create(nombre="Ingreso XLSX", tipo=Category.Tipo.INGRESO, activa=True)
        Transaction.objects.create(
            organizacion=self.org,
            categoria=categoria,
            fecha="2026-02-05",
            tipo=Transaction.Tipo.INGRESO,
            monto=12000,
            descripcion="Transaccion real",
        )
        Payment.objects.create(
            persona=self.persona_no_admin,
            organizacion=self.org,
            fecha_pago="2026-02-05",
            metodo_pago=Payment.Metodo.EFECTIVO,
            aplica_iva=False,
            monto_referencia=99000,
            clases_asignadas=1,
            observaciones="Pago operacional no contable",
        )

        self.client.force_login(self.user_admin)
        response = self.client.get(
            reverse("finanzas:export_transacciones_xlsx"),
            {"periodo_mes": 2, "periodo_anio": 2026, "organizacion": self.org.pk},
        )

        rows = self._xlsx_rows(response)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(rows[0][0], "Fecha")
        self.assertIn("Msg", rows[0])
        contenido = str(rows)
        self.assertIn("Transaccion real", contenido)
        self.assertNotIn("Pago operacional no contable", contenido)

    def test_export_pagos_profesores_xlsx_usa_fuente_operacional_existente(self):
        disciplina = Disciplina.objects.create(organizacion=self.org, nombre="Danza XLSX")
        sesion = SesionClase.objects.create(
            disciplina=disciplina,
            fecha="2026-02-06",
            estado=SesionClase.Estado.COMPLETADA,
        )
        sesion.profesores.add(self.persona_profesor)
        PersonaRol.objects.filter(persona=self.persona_profesor, rol=self.rol_profesor, organizacion=self.org).update(
            valor_clase=Decimal("10000"),
            retencion_sii=Decimal("10"),
        )
        Asistencia.objects.create(sesion=sesion, persona=self.persona_no_admin, estado=Asistencia.Estado.PRESENTE)

        self.client.force_login(self.user_finanzas)
        response = self.client.get(
            reverse("finanzas:export_pagos_profesores_xlsx"),
            {"periodo_mes": 2, "periodo_anio": 2026, "organizacion": self.org.pk},
        )

        rows = self._xlsx_rows(response)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(rows[0][0], "Periodo")
        contenido = str(rows)
        self.assertIn("Profesor Fin", contenido)
        self.assertIn("Estimado operacional", contenido)
        self.assertIn("9000", contenido)

    def test_exports_financieros_xlsx_bloquean_roles_no_autorizados(self):
        for url_name in (
            "finanzas:export_pagos_alumnos_xlsx",
            "finanzas:export_pagos_profesores_xlsx",
            "finanzas:export_transacciones_xlsx",
        ):
            self.client.force_login(self.user_solo_lectura)
            response = self.client.get(reverse(url_name), {"periodo_mes": 2, "periodo_anio": 2026, "organizacion": self.org.pk})
            self.assertEqual(response.status_code, 403)

            self.client.force_login(self.user_profesor)
            response = self.client.get(reverse(url_name), {"periodo_mes": 2, "periodo_anio": 2026, "organizacion": self.org.pk})
            self.assertEqual(response.status_code, 403)

            self.client.force_login(self.user_finanzas)
            response = self.client.get(reverse(url_name), {"periodo_mes": 2, "periodo_anio": 2026, "organizacion": self.org.pk})
            self.assertEqual(response.status_code, 200)

    def test_pagos_list_permita_abrir_modal_con_estudiante_preseleccionado(self):
        self.client.force_login(self.user_finanzas)
        response = self.client.get(
            reverse("finanzas:pagos_list"),
            {
                "periodo_mes": 2,
                "periodo_anio": 2026,
                "organizacion": self.org.pk,
                "persona": self.persona_no_admin.pk,
                "open": "registrar_pago",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["open_registrar_pago"])
        self.assertEqual(str(response.context["form"].initial["persona"]), str(self.persona_no_admin.pk))

    def test_pagos_list_filtra_realmente_por_persona(self):
        otra_persona = Persona.objects.create(
            nombres="Otra",
            apellidos="Estudiante",
            email="otra.estudiante@example.com",
        )
        PersonaRol.objects.create(
            persona=otra_persona,
            rol=self.rol_estudiante,
            organizacion=self.org,
            activo=True,
        )
        pago_objetivo = Payment.objects.create(
            persona=self.persona_no_admin,
            organizacion=self.org,
            fecha_pago="2026-09-05",
            metodo_pago=Payment.Metodo.EFECTIVO,
            aplica_iva=False,
            monto_referencia=12000,
        )
        Payment.objects.create(
            persona=otra_persona,
            organizacion=self.org,
            fecha_pago="2026-09-06",
            metodo_pago=Payment.Metodo.EFECTIVO,
            aplica_iva=False,
            monto_referencia=15000,
        )
        self.client.force_login(self.user_finanzas)

        response = self.client.get(
            reverse("finanzas:pagos_list"),
            {
                "periodo_mes": 9,
                "periodo_anio": 2026,
                "organizacion": self.org.pk,
                "persona": self.persona_no_admin.pk,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual([pago.pk for pago in response.context["pagos"]], [pago_objetivo.pk])
        self.assertEqual(response.context["persona_filtrada"], self.persona_no_admin)
        self.assertContains(response, "Mostrando únicamente los pagos de")
        self.assertContains(response, "Ver todos los pagos")
        self.assertContains(response, "/static/plataformaelemental/js/shell.js")



    def test_pagos_list_error_validacion_mantiene_modal_abierto(self):
        self.client.force_login(self.user_admin)
        response = self.client.post(
            reverse("finanzas:pagos_list")
            + f"?periodo_mes=2&periodo_anio=2026&organizacion={self.org.pk}"
            "&open=registrar_pago",
            {
                "guardar_pago": "1",
                "organizacion": self.org.pk,
                "persona": "",
                "fecha_pago": "2026-02-27",
                "metodo_pago": Payment.Metodo.EFECTIVO,
                "monto_referencia": "",
                "clases_asignadas": "",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["open_registrar_pago"])
        self.assertTrue(response.context["form"].errors)
        self.assertContains(response, "registrarPagoModal")


    def test_pago_edit_get_redirige_a_listado_con_modal(self):
        pago = Payment.objects.create(
            persona=self.persona_no_admin,
            organizacion=self.org,
            fecha_pago="2026-02-27",
            metodo_pago=Payment.Metodo.EFECTIVO,
            aplica_iva=False,
            monto_referencia=10000,
            clases_asignadas=1,
        )
        self.client.force_login(self.user_admin)
        query = f"periodo_mes=2&periodo_anio=2026&organizacion={self.org.pk}&q=ana&metodo=transferencia"
        response = self.client.get(f"{reverse('finanzas:pago_edit', kwargs={'pk': pago.pk})}?{query}")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response["Location"],
            f"{reverse('finanzas:pagos_list')}?{query}&editar_pago={pago.pk}",
        )

    def test_pagos_list_abre_modal_edicion_cuando_recibe_editar_pago(self):
        pago = Payment.objects.create(
            persona=self.persona_no_admin,
            organizacion=self.org,
            fecha_pago="2026-02-27",
            metodo_pago=Payment.Metodo.EFECTIVO,
            aplica_iva=False,
            monto_referencia=10000,
            clases_asignadas=1,
        )
        self.client.force_login(self.user_admin)
        response = self.client.get(
            reverse("finanzas:pagos_list"),
            {
                "periodo_mes": 2,
                "periodo_anio": 2026,
                "organizacion": self.org.pk,
                "editar_pago": pago.pk,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["edit_pago"], pago)
        self.assertIsNotNone(response.context["edit_form"])
        self.assertContains(response, 'id="editarPagoModal"', html=False)
        self.assertContains(response, f'action="{reverse("finanzas:pago_edit", kwargs={"pk": pago.pk})}?periodo_mes=2&amp;periodo_anio=2026&amp;organizacion={self.org.pk}"', html=False)
        self.assertContains(response, f'href="{reverse("finanzas:pagos_list")}?periodo_mes=2&amp;periodo_anio=2026&amp;organizacion={self.org.pk}"', html=False)


    def test_pagos_list_crea_persona_rapida_como_estudiante_en_organizacion_filtrada(self):
        self.client.force_login(self.user_admin)

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                reverse("finanzas:pagos_list") + f"?periodo_mes=2&periodo_anio=2026&organizacion={self.org.pk}",
                {
                    "nombres": "Lucia",
                    "apellidos": "Perez",
                    "telefono": "999999",
                    "agregar_persona": "1",
                },
            )

        self.assertEqual(response.status_code, 302)
        persona = Persona.objects.get(nombres="Lucia", apellidos="Perez")
        self.assertTrue(
            PersonaRol.objects.filter(
                persona=persona,
                rol__codigo="ESTUDIANTE",
                organizacion=self.org,
                activo=True,
            ).exists()
        )
        self.assertTrue(
            AuditLog.objects.filter(
                dominio="personas",
                accion=AuditLog.ACCION_CREAR,
                objeto_id=str(persona.pk),
            ).exists()
        )

    def test_pagos_list_nueva_persona_sin_organizacion_se_deniega(self):
        self.client.force_login(self.user_admin)

        response = self.client.post(
            reverse("finanzas:pagos_list") + "?periodo_mes=2&periodo_anio=2026",
            {
                "nombres": "Mario",
                "apellidos": "Lopez",
                "telefono": "888888",
                "agregar_persona": "1",
            },
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(Persona.objects.filter(nombres="Mario", apellidos="Lopez").exists())

    def test_transaccion_detail_muestra_iframe_pdf(self):
        categoria = Category.objects.create(nombre="Arriendo", tipo="egreso", activa=True)
        archivo = SimpleUploadedFile(
            "comprobante.pdf",
            b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF",
            content_type="application/pdf",
        )
        transaccion = Transaction.objects.create(
            organizacion=self.org,
            categoria=categoria,
            fecha="2026-02-27",
            tipo=Transaction.Tipo.EGRESO,
            monto=15000,
            descripcion="Pago de arriendo",
            archivo=archivo,
        )

        self.client.force_login(self.user_admin)
        query = f"periodo_mes=2&periodo_anio=2026&organizacion={self.org.pk}"
        response = self.client.get(f"{reverse('finanzas:transaccion_detail', kwargs={'pk': transaccion.pk})}?{query}")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["archivo_es_pdf"])
        self.assertContains(response, "<iframe", html=False)
        self.assertContains(response, reverse("finanzas:transaccion_archivo", kwargs={"pk": transaccion.pk}))

    def test_transaccion_detail_muestra_imagen_inline(self):
        categoria = Category.objects.create(nombre="Movilidad", tipo="egreso", activa=True)
        archivo = SimpleUploadedFile(
            "comprobante.jpg",
            b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xd9",
            content_type="image/jpeg",
        )
        transaccion = Transaction.objects.create(
            organizacion=self.org,
            categoria=categoria,
            fecha="2026-02-27",
            tipo=Transaction.Tipo.EGRESO,
            monto=18000,
            descripcion="Taxi",
            archivo=archivo,
        )

        self.client.force_login(self.user_admin)
        response = self.client.get(
            reverse("finanzas:transaccion_detail", kwargs={"pk": transaccion.pk}),
            {"organizacion": self.org.pk},
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["archivo_es_pdf"])
        self.assertTrue(response.context["archivo_es_imagen"])
        self.assertContains(response, "<img", html=False)
        self.assertContains(response, reverse("finanzas:transaccion_archivo", kwargs={"pk": transaccion.pk}))

    def test_transaccion_archivo_permite_iframe_sameorigin(self):
        categoria = Category.objects.create(nombre="Honorarios", tipo="egreso", activa=True)
        archivo = SimpleUploadedFile(
            "respaldo.pdf",
            b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF",
            content_type="application/pdf",
        )
        transaccion = Transaction.objects.create(
            organizacion=self.org,
            categoria=categoria,
            fecha="2026-02-27",
            tipo=Transaction.Tipo.EGRESO,
            monto=9900,
            descripcion="Honorarios",
            archivo=archivo,
        )

        self.client.force_login(self.user_admin)
        response = self.client.get(
            reverse("finanzas:transaccion_archivo", kwargs={"pk": transaccion.pk}),
            {"organizacion": self.org.pk},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["X-Frame-Options"], "SAMEORIGIN")
        self.assertIn("inline;", response["Content-Disposition"])



    def test_reporte_categorias_muestra_grafico_torta(self):
        categoria = Category.objects.create(nombre="Arriendo sala", tipo="egreso", activa=True)
        Transaction.objects.create(
            organizacion=self.org,
            categoria=categoria,
            fecha="2026-02-27",
            tipo=Transaction.Tipo.EGRESO,
            monto=25000,
            descripcion="Arriendo febrero",
        )

        self.client.force_login(self.user_admin)
        response = self.client.get(
            reverse("finanzas:reporte_categorias"),
            {"periodo_mes": 2, "periodo_anio": 2026, "organizacion": self.org.pk},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'canvas id="categoriasChart"', html=False)
        self.assertContains(response, "Chart(", html=False)
        self.assertContains(response, "Arriendo sala")

    def test_export_pagos_csv_mantiene_headers_y_filas_filtradas(self):
        Payment.objects.create(
            persona=self.persona_no_admin,
            organizacion=self.org,
            fecha_pago="2026-02-25",
            metodo_pago=Payment.Metodo.TRANSFERENCIA,
            numero_comprobante="FEB-1",
            aplica_iva=False,
            monto_referencia=10000,
            clases_asignadas=2,
        )
        Payment.objects.create(
            persona=self.persona_no_admin,
            organizacion=self.org,
            fecha_pago="2026-03-01",
            metodo_pago=Payment.Metodo.EFECTIVO,
            aplica_iva=False,
            monto_referencia=5000,
            clases_asignadas=1,
        )

        self.client.force_login(self.user_admin)
        response = self.client.get(
            reverse("finanzas:export_pagos_csv"),
            {"periodo_mes": 2, "periodo_anio": 2026, "organizacion": self.org.pk},
        )

        rows = list(csv.reader(response.content.decode().splitlines()))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Disposition"], 'attachment; filename="pagos_finanzas.csv"')
        self.assertEqual(rows[0], ["Fecha", "Organizacion", "Persona", "Metodo", "Neto", "IVA", "Total", "Clases"])
        self.assertEqual(len(rows), 2)
        self.assertEqual(
            rows[1],
            [
                "2026-02-25",
                "Org Finanzas",
                "No Admin",
                "Transferencia",
                "10000.00",
                "0.00",
                "10000.00",
                "2",
            ],
        )

    def test_export_transacciones_csv_mantiene_headers_y_filas_filtradas(self):
        categoria_ingreso = Category.objects.create(nombre="Ventas clases", tipo=Category.Tipo.INGRESO, activa=True)
        categoria_egreso = Category.objects.create(nombre="Arriendo sala", tipo=Category.Tipo.EGRESO, activa=True)
        Transaction.objects.create(
            organizacion=self.org,
            categoria=categoria_ingreso,
            fecha="2026-02-25",
            tipo=Transaction.Tipo.INGRESO,
            monto=25000,
            descripcion="Ingreso febrero",
        )
        Transaction.objects.create(
            organizacion=self.org,
            categoria=categoria_egreso,
            fecha="2026-03-01",
            tipo=Transaction.Tipo.EGRESO,
            monto=12000,
            descripcion="Egreso marzo",
        )

        self.client.force_login(self.user_admin)
        response = self.client.get(
            reverse("finanzas:export_transacciones_csv"),
            {"periodo_mes": 2, "periodo_anio": 2026, "organizacion": self.org.pk},
        )

        rows = list(csv.reader(response.content.decode().splitlines()))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Disposition"], 'attachment; filename="transacciones_finanzas.csv"')
        self.assertEqual(rows[0], ["Fecha", "Organizacion", "Tipo", "Categoria", "Monto", "Descripcion"])
        self.assertEqual(len(rows), 2)
        self.assertEqual(
            rows[1],
            [
                "2026-02-25",
                "Org Finanzas",
                "Ingreso",
                "Ventas clases",
                "25000.00",
                "Ingreso febrero",
            ],
        )

    def test_payment_plan_primer_plan_queda_por_defecto_y_se_puede_reasignar(self):
        plan_1 = PaymentPlan.objects.create(
            organizacion=self.org,
            nombre="Plan Inicial",
            num_clases=4,
            precio=20000,
            activo=True,
        )
        plan_1.refresh_from_db()
        self.assertTrue(plan_1.es_por_defecto)

        plan_2 = PaymentPlan.objects.create(
            organizacion=self.org,
            nombre="Plan Nuevo",
            num_clases=8,
            precio=35000,
            activo=True,
        )
        plan_2.refresh_from_db()
        self.assertFalse(plan_2.es_por_defecto)

        plan_2.es_por_defecto = True
        plan_2.save()
        plan_1.refresh_from_db()
        plan_2.refresh_from_db()

        self.assertFalse(plan_1.es_por_defecto)
        self.assertTrue(plan_2.es_por_defecto)

        plan_2.delete()
        plan_1.refresh_from_db()
        self.assertTrue(plan_1.es_por_defecto)

    def test_payment_form_precarga_plan_por_defecto_de_la_organizacion(self):
        PaymentPlan.objects.create(
            organizacion=self.org,
            nombre="Plan Base",
            num_clases=4,
            precio=20000,
            activo=True,
        )
        plan_destacado = PaymentPlan.objects.create(
            organizacion=self.org,
            nombre="Plan Destacado",
            num_clases=8,
            precio=30000,
            activo=True,
            es_por_defecto=True,
        )

        form = PaymentForm(initial={"organizacion": self.org.pk})

        self.assertEqual(str(form["plan"].value()), str(plan_destacado.pk))

    def test_payment_form_precarga_aplica_iva_segun_configuracion_de_organizacion(self):
        form_afecta = PaymentForm(initial={"organizacion": self.org.pk})
        self.assertTrue(form_afecta.initial["aplica_iva"])

        org_exenta = Organizacion.objects.create(
            nombre="Org Exenta",
            razon_social="Org Exenta SPA",
            rut="66.666.666-6",
            es_exenta_iva=True,
        )
        form_exenta = PaymentForm(initial={"organizacion": org_exenta.pk})
        self.assertFalse(form_exenta.initial["aplica_iva"])

    def test_plan_edit_renderiza_listado_con_edicion_inline(self):
        plan = PaymentPlan.objects.create(
            organizacion=self.org,
            nombre="Plan Editable",
            num_clases=4,
            precio=20000,
            activo=True,
        )
        self.client.force_login(self.user_admin)

        response = self.client.get(
            reverse("finanzas:plan_edit", kwargs={"pk": plan.pk}),
            {"periodo_mes": 3, "periodo_anio": 2026, "organizacion": self.org.pk},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "finanzas/planes_list.html")
        self.assertEqual(response.context["editing_plan_id"], plan.pk)
        self.assertContains(response, "Guardar cambios")
        self.assertContains(response, 'name="es_por_defecto"', html=False)
        self.assertNotContains(response, "Editar plan")

    def test_plan_edit_inline_actualiza_plan_por_defecto(self):
        plan_base = PaymentPlan.objects.create(
            organizacion=self.org,
            nombre="Plan Base",
            num_clases=4,
            precio=20000,
            activo=True,
        )
        plan_otro = PaymentPlan.objects.create(
            organizacion=self.org,
            nombre="Plan Otro",
            num_clases=8,
            precio=30000,
            activo=True,
        )
        self.client.force_login(self.user_admin)

        response = self.client.post(
            f"{reverse('finanzas:plan_edit', kwargs={'pk': plan_otro.pk})}?periodo_mes=3&periodo_anio=2026&organizacion={self.org.pk}",
            {
                "organizacion": self.org.pk,
                "nombre": "Plan Otro",
                "num_clases": 8,
                "precio": 30000,
                "precio_incluye_iva": "",
                "es_por_defecto": "on",
                "fecha_inicio": "",
                "fecha_fin": "",
                "descripcion": "",
                "activo": "on",
            },
        )

        self.assertEqual(response.status_code, 302)
        plan_base.refresh_from_db()
        plan_otro.refresh_from_db()
        self.assertFalse(plan_base.es_por_defecto)
        self.assertTrue(plan_otro.es_por_defecto)


    def test_transaccion_edit_get_precarga_fecha_en_formato_html(self):
        categoria = Category.objects.create(nombre="Ingreso edición", tipo=Category.Tipo.INGRESO)
        transaccion = Transaction.objects.create(
            organizacion=self.org,
            categoria=categoria,
            fecha="2026-02-27",
            tipo=Transaction.Tipo.INGRESO,
            monto=25000,
            descripcion="Movimiento a editar",
        )
        self.client.force_login(self.user_admin)

        response = self.client.get(
            reverse("finanzas:transaccion_edit", kwargs={"pk": transaccion.pk}),
            {"periodo_mes": 2, "periodo_anio": 2026, "organizacion": self.org.pk},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<input type="date" name="fecha"', html=False)
        self.assertContains(response, 'value="2026-02-27"', html=False)



    def test_transacciones_list_precarga_organizacion_del_filtro_en_formulario(self):
        self.client.force_login(self.user_admin)

        response = self.client.get(
            reverse("finanzas:transacciones_list"),
            {"periodo_mes": 2, "periodo_anio": 2026, "organizacion": self.org.pk},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["form"].initial["organizacion"], self.org.pk)
        self.assertContains(response, f'<option value="{self.org.pk}" selected>', html=False)





    def test_transacciones_list_muestra_resumen_del_listado(self):
        categoria_ingreso = Category.objects.create(nombre="Venta", tipo="ingreso", activa=True)
        categoria_egreso = Category.objects.create(nombre="Honorarios", tipo="egreso", activa=True)
        Transaction.objects.create(
            organizacion=self.org,
            categoria=categoria_ingreso,
            fecha="2026-02-05",
            tipo=Transaction.Tipo.INGRESO,
            monto=120000,
            descripcion="Ingreso evento",
        )
        Transaction.objects.create(
            organizacion=self.org,
            categoria=categoria_egreso,
            fecha="2026-02-06",
            tipo=Transaction.Tipo.EGRESO,
            monto=30000,
            descripcion="Pago artista",
        )
        Transaction.objects.create(
            organizacion=self.org,
            categoria=categoria_egreso,
            fecha="2026-03-06",
            tipo=Transaction.Tipo.EGRESO,
            monto=99999,
            descripcion="Fuera de periodo",
        )

        self.client.force_login(self.user_admin)
        response = self.client.get(
            reverse("finanzas:transacciones_list"),
            {"periodo_mes": 2, "periodo_anio": 2026, "organizacion": self.org.pk},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["total_transacciones"], 2)
        self.assertEqual(response.context["total_ingresos"], 120000)
        self.assertEqual(response.context["total_egresos"], 30000)
        self.assertEqual(response.context["balance_transacciones"], 90000)
        self.assertContains(response, "Total transacciones")
        self.assertContains(response, "Balance")














class FinanzasIntegrationTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.org = Organizacion.objects.create(
            nombre="Org Integracion",
            razon_social="Org Integracion SPA",
            rut="33.333.333-3",
        )
        self.rol_admin = Rol.objects.create(nombre="Administrador", codigo="ADMINISTRADOR")
        self.rol_estudiante = Rol.objects.create(nombre="Estudiante", codigo="ESTUDIANTE")

        self.user_admin = User.objects.create_user("admin_int", password=TEST_PASSWORD)
        self.persona_admin = Persona.objects.create(
            nombres="Admin",
            apellidos="Integracion",
            email="adminint@example.com",
            user=self.user_admin,
        )
        PersonaRol.objects.create(
            persona=self.persona_admin,
            rol=self.rol_admin,
            organizacion=self.org,
            activo=True,
        )

        self.estudiante = Persona.objects.create(
            nombres="Ana",
            apellidos="Diaz",
            email="ana.int@example.com",
        )
        PersonaRol.objects.create(
            persona=self.estudiante,
            rol=self.rol_estudiante,
            organizacion=self.org,
            activo=True,
        )
        self.disciplina = Disciplina.objects.create(
            organizacion=self.org,
            nombre="Yoga",
        )
        self.sesion_1 = SesionClase.objects.create(
            disciplina=self.disciplina,
            fecha="2026-02-26",
            estado=SesionClase.Estado.PROGRAMADA,
        )
        self.sesion_2 = SesionClase.objects.create(
            disciplina=self.disciplina,
            fecha="2026-02-27",
            estado=SesionClase.Estado.PROGRAMADA,
        )

    def _crear_pago(self, fecha_pago="2026-02-25", clases_asignadas=1, numero_comprobante="PAGO-1"):
        return Payment.objects.create(
            persona=self.estudiante,
            organizacion=self.org,
            fecha_pago=fecha_pago,
            metodo_pago=Payment.Metodo.TRANSFERENCIA,
            numero_comprobante=numero_comprobante,
            aplica_iva=False,
            monto_referencia=10000,
            clases_asignadas=clases_asignadas,
        )

    def _crear_sesion(self, fecha):
        return SesionClase.objects.create(
            disciplina=self.disciplina,
            fecha=fecha,
            estado=SesionClase.Estado.PROGRAMADA,
        )

    def _crear_asistencia_presente(self, sesion):
        return Asistencia.objects.create(
            sesion=sesion,
            persona=self.estudiante,
            estado=Asistencia.Estado.PRESENTE,
        )

    def test_asistencia_sin_pago_queda_como_deuda(self):
        asistencia = self._crear_asistencia_presente(self.sesion_1)
        consumo = AttendanceConsumption.objects.get(asistencia=asistencia)

        self.assertEqual(consumo.persona, self.estudiante)
        self.assertEqual(consumo.clase_fecha, date(2026, 2, 26))
        self.assertEqual(consumo.estado, AttendanceConsumption.Estado.DEUDA)
        self.assertIsNone(consumo.pago)

    def test_asistencia_con_pago_disponible_queda_consumida(self):
        pago = self._crear_pago(clases_asignadas=1)

        asistencia = self._crear_asistencia_presente(self.sesion_2)
        consumo = AttendanceConsumption.objects.get(asistencia=asistencia)

        self.assertEqual(consumo.estado, AttendanceConsumption.Estado.CONSUMIDO)
        self.assertEqual(consumo.pago, pago)
        self.assertEqual(pago.clases_consumidas, 1)
        self.assertEqual(pago.saldo_clases, 0)

    def test_asistencia_no_consume_pago_de_otro_mes(self):
        pago_enero = self._crear_pago(fecha_pago="2026-01-25", numero_comprobante="ENE-1")

        asistencia = self._crear_asistencia_presente(self.sesion_2)
        consumo = AttendanceConsumption.objects.get(asistencia=asistencia)

        self.assertEqual(consumo.estado, AttendanceConsumption.Estado.DEUDA)
        self.assertIsNone(consumo.pago)
        self.assertEqual(pago_enero.saldo_clases, 1)

    def test_pago_nuevo_imputa_deudas_previas(self):
        asistencia_febrero = self._crear_asistencia_presente(self.sesion_1)
        asistencia_marzo = self._crear_asistencia_presente(self._crear_sesion("2026-03-01"))
        consumo_febrero = AttendanceConsumption.objects.get(asistencia=asistencia_febrero)
        consumo_marzo = AttendanceConsumption.objects.get(asistencia=asistencia_marzo)
        self.assertEqual(consumo_febrero.estado, AttendanceConsumption.Estado.DEUDA)
        self.assertEqual(consumo_marzo.estado, AttendanceConsumption.Estado.DEUDA)

        pago = self._crear_pago(fecha_pago="2026-02-28", clases_asignadas=2, numero_comprobante="FEB-1")

        consumo_febrero.refresh_from_db()
        consumo_marzo.refresh_from_db()
        self.assertEqual(consumo_febrero.estado, AttendanceConsumption.Estado.CONSUMIDO)
        self.assertEqual(consumo_febrero.pago, pago)
        self.assertEqual(consumo_marzo.estado, AttendanceConsumption.Estado.DEUDA)
        self.assertIsNone(consumo_marzo.pago)
        self.assertEqual(pago.clases_consumidas, 1)
        self.assertEqual(pago.saldo_clases, 1)

    def test_pago_no_imputa_deuda_de_otro_mes(self):
        asistencia = self._crear_asistencia_presente(self.sesion_1)
        consumo = AttendanceConsumption.objects.get(asistencia=asistencia)
        self.assertEqual(consumo.estado, AttendanceConsumption.Estado.DEUDA)

        pago_marzo = self._crear_pago(fecha_pago="2026-03-05", numero_comprobante="MAR-1")

        consumo.refresh_from_db()
        self.assertEqual(consumo.estado, AttendanceConsumption.Estado.DEUDA)
        self.assertIsNone(consumo.pago)
        self.assertEqual(pago_marzo.saldo_clases, 1)

    def test_asociar_asistencia_a_pago_rechaza_pago_de_otro_mes(self):
        pago_otro_mes = self._crear_pago(fecha_pago="2026-03-05", numero_comprobante="MAR-2")
        asistencia = self._crear_asistencia_presente(self.sesion_1)

        with self.assertRaisesMessage(
            ValueError,
            "Solo se pueden asociar pagos del mismo mes y anio de la asistencia.",
        ):
            asociar_asistencia_a_pago(asistencia, pago_otro_mes)

    def test_resumen_financiero_estudiante_refleja_pagadas_consumidas_deuda_y_saldo(self):
        pago = self._crear_pago(fecha_pago="2026-02-25", clases_asignadas=3)
        asistencia_consumida = self._crear_asistencia_presente(self.sesion_1)
        asistencia_deuda = self._crear_asistencia_presente(self.sesion_2)
        consumo_consumido = AttendanceConsumption.objects.get(asistencia=asistencia_consumida)
        consumo_deuda = AttendanceConsumption.objects.get(asistencia=asistencia_deuda)

        consumo_consumido.pago = pago
        consumo_consumido.estado = AttendanceConsumption.Estado.CONSUMIDO
        consumo_consumido.save(update_fields=["pago", "estado"])
        consumo_deuda.pago = None
        consumo_deuda.estado = AttendanceConsumption.Estado.DEUDA
        consumo_deuda.save(update_fields=["pago", "estado"])

        resumen = resumen_financiero_estudiante(self.estudiante, organizacion=self.org)

        self.assertEqual(resumen["clases_pagadas"], 3)
        self.assertEqual(resumen["clases_consumidas"], 1)
        self.assertEqual(resumen["deuda_pendiente"], 1)
        self.assertEqual(resumen["saldo_clases"], 2)
        self.assertEqual(resumen["fecha_ultimo_pago"], date(2026, 2, 25))

    def test_pago_con_plan_respeta_monto_referencia_editable(self):
        plan = PaymentPlan.objects.create(
            organizacion=self.org,
            nombre="Plan Base",
            num_clases=4,
            precio=20000,
            activo=True,
        )
        pago = Payment.objects.create(
            persona=self.estudiante,
            organizacion=self.org,
            plan=plan,
            fecha_pago="2026-02-28",
            metodo_pago=Payment.Metodo.TRANSFERENCIA,
            aplica_iva=False,
            monto_referencia=15000,
        )
        self.assertEqual(pago.monto_total, 15000)

    def test_form_transferencia_exige_numero_comprobante(self):
        data_base = {
            "organizacion": self.org.pk,
            "persona": self.estudiante.pk,
            "fecha_pago": "2026-02-28",
            "metodo_pago": "transferencia",
            "monto_referencia": "10000",
            "clases_asignadas": "1",
        }
        form = PaymentForm(data=data_base)
        self.assertFalse(form.is_valid())
        self.assertIn("numero_comprobante", form.errors)

        data_efectivo = {
            **data_base,
            "metodo_pago": "efectivo",
            "numero_comprobante": "",
        }
        form_efectivo = PaymentForm(data=data_efectivo)
        self.assertTrue(form_efectivo.is_valid(), form_efectivo.errors)

    def test_form_rechaza_plan_de_otra_organizacion(self):
        otra_org = Organizacion.objects.create(
            nombre="Org Externa",
            razon_social="Org Externa SPA",
            rut="44.444.444-4",
        )
        plan_otro = PaymentPlan.objects.create(
            organizacion=otra_org,
            nombre="Plan Otro",
            num_clases=4,
            precio=22000,
            activo=True,
        )
        form = PaymentForm(
            data={
                "organizacion": self.org.pk,
                "persona": self.estudiante.pk,
                "plan": plan_otro.pk,
                "fecha_pago": "2026-02-28",
                "metodo_pago": "efectivo",
                "monto_referencia": "10000",
                "clases_asignadas": "1",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("plan", form.errors)













    def test_form_edicion_pago_renderiza_fecha_iso_para_input_date(self):
        pago = Payment.objects.create(
            persona=self.estudiante,
            organizacion=self.org,
            fecha_pago="2026-02-28",
            metodo_pago=Payment.Metodo.EFECTIVO,
            aplica_iva=False,
            monto_referencia=10000,
            clases_asignadas=1,
        )
        form = PaymentForm(instance=pago)
        html = form["fecha_pago"].as_widget()
        self.assertIn('value="2026-02-28"', html)





    def test_pagos_list_muestra_resumen_compilado_del_listado(self):
        self.client.force_login(self.user_admin)

        pago_1 = Payment.objects.create(
            persona=self.estudiante,
            organizacion=self.org,
            fecha_pago="2026-02-25",
            metodo_pago=Payment.Metodo.EFECTIVO,
            aplica_iva=False,
            monto_referencia=10000,
            clases_asignadas=2,
        )
        Payment.objects.create(
            persona=self.estudiante,
            organizacion=self.org,
            fecha_pago="2026-02-28",
            metodo_pago=Payment.Metodo.TRANSFERENCIA,
            numero_comprobante="ABC123",
            aplica_iva=False,
            monto_referencia=15000,
            clases_asignadas=3,
        )
        Payment.objects.create(
            persona=self.estudiante,
            organizacion=self.org,
            fecha_pago="2026-03-02",
            metodo_pago=Payment.Metodo.EFECTIVO,
            aplica_iva=False,
            monto_referencia=5000,
            clases_asignadas=1,
        )

        asistencia = Asistencia.objects.create(sesion=self.sesion_1, persona=self.estudiante)
        consumo = AttendanceConsumption.objects.get(asistencia=asistencia)
        self.assertEqual(consumo.pago, pago_1)

        response = self.client.get(
            reverse("finanzas:pagos_list"),
            {"periodo_mes": 2, "periodo_anio": 2026, "organizacion": self.org.pk},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["total_pagos_monto"], 25000)
        self.assertEqual(response.context["total_clases_pagadas"], 5)
        self.assertEqual(response.context["total_saldo_clases"], 4)

    def test_pagos_list_muestra_estado_fiscal_y_texto_copiable(self):
        self.client.force_login(self.user_admin)
        plan = PaymentPlan.objects.create(
            organizacion=self.org,
            nombre="Plan Mensual",
            num_clases=4,
            precio=10000,
            activo=True,
        )
        Payment.objects.create(
            persona=self.estudiante,
            organizacion=self.org,
            plan=plan,
            fecha_pago="2026-02-25",
            metodo_pago=Payment.Metodo.EFECTIVO,
            aplica_iva=True,
            monto_incluye_iva=False,
            monto_referencia=10000,
            clases_asignadas=4,
        )
        Payment.objects.create(
            persona=self.estudiante,
            organizacion=self.org,
            fecha_pago="2026-02-26",
            metodo_pago=Payment.Metodo.EFECTIVO,
            aplica_iva=False,
            monto_referencia=8000,
            clases_asignadas=1,
        )
        disciplina_secundaria = Disciplina.objects.create(
            organizacion=self.org,
            nombre="Pilates",
        )
        sesion_pilates = SesionClase.objects.create(
            disciplina=disciplina_secundaria,
            fecha="2026-02-24",
            estado=SesionClase.Estado.PROGRAMADA,
        )
        Asistencia.objects.create(sesion=self.sesion_1, persona=self.estudiante)
        Asistencia.objects.create(sesion=self.sesion_2, persona=self.estudiante)
        Asistencia.objects.create(sesion=sesion_pilates, persona=self.estudiante)
        Asistencia.objects.filter(sesion=sesion_pilates, persona=self.estudiante).update(
            estado=Asistencia.Estado.AUSENTE
        )

        response = self.client.get(
            reverse("finanzas:pagos_list"),
            {"periodo_mes": 2, "periodo_anio": 2026, "organizacion": self.org.pk},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Haz clic sobre los montos de neto, IVA o bruto para copiar el valor sin puntos.")
        self.assertContains(response, "<th>IVA</th>", html=False)
        self.assertNotContains(response, "<th>Organizacion</th>", html=False)
        self.assertContains(response, "Afecta")
        self.assertContains(response, "Exenta")
        self.assertContains(response, "11.900")
        self.assertContains(response, "10.000")
        self.assertContains(response, "1.900")
        self.assertContains(response, "8.000")
        self.assertContains(response, "bi-chat-text", html=False)
        self.assertContains(response, 'data-copy-value="10000"', html=False)
        self.assertContains(response, 'data-copy-value="1900"', html=False)
        self.assertContains(response, 'data-copy-value="11900"', html=False)
        self.assertContains(response, 'title="$ 11.900 · clic para copiar 11900"', html=False)
        self.assertContains(
            response,
            'data-copy-text="Taller de Yoga - Plan Mensual (Ana Diaz)"',
            html=False,
        )
        self.assertContains(
            response,
            'title="Taller de Yoga - Plan Mensual (Ana Diaz) · clic para copiar"',
            html=False,
        )

        pago = next(item for item in response.context["pagos"] if item.plan_id)
        self.assertEqual(pago.disciplina_principal_nombre, "Yoga")
        self.assertEqual(pago.texto_copia, "Taller de Yoga - Plan Mensual (Ana Diaz)")

    def test_servicio_pagos_enriquece_filas_para_listado(self):
        plan = PaymentPlan.objects.create(
            organizacion=self.org,
            nombre="Plan Mensual",
            num_clases=4,
            precio=10000,
            activo=True,
        )
        pago = Payment.objects.create(
            persona=self.estudiante,
            organizacion=self.org,
            plan=plan,
            fecha_pago="2026-02-25",
            metodo_pago=Payment.Metodo.EFECTIVO,
            aplica_iva=True,
            monto_referencia=10000,
            clases_asignadas=4,
        )
        pago.disciplina_principal_nombre = "Yoga"

        pagos = enriquecer_pagos_para_listado([pago])

        self.assertEqual(pagos[0].estado_fiscal_label, "Afecta")
        self.assertEqual(pagos[0].estado_fiscal_badge_class, "text-bg-primary")
        self.assertEqual(pagos[0].texto_copia, "Taller de Yoga - Plan Mensual (Ana Diaz)")
        self.assertEqual(pagos[0].monto_neto_copia, "10000")
        self.assertEqual(pagos[0].monto_iva_copia, "1900")
        self.assertEqual(pagos[0].monto_total_copia, "11900")

    def test_servicio_pagos_crea_persona_estudiante_desde_modal(self):
        form = PersonaRapidaForm(
            data={
                "nombres": "Lucia",
                "apellidos": "Perez",
                "telefono": "999999",
            }
        )
        self.assertTrue(form.is_valid(), form.errors)

        persona = crear_persona_estudiante_desde_modal(form=form, organizacion=self.org)

        self.assertEqual(persona.nombres, "Lucia")
        self.assertEqual(persona.apellidos, "Perez")
        self.assertTrue(
            PersonaRol.objects.filter(
                persona=persona,
                rol=self.rol_estudiante,
                organizacion=self.org,
                activo=True,
            ).exists()
        )

    def test_servicio_pagos_resume_consumos_y_saldo(self):
        pago = self._crear_pago(fecha_pago="2026-02-25", clases_asignadas=3)
        asistencia_consumida = self._crear_asistencia_presente(self.sesion_1)
        asistencia_deuda = self._crear_asistencia_presente(self.sesion_2)
        consumo_consumido = AttendanceConsumption.objects.get(asistencia=asistencia_consumida)
        consumo_deuda = AttendanceConsumption.objects.get(asistencia=asistencia_deuda)

        consumo_consumido.pago = pago
        consumo_consumido.estado = AttendanceConsumption.Estado.CONSUMIDO
        consumo_consumido.save(update_fields=["pago", "estado"])
        consumo_deuda.pago = pago
        consumo_deuda.estado = AttendanceConsumption.Estado.DEUDA
        consumo_deuda.save(update_fields=["pago", "estado"])

        resumen = resumen_consumos_pago(pago)

        self.assertEqual(resumen["consumos"], [consumo_deuda, consumo_consumido])
        self.assertEqual(resumen["consumos_consumidos"], 1)
        self.assertEqual(resumen["consumos_pendientes"], 0)
        self.assertEqual(resumen["consumos_deuda"], 1)
        self.assertEqual(resumen["saldo_clases"], 2)

    def test_servicio_pagos_texto_copiable_usa_fallbacks_operativos(self):
        pago = self._crear_pago(fecha_pago="2026-02-25", clases_asignadas=1)
        pago.disciplina_principal_nombre = ""

        self.assertEqual(
            texto_copiable_operativo_pago(pago),
            "Taller de Sin disciplina - Sin plan (Ana Diaz)",
        )


class SprintDosReversaPagosTests(TestCase):
    def setUp(self):
        self.organizacion = Organizacion.objects.create(
            nombre="Org Reversa Sprint 2",
            razon_social="Org Reversa Sprint 2 SpA",
            rut="71.000.000-1",
        )
        self.otra_organizacion = Organizacion.objects.create(
            nombre="Otra Reversa Sprint 2",
            razon_social="Otra Reversa Sprint 2 SpA",
            rut="71.000.000-2",
        )
        self.rol_admin = Rol.objects.create(nombre="Admin Reversa", codigo="ADMIN")
        self.rol_finanzas = Rol.objects.create(nombre="Finanzas Reversa", codigo="FINANZAS")
        self.rol_profesor = Rol.objects.create(nombre="Profesor Reversa", codigo="PROFESOR")
        self.rol_estudiante = Rol.objects.create(nombre="Estudiante Reversa", codigo="ESTUDIANTE")
        self.admin = self._crear_usuario_rol("admin_reversa", self.rol_admin, self.organizacion)
        self.finanzas = self._crear_usuario_rol("finanzas_reversa", self.rol_finanzas, self.organizacion)
        self.profesor = self._crear_usuario_rol("profesor_reversa", self.rol_profesor, self.organizacion)
        self.admin_otra = self._crear_usuario_rol("admin_reversa_otra", self.rol_admin, self.otra_organizacion)
        self.estudiante = Persona.objects.create(nombres="Alumno", apellidos="Reversa")
        PersonaRol.objects.create(
            persona=self.estudiante,
            rol=self.rol_estudiante,
            organizacion=self.organizacion,
            activo=True,
        )
        self.disciplina = Disciplina.objects.create(
            organizacion=self.organizacion,
            nombre="Disciplina Reversa",
        )
        self.sesion = SesionClase.objects.create(
            disciplina=self.disciplina,
            fecha=date(2026, 7, 15),
        )

    def _crear_usuario_rol(self, username, rol, organizacion):
        return crear_usuario_con_rol(
            username=username,
            password=TEST_PASSWORD,
            rol=rol,
            organizacion=organizacion,
            apellidos="Sprint",
        )

    def _crear_pago(self, *, clases=1):
        return Payment.objects.create(
            persona=self.estudiante,
            organizacion=self.organizacion,
            fecha_pago=date(2026, 7, 2),
            metodo_pago=Payment.Metodo.EFECTIVO,
            aplica_iva=False,
            monto_referencia=20000,
            clases_asignadas=clases,
        )

    def test_revertir_pago_preserva_historia_traza_y_recalcula_consumo(self):
        pago = self._crear_pago()
        asistencia = Asistencia.objects.create(sesion=self.sesion, persona=self.estudiante)
        consumo = AttendanceConsumption.objects.get(asistencia=asistencia)
        self.assertEqual(consumo.estado, AttendanceConsumption.Estado.CONSUMIDO)

        with self.captureOnCommitCallbacks(execute=True):
            revertido = revertir_pago(
                pago=pago,
                motivo="Transferencia anulada por banco",
                usuario=self.admin,
            )

        self.assertEqual(revertido.pk, pago.pk)
        self.assertIsNotNone(revertido.revertido_en)
        self.assertEqual(revertido.revertido_por, self.admin)
        self.assertEqual(revertido.motivo_reversa, "Transferencia anulada por banco")
        consumo.refresh_from_db()
        self.assertEqual(consumo.estado, AttendanceConsumption.Estado.DEUDA)
        self.assertIsNone(consumo.pago)
        self.assertTrue(Payment.objects.filter(pk=pago.pk).exists())
        self.assertTrue(AuditLog.objects.filter(objeto_id=str(pago.pk), resumen="Pago revertido").exists())

    def test_revertir_pago_reasigna_consumo_a_otro_derecho_valido(self):
        primero = self._crear_pago()
        segundo = self._crear_pago()
        asistencia = Asistencia.objects.create(sesion=self.sesion, persona=self.estudiante)
        consumo = AttendanceConsumption.objects.get(asistencia=asistencia)
        self.assertEqual(consumo.pago, primero)

        revertir_pago(pago=primero, motivo="Pago duplicado", usuario=self.admin)

        consumo.refresh_from_db()
        self.assertEqual(consumo.estado, AttendanceConsumption.Estado.CONSUMIDO)
        self.assertEqual(consumo.pago, segundo)

    def test_revertir_pago_exige_motivo_e_impide_segunda_reversa(self):
        pago = self._crear_pago()
        with self.assertRaisesMessage(ValidationError, "motivo"):
            revertir_pago(pago=pago, motivo="", usuario=self.admin)
        revertir_pago(pago=pago, motivo="Primera reversa", usuario=self.admin)
        with self.assertRaisesMessage(ValidationError, "ya fue revertido"):
            revertir_pago(pago=pago, motivo="Segunda reversa", usuario=self.admin)

    def test_reversa_pago_restringida_a_admin_de_la_organizacion(self):
        pago = self._crear_pago()
        url = (
            reverse("finanzas:pago_revertir", kwargs={"pk": pago.pk})
            + f"?organizacion={self.organizacion.pk}"
        )
        for usuario, esperado in (
            (self.admin, 302),
            (self.finanzas, 403),
            (self.profesor, 403),
            (self.admin_otra, 403),
        ):
            with self.subTest(usuario=usuario.username):
                if pago.revertido_en:
                    pago = self._crear_pago()
                    url = (
                        reverse("finanzas:pago_revertir", kwargs={"pk": pago.pk})
                        + f"?organizacion={self.organizacion.pk}"
                    )
                self.client.force_login(usuario)
                response = self.client.post(url, {"motivo": "Motivo de prueba"})
                self.assertEqual(response.status_code, esperado)
                pago.refresh_from_db()

    def test_accion_reversa_solo_es_visible_para_admin_autorizado(self):
        pago = self._crear_pago()
        url = reverse("finanzas:pagos_list")
        params = {
            "periodo_mes": 7,
            "periodo_anio": 2026,
            "organizacion": self.organizacion.pk,
        }
        self.client.force_login(self.admin)
        response_admin = self.client.get(url, params)
        self.assertContains(
            response_admin,
            reverse("finanzas:pago_revertir", kwargs={"pk": pago.pk}),
        )

        for usuario in (self.finanzas, self.profesor, self.admin_otra):
            with self.subTest(usuario=usuario.username):
                self.client.force_login(usuario)
                response = self.client.get(url, params)
                if usuario == self.finanzas:
                    self.assertEqual(response.status_code, 200)
                    self.assertNotContains(
                        response,
                        reverse("finanzas:pago_revertir", kwargs={"pk": pago.pk}),
                    )
                else:
                    self.assertEqual(response.status_code, 403)

    def test_listado_muestra_revertido_y_excluye_pago_de_resumen(self):
        vigente = self._crear_pago(clases=2)
        revertido = self._crear_pago(clases=3)
        revertir_pago(pago=revertido, motivo="No vigente", usuario=self.admin)
        self.client.force_login(self.admin)
        response = self.client.get(
            reverse("finanzas:pagos_list"),
            {
                "periodo_mes": 7,
                "periodo_anio": 2026,
                "organizacion": self.organizacion.pk,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Revertido")
        self.assertEqual(response.context["total_clases_pagadas"], vigente.clases_asignadas)
        self.assertEqual(response.context["total_pagos_monto"], vigente.monto_total)


class SprintDosReconciliacionTests(TestCase):
    def setUp(self):
        self.organizacion = Organizacion.objects.create(
            nombre="Org Reconciliación",
            razon_social="Org Reconciliación SpA",
            rut="71.000.000-3",
        )
        self.otra_organizacion = Organizacion.objects.create(
            nombre="Otra Reconciliación",
            razon_social="Otra Reconciliación SpA",
            rut="71.000.000-4",
        )
        self.estudiante = Persona.objects.create(nombres="Alumno", apellidos="Reconciliación")
        self.disciplina = Disciplina.objects.create(
            organizacion=self.organizacion,
            nombre="Reconciliación",
        )
        self.sesion = SesionClase.objects.create(
            disciplina=self.disciplina,
            fecha=date(2026, 7, 20),
        )

    def _pago(self, organizacion=None, *, clases=1, fecha_pago=None):
        return Payment.objects.create(
            persona=self.estudiante,
            organizacion=organizacion or self.organizacion,
            fecha_pago=fecha_pago or date(2026, 7, 1),
            metodo_pago=Payment.Metodo.EFECTIVO,
            aplica_iva=False,
            monto_referencia=10000,
            clases_asignadas=clases,
        )

    def _otra_asistencia(self, *, dia=21):
        sesion = SesionClase.objects.create(
            disciplina=self.disciplina,
            fecha=date(2026, 7, dia),
        )
        return Asistencia.objects.create(sesion=sesion, persona=self.estudiante)

    def test_reconciliacion_permite_consumos_compartidos_con_cupo_suficiente(self):
        pago = self._pago(clases=2)
        primera = Asistencia.objects.create(
            sesion=self.sesion,
            persona=self.estudiante,
        )
        segunda = self._otra_asistencia()
        resultado = reconciliar_integridad_dominio()

        self.assertTrue(resultado["ok"])
        self.assertFalse(any(resultado["resumen"].values()))
        self.assertEqual(
            AttendanceConsumption.objects.filter(
                asistencia__in=[primera, segunda],
                pago=pago,
                estado=AttendanceConsumption.Estado.CONSUMIDO,
            ).count(),
            2,
        )

        salida = StringIO()
        call_command("reconciliar_integridad_dominio", stdout=salida)
        self.assertIn("Sin inconsistencias de dominio", salida.getvalue())

    def test_reconciliacion_detecta_sobreconsumo_respecto_de_clases_asignadas(self):
        pago = self._pago(clases=1)
        primera = Asistencia.objects.create(
            sesion=self.sesion,
            persona=self.estudiante,
        )
        segunda = self._otra_asistencia()
        AttendanceConsumption.objects.filter(asistencia=segunda).update(
            estado=AttendanceConsumption.Estado.CONSUMIDO,
            pago=pago,
        )

        resultado = reconciliar_integridad_dominio()

        self.assertEqual(resultado["resumen"]["sobreconsumo_pago"], 1)
        self.assertEqual(
            resultado["detalle"]["sobreconsumo_pago"],
            [
                {
                    "pago_id": pago.pk,
                    "organizacion_id": self.organizacion.pk,
                    "clases_asignadas": 1,
                    "consumos_consumidos": 2,
                }
            ],
        )
        self.assertEqual(
            AttendanceConsumption.objects.filter(
                asistencia__in=[primera, segunda],
                pago=pago,
            ).count(),
            2,
        )

    def test_reconciliacion_detecta_consumo_fuera_periodo_y_sin_pago(self):
        pago_anterior = self._pago(fecha_pago=date(2026, 6, 1))
        fuera_periodo = Asistencia.objects.create(
            sesion=self.sesion,
            persona=self.estudiante,
        )
        huerfano = self._otra_asistencia()
        AttendanceConsumption.objects.filter(asistencia=fuera_periodo).update(
            estado=AttendanceConsumption.Estado.CONSUMIDO,
            pago=pago_anterior,
        )
        AttendanceConsumption.objects.filter(asistencia=huerfano).update(
            estado=AttendanceConsumption.Estado.CONSUMIDO,
            pago=None,
        )

        resultado = reconciliar_integridad_dominio()

        self.assertEqual(resultado["resumen"]["consumo_fuera_periodo"], 1)
        self.assertEqual(resultado["resumen"]["consumo_sin_pago"], 1)

    def test_reconciliacion_detecta_consumo_de_otra_persona_u_organizacion(self):
        pago_ajeno = self._pago(organizacion=self.otra_organizacion)
        asistencia = Asistencia.objects.create(
            sesion=self.sesion,
            persona=self.estudiante,
            estado=Asistencia.Estado.AUSENTE,
        )
        AttendanceConsumption.objects.filter(asistencia=asistencia).update(
            estado=AttendanceConsumption.Estado.CONSUMIDO,
            pago=pago_ajeno,
        )
        resultado = reconciliar_integridad_dominio()
        self.assertFalse(resultado["ok"])
        self.assertEqual(
            resultado["resumen"]["consumo_otra_persona_organizacion"],
            1,
        )

        with self.assertRaises(CommandError):
            call_command("reconciliar_integridad_dominio", stdout=StringIO())

    def test_reconciliacion_detecta_liberada_consumiendo_y_pago_revertido(self):
        user = get_user_model().objects.create_user("audit_reconciliacion", password=TEST_PASSWORD)
        pago = self._pago()
        asistencia = Asistencia.objects.create(sesion=self.sesion, persona=self.estudiante)
        ClaseLiberada.objects.create(
            asistencia=asistencia,
            organizacion=self.organizacion,
            motivo="Inconsistencia inducida",
            liberada_por=user,
        )
        Payment.objects.filter(pk=pago.pk).update(
            revertido_en=timezone.now(),
            revertido_por=user,
            motivo_reversa="Inconsistencia inducida",
        )
        resultado = reconciliar_integridad_dominio()
        self.assertEqual(resultado["resumen"]["clase_liberada_consumiendo"], 1)
        self.assertEqual(resultado["resumen"]["pago_revertido_incluido"], 1)

    def test_reconciliacion_detecta_estado_ordinario_pendiente(self):
        asistencia = Asistencia.objects.create(
            sesion=self.sesion,
            persona=self.estudiante,
            estado=Asistencia.Estado.JUSTIFICADA,
        )
        AttendanceConsumption.objects.filter(asistencia=asistencia).update(
            estado=AttendanceConsumption.Estado.PENDIENTE,
            pago=None,
        )

        resultado = reconciliar_integridad_dominio()

        self.assertEqual(resultado["resumen"]["estado_asistencia_incompatible"], 1)


class PagoMasivoDominioTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.org = Organizacion.objects.create(nombre="Org Lotes", razon_social="Org Lotes SPA", rut="76.000.000-1")
        self.otra_org = Organizacion.objects.create(nombre="Otra Org Lotes", razon_social="Otra Org Lotes SPA", rut="76.000.000-2")
        self.rol_admin = Rol.objects.create(nombre="Admin lotes", codigo="ADMIN")
        self.rol_estudiante = Rol.objects.create(nombre="Estudiante lotes", codigo="ESTUDIANTE")
        self.user = User.objects.create_user("admin_lotes", password=TEST_PASSWORD)
        self.admin = Persona.objects.create(nombres="Admin", apellidos="Lotes", user=self.user)
        PersonaRol.objects.create(persona=self.admin, rol=self.rol_admin, organizacion=self.org, activo=True)
        self.plan = PaymentPlan.objects.create(
            organizacion=self.org,
            nombre="Plan lote",
            num_clases=2,
            precio=10000,
            activo=True,
        )
        self.personas = []
        for index in range(20):
            persona = Persona.objects.create(nombres=f"Alumno{index}", apellidos="Lote")
            PersonaRol.objects.create(persona=persona, rol=self.rol_estudiante, organizacion=self.org, activo=True)
            self.personas.append(persona)

    def _filas(self, cantidad):
        return [
            {
                "persona_id": persona.pk,
                "plan_id": self.plan.pk,
                "fecha_pago": date(2026, 7, 27),
                "metodo_pago": Payment.Metodo.EFECTIVO,
                "numero_comprobante": "",
                "aplica_iva": False,
                "monto_incluye_iva": False,
                "monto_referencia": Decimal("10000"),
                "clases_asignadas": 0,
                "observaciones": "lote de prueba",
            }
            for persona in self.personas[:cantidad]
        ]

    def test_lote_valido_de_10_crea_pagos_y_auditoria_de_lote(self):
        with self.captureOnCommitCallbacks(execute=True):
            lote, creado = confirmar_lote_pagos(
                usuario=self.user,
                organizacion_id=self.org.pk,
                clave_idempotencia="lote-10",
                filas=self._filas(10),
            )
        self.assertTrue(creado)
        self.assertEqual(lote.cantidad_pagos, 10)
        self.assertEqual(Payment.objects.filter(lote=lote).count(), 10)
        self.assertEqual(AuditLog.objects.filter(objeto_id=str(lote.pk)).count(), 1)

    def test_lote_valido_de_20_conserva_mismos_montos_del_pago_individual(self):
        lote, creado = confirmar_lote_pagos(
            usuario=self.user,
            organizacion_id=self.org.pk,
            clave_idempotencia="lote-20",
            filas=self._filas(20),
        )
        self.assertTrue(creado)
        pagos = list(Payment.objects.filter(lote=lote))
        self.assertEqual(len(pagos), 20)
        self.assertTrue(all(pago.monto_total == Decimal("10000.00") for pago in pagos))
        self.assertTrue(all(pago.clases_asignadas == 2 for pago in pagos))

    def test_fila_invalida_hace_rollback_de_todo_el_lote(self):
        filas = self._filas(10)
        filas[-1]["persona_id"] = self.personas[0].pk
        with self.assertRaises(ValidationError):
            confirmar_lote_pagos(
                usuario=self.user,
                organizacion_id=self.org.pk,
                clave_idempotencia="lote-invalido",
                filas=filas,
            )
        self.assertEqual(Payment.objects.count(), 0)
        self.assertEqual(LotePago.objects.count(), 0)

    def test_misma_clave_idempotente_no_duplica_pagos(self):
        lote, creado = confirmar_lote_pagos(
            usuario=self.user,
            organizacion_id=self.org.pk,
            clave_idempotencia="lote-reintento",
            filas=self._filas(10),
        )
        repetido, creado_repetido = confirmar_lote_pagos(
            usuario=self.user,
            organizacion_id=self.org.pk,
            clave_idempotencia="lote-reintento",
            filas=self._filas(10),
        )
        self.assertTrue(creado)
        self.assertFalse(creado_repetido)
        self.assertEqual(repetido.pk, lote.pk)
        self.assertEqual(Payment.objects.count(), 10)

    def test_persona_de_otra_organizacion_no_puede_formar_parte_del_lote(self):
        persona_ajena = Persona.objects.create(nombres="Ajena", apellidos="Lote")
        PersonaRol.objects.create(persona=persona_ajena, rol=self.rol_estudiante, organizacion=self.otra_org, activo=True)
        filas = self._filas(1)
        filas[0]["persona_id"] = persona_ajena.pk
        with self.assertRaisesMessage(ValidationError, "persona seleccionada"):
            confirmar_lote_pagos(
                usuario=self.user,
                organizacion_id=self.org.pk,
                clave_idempotencia="lote-ajeno",
                filas=filas,
            )
        self.assertEqual(Payment.objects.count(), 0)

    def test_vista_masiva_y_busqueda_estan_limitadas_por_organizacion(self):
        self.client.force_login(self.user)
        url = reverse("finanzas:pago_masivo")
        response = self.client.get(f"{url}?organizacion={self.org.pk}")
        self.assertEqual(response.status_code, 200)
        busqueda = self.client.get(
            reverse("finanzas:pago_masivo_personas"),
            {"organizacion": self.org.pk, "q": "Alumno"},
        )
        self.assertEqual(busqueda.status_code, 200)
        self.assertEqual(len(busqueda.json()["resultados"]), 20)
        persona_con_tildes = Persona.objects.create(
            nombres="Matías Andrés",
            apellidos="Pérez Muñoz",
            email="matias.perez@example.com",
        )
        PersonaRol.objects.create(
            persona=persona_con_tildes,
            rol=self.rol_estudiante,
            organizacion=self.org,
            activo=True,
        )
        busqueda_nombre_completo = self.client.get(
            reverse("finanzas:pago_masivo_personas"),
            {"organizacion": self.org.pk, "q": "matias perez"},
        )
        self.assertEqual(busqueda_nombre_completo.status_code, 200)
        self.assertEqual(
            [item["id"] for item in busqueda_nombre_completo.json()["resultados"]],
            [persona_con_tildes.pk],
        )
        ajena = self.client.get(
            reverse("finanzas:pago_masivo_personas"),
            {"organizacion": self.otra_org.pk, "q": "Alumno"},
        )
        self.assertEqual(ajena.status_code, 404)

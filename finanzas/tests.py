from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from finanzas.forms import PaymentForm

from database.models import (
    Asistencia,
    AttendanceConsumption,
    Disciplina,
    Organizacion,
    Payment,
    PaymentPlan,
    Persona,
    PersonaRol,
    Rol,
    SesionClase,
)


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

        self.user_admin = User.objects.create_user("admin_fin", password="secret123")
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

        self.user_no_admin = User.objects.create_user("noadmin_fin", password="secret123")
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

    def test_finanzas_dashboard_requiere_admin(self):
        self.client.force_login(self.user_no_admin)
        response = self.client.get(reverse("finanzas:dashboard"))
        self.assertEqual(response.status_code, 403)

    def test_finanzas_dashboard_admin_ok(self):
        self.client.force_login(self.user_admin)
        response = self.client.get(reverse("finanzas:dashboard"))
        self.assertEqual(response.status_code, 200)

    def test_pago_edit_back_url_conserva_querystring(self):
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
        query = "periodo_mes=2&periodo_anio=2026&organizacion=1&q=ana&metodo=transferencia"
        response = self.client.get(f"{reverse('finanzas:pago_edit', kwargs={'pk': pago.pk})}?{query}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["back_url"], f"{reverse('finanzas:pagos_list')}?{query}")


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

        self.user_admin = User.objects.create_user("admin_int", password="secret123")
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

    def test_asistencia_sin_pago_queda_como_deuda(self):
        asistencia = Asistencia.objects.create(sesion=self.sesion_1, persona=self.estudiante)
        consumo = AttendanceConsumption.objects.get(asistencia=asistencia)
        self.assertEqual(consumo.estado, AttendanceConsumption.Estado.DEUDA)
        self.assertIsNone(consumo.pago)

    def test_asistencia_con_pago_disponible_queda_consumida(self):
        Payment.objects.create(
            persona=self.estudiante,
            organizacion=self.org,
            fecha_pago="2026-02-25",
            metodo_pago=Payment.Metodo.TRANSFERENCIA,
            aplica_iva=False,
            monto_referencia=10000,
            clases_asignadas=1,
        )
        asistencia = Asistencia.objects.create(sesion=self.sesion_2, persona=self.estudiante)
        consumo = AttendanceConsumption.objects.get(asistencia=asistencia)
        self.assertEqual(consumo.estado, AttendanceConsumption.Estado.CONSUMIDO)
        self.assertIsNotNone(consumo.pago)

    def test_pago_nuevo_imputa_deudas_previas(self):
        asistencia = Asistencia.objects.create(sesion=self.sesion_1, persona=self.estudiante)
        consumo = AttendanceConsumption.objects.get(asistencia=asistencia)
        self.assertEqual(consumo.estado, AttendanceConsumption.Estado.DEUDA)
        self.assertIsNone(consumo.pago)

        pago = Payment.objects.create(
            persona=self.estudiante,
            organizacion=self.org,
            fecha_pago="2026-02-28",
            metodo_pago=Payment.Metodo.TRANSFERENCIA,
            aplica_iva=False,
            monto_referencia=10000,
            clases_asignadas=1,
        )

        consumo.refresh_from_db()
        self.assertEqual(consumo.estado, AttendanceConsumption.Estado.CONSUMIDO)
        self.assertEqual(consumo.pago, pago)

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

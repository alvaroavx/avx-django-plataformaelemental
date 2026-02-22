from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase

from academia.models import Disciplina, SesionClase
from asistencias.models import Asistencia
from cobros.models import Pago, Plan
from cobros.services import aplicar_pago_a_deudas
from cuentas.models import Persona
from organizaciones.models import Organizacion


class PagoPlanClasesTests(TestCase):
    def setUp(self):
        self.organizacion = Organizacion.objects.create(
            nombre="Espacio Elementos",
            razon_social="Elementos SpA",
            rut="11.111.111-1",
        )
        self.persona = Persona.objects.create(
            nombres="Valentina",
            apellidos="Rios",
            email="valentina@example.com",
        )
        self.plan = Plan.objects.create(
            organizacion=self.organizacion,
            nombre="Plan 4 clases",
            precio=Decimal("50000"),
            duracion_dias=30,
            clases_por_semana=1,
            clases_por_mes=4,
        )
        self.disciplina = Disciplina.objects.create(
            organizacion=self.organizacion,
            nombre="Lyra",
        )

    def _crear_sesion_y_asistencia(self, fecha):
        sesion = SesionClase.objects.create(
            disciplina=self.disciplina,
            fecha=fecha,
        )
        asistencia = Asistencia.objects.create(
            sesion=sesion,
            persona=self.persona,
        )
        return asistencia

    def test_pago_plan_consumo_clases(self):
        pago = Pago.objects.create(
            persona=self.persona,
            tipo=Pago.Tipo.PLAN,
            plan=self.plan,
            fecha_pago=date.today(),
            monto=Decimal("50000"),
            metodo=Pago.Metodo.TRANSFERENCIA,
        )
        asistencia = self._crear_sesion_y_asistencia(date.today())
        pago.refresh_from_db()
        self.assertEqual(pago.clases_total, 4)
        self.assertEqual(pago.clases_usadas, 1)
        self.assertEqual(pago.clases_restantes(), 3)
        asistencia.refresh_from_db()
        self.assertEqual(asistencia.estado_cobro, Asistencia.EstadoCobro.CUBIERTA)

    def test_pago_plan_caducado_no_aplica(self):
        Pago.objects.create(
            persona=self.persona,
            tipo=Pago.Tipo.PLAN,
            plan=self.plan,
            fecha_pago=date.today() - timedelta(days=40),
            monto=Decimal("50000"),
            metodo=Pago.Metodo.TRANSFERENCIA,
        )
        asistencia = self._crear_sesion_y_asistencia(date.today())
        asistencia.refresh_from_db()
        self.assertEqual(asistencia.estado_cobro, Asistencia.EstadoCobro.DEUDA)

    def test_pago_posterior_cubre_deuda_fifo(self):
        sesion_1 = SesionClase.objects.create(disciplina=self.disciplina, fecha=date.today() - timedelta(days=2))
        sesion_2 = SesionClase.objects.create(disciplina=self.disciplina, fecha=date.today() - timedelta(days=1))
        asistencia_1 = Asistencia.objects.create(sesion=sesion_1, persona=self.persona)
        asistencia_2 = Asistencia.objects.create(sesion=sesion_2, persona=self.persona)
        pago = Pago.objects.create(
            persona=self.persona,
            tipo=Pago.Tipo.PLAN,
            plan=self.plan,
            fecha_pago=date.today(),
            monto=Decimal("50000"),
            metodo=Pago.Metodo.TRANSFERENCIA,
            clases_total=1,
        )
        aplicadas = aplicar_pago_a_deudas(self.persona, pago, lookback_days=90)
        self.assertEqual(aplicadas, 1)

        asistencia_1.refresh_from_db()
        asistencia_2.refresh_from_db()
        self.assertEqual(asistencia_1.estado_cobro, Asistencia.EstadoCobro.CUBIERTA)
        self.assertEqual(asistencia_2.estado_cobro, Asistencia.EstadoCobro.DEUDA)

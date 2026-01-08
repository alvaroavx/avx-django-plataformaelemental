from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase

from academia.models import Disciplina, SesionClase
from asistencias.models import Asistencia
from cobros.models import ConvenioIntercambio, Pago, Plan, Suscripcion
from cuentas.models import Persona
from organizaciones.models import Organizacion


class SuscripcionClasesTests(TestCase):
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
            nombre="Plan 2 clases",
            precio=Decimal("50000"),
            duracion_dias=28,
            clases_por_semana=2,
        )
        self.disciplina = Disciplina.objects.create(
            organizacion=self.organizacion,
            nombre="Lyra",
        )
        self.suscripcion = Suscripcion.objects.create(
            persona=self.persona,
            plan=self.plan,
            fecha_inicio=date.today() - timedelta(days=14),
            fecha_fin=date.today() + timedelta(days=14),
        )
        self.convenio = ConvenioIntercambio.objects.create(
            organizacion=self.organizacion,
            nombre="Yoga Exchange",
            descuento_porcentaje=Decimal("100.0"),
            vigente_desde=date.today() - timedelta(days=30),
        )

    def _crear_sesion_y_asistencia(self, fecha, con_convenio=False):
        sesion = SesionClase.objects.create(
            disciplina=self.disciplina,
            fecha=fecha,
        )
        Asistencia.objects.create(
            sesion=sesion,
            persona=self.persona,
            convenio=self.convenio if con_convenio else None,
        )

    def test_calculo_clases_asignadas_y_usadas(self):
        # 4 semanas aprox => 8 clases asignadas
        for offset in range(3):
            self._crear_sesion_y_asistencia(date.today() - timedelta(days=offset))
        # convenios no consumen saldo
        self._crear_sesion_y_asistencia(date.today() - timedelta(days=5), con_convenio=True)

        self.assertGreater(self.suscripcion.clases_asignadas(), 0)
        self.assertEqual(self.suscripcion.clases_usadas(), 3)
        self.assertEqual(self.suscripcion.clases_disponibles(), self.suscripcion.clases_asignadas() - 3)
        self.assertEqual(self.suscripcion.clases_sobreconsumo(), 0)

    def test_saldo_pendiente_considera_pagos(self):
        Pago.objects.create(
            persona=self.persona,
            suscripcion=self.suscripcion,
            fecha_pago=date.today(),
            monto=Decimal("20000"),
            metodo=Pago.Metodo.TRANSFERENCIA,
        )
        saldo = self.suscripcion.saldo_pendiente()
        self.assertEqual(saldo, Decimal("30000"))

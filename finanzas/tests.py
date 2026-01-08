from datetime import date
from decimal import Decimal

from django.test import TestCase

from academia.models import Disciplina, SesionClase
from asistencias.models import Asistencia
from cuentas.models import Persona
from finanzas.models import LiquidacionProfesor, MovimientoCaja, TarifaPagoProfesor
from organizaciones.models import Organizacion


class LiquidacionProfesorTests(TestCase):
    def setUp(self):
        self.organizacion = Organizacion.objects.create(
            nombre="Espacio Elementos",
            razon_social="Elementos SpA",
            rut="22.222.222-2",
        )
        self.profesor = Persona.objects.create(
            nombres="Carlos",
            apellidos="Lagos",
            email="carlos@example.com",
        )
        self.estudiante = Persona.objects.create(
            nombres="Ana",
            apellidos="Perez",
            email="ana@example.com",
        )
        self.disciplina = Disciplina.objects.create(
            organizacion=self.organizacion,
            nombre="Fuerza",
        )
        self.sesion = SesionClase.objects.create(
            disciplina=self.disciplina,
            profesor=self.profesor,
            fecha=date(2025, 1, 10),
        )
        Asistencia.objects.create(
            sesion=self.sesion,
            persona=self.estudiante,
        )
        TarifaPagoProfesor.objects.create(
            organizacion=self.organizacion,
            disciplina=None,
            monto_por_sesion=Decimal("5000"),
            vigente_desde=date(2024, 1, 1),
        )

    def test_calculo_liquidacion_con_tarifa(self):
        liquidacion = LiquidacionProfesor.objects.create(
            organizacion=self.organizacion,
            profesor=self.profesor,
            periodo_inicio=date(2025, 1, 1),
            periodo_fin=date(2025, 1, 31),
        )
        total_asistencias = liquidacion.calcular_totales()
        self.assertEqual(total_asistencias, 1)
        self.assertEqual(liquidacion.monto_total, Decimal("5000"))
        self.assertAlmostEqual(liquidacion.monto_retencion, Decimal("725.0"))
        self.assertAlmostEqual(liquidacion.monto_neto, Decimal("4275.0"))


class MovimientoCajaTests(TestCase):
    def test_calculo_iva(self):
        organizacion = Organizacion.objects.create(
            nombre="Org",
            razon_social="Org LTDA",
            rut="33.333.333-3",
        )
        movimiento = MovimientoCaja.objects.create(
            organizacion=organizacion,
            tipo=MovimientoCaja.Tipo.INGRESO,
            fecha=date.today(),
            monto_total=Decimal("119000"),
            afecta_iva=True,
            categoria=MovimientoCaja.Categoria.SERVICIOS,
            glosa="Venta taller",
        )
        self.assertEqual(movimiento.monto_iva, Decimal("19000.00"))
        self.assertEqual(movimiento.monto_neto, Decimal("100000.00"))

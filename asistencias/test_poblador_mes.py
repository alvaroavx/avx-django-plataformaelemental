from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from finanzas.models import AttendanceConsumption
from personas.models import Organizacion, Persona, PersonaRol, Rol

from .management.commands.poblar_mes_pruebas import MARCADOR
from .models import AsignacionProfesorDisciplina, Asistencia, Disciplina, SesionClase


@override_settings(DEBUG=True)
class PoblarMesPruebasTests(TestCase):
    def setUp(self):
        self.elementos = Organizacion.objects.create(
            nombre="Elementos seed",
            razon_social="Elementos seed",
            rut="76.000.001-1",
        )
        self.latin = Organizacion.objects.create(
            nombre="Latin seed",
            razon_social="Latin seed",
            rut="76.000.002-2",
        )
        profesor = Rol.objects.create(nombre="Profesor seed", codigo="PROFESOR")
        estudiante = Rol.objects.create(nombre="Estudiante seed", codigo="ESTUDIANTE")
        self.evelyn = Persona.objects.create(nombres="Evelyn", apellidos="Seed")
        self.laura = Persona.objects.create(nombres="Laura", apellidos="Seed")
        self.alvaro = Persona.objects.create(nombres="Álvaro", apellidos="Seed")
        PersonaRol.objects.create(persona=self.evelyn, rol=profesor, organizacion=self.elementos)
        PersonaRol.objects.create(persona=self.laura, rol=profesor, organizacion=self.latin)
        PersonaRol.objects.create(persona=self.alvaro, rol=profesor, organizacion=self.elementos)
        self.lyra = Disciplina.objects.create(organizacion=self.elementos, nombre="Lyra")
        self.latinrengo = Disciplina.objects.create(organizacion=self.latin, nombre="LatinRengo")
        for indice in range(12):
            alumno_elementos = Persona.objects.create(
                nombres=f"Alumno E {indice}",
                email=f"elementos.seed.{indice}@example.com",
            )
            alumno_latin = Persona.objects.create(
                nombres=f"Alumno L {indice}",
                email=f"latin.seed.{indice}@example.com",
            )
            PersonaRol.objects.create(persona=alumno_elementos, rol=estudiante, organizacion=self.elementos)
            PersonaRol.objects.create(persona=alumno_latin, rol=estudiante, organizacion=self.latin)

    def opciones(self):
        return {
            "anio": 2026,
            "mes": 8,
            "organizacion_elementos_id": self.elementos.pk,
            "organizacion_latin_id": self.latin.pk,
            "profesor_lyra_id": self.evelyn.pk,
            "profesor_latin_id": self.laura.pk,
            "profesor_circo_id": self.alvaro.pk,
        }

    def test_preview_no_escribe_y_aplicar_es_idempotente(self):
        salida = StringIO()
        call_command("poblar_mes_pruebas", stdout=salida, **self.opciones())
        self.assertIn('"modo": "preview"', salida.getvalue())
        self.assertEqual(SesionClase.objects.count(), 0)
        self.assertFalse(Disciplina.objects.filter(nombre="Tela Aérea").exists())

        call_command("poblar_mes_pruebas", aplicar=True, stdout=StringIO(), **self.opciones())
        circo = Disciplina.objects.get(organizacion=self.elementos, nombre="Tela Aérea")
        self.assertIn(MARCADOR, circo.descripcion)
        self.assertEqual(SesionClase.objects.filter(notas__contains=MARCADOR).count(), 14)
        self.assertEqual(Asistencia.objects.filter(comentario__contains=MARCADOR).count(), 25)
        self.assertEqual(AttendanceConsumption.objects.filter(asistencia__comentario__contains=MARCADOR).count(), 25)
        self.assertEqual(
            SesionClase.objects.get(disciplina=self.lyra, fecha="2026-08-03").estado,
            SesionClase.Estado.COMPLETADA,
        )
        self.assertEqual(
            SesionClase.objects.get(disciplina=self.lyra, fecha="2026-08-10").estado,
            SesionClase.Estado.ABIERTA,
        )
        latin_incompleta = SesionClase.objects.get(disciplina=self.latinrengo, fecha="2026-08-08")
        self.assertEqual(latin_incompleta.estado, SesionClase.Estado.PROGRAMADA)
        self.assertEqual(latin_incompleta.asistencias.count(), 0)
        self.assertEqual(
            SesionClase.objects.get(disciplina=circo, fecha="2026-08-07").estado,
            SesionClase.Estado.ABIERTA,
        )
        self.assertTrue(
            AsignacionProfesorDisciplina.objects.filter(
                disciplina=circo,
                profesor=self.alvaro,
                activa=True,
            ).exists()
        )

        call_command("poblar_mes_pruebas", aplicar=True, stdout=StringIO(), **self.opciones())
        self.assertEqual(SesionClase.objects.filter(notas__contains=MARCADOR).count(), 14)
        self.assertEqual(Asistencia.objects.filter(comentario__contains=MARCADOR).count(), 25)

    @override_settings(DEBUG=False)
    def test_rechaza_entorno_sin_debug(self):
        with self.assertRaisesMessage(CommandError, "bloqueado fuera"):
            call_command("poblar_mes_pruebas", aplicar=True, stdout=StringIO(), **self.opciones())

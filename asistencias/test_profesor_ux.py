from datetime import date

from django.test import TestCase
from django.urls import reverse

from personas.models import Persona, PersonaRol

from . import test_operacion_profesor as fixtures
from .models import AlumnoDisciplina
from .profesor_forms import PagoMasivoProfesorForm, PagoProfesorForm


class ProfesorUXTests(TestCase):
    # Reutiliza la matriz sintética existente de dos organizaciones.
    setUp = fixtures.ProfesorMultiOrganizacionTests.setUp
    _crear_alumno = fixtures.ProfesorMultiOrganizacionTests._crear_alumno
    _crear_sesion = fixtures.ProfesorMultiOrganizacionTests._crear_sesion
    _crear_pago = fixtures.ProfesorMultiOrganizacionTests._crear_pago

    def test_fecha_inicial_y_validacion_mensual_individual_y_masiva(self):
        for clase in (PagoProfesorForm, PagoMasivoProfesorForm):
            form = clase(periodo_mes=2, periodo_anio=2024)
            self.assertEqual(form.initial["fecha_pago"], date(2024, 2, 1))
            self.assertEqual(form.fields["fecha_pago"].widget.attrs["max"], "2024-02-29")
            self.assertIn('value="2024-02-01"', form["fecha_pago"].as_widget())
            for fecha, valida in (("2024-02-29", True), ("2024-03-01", False)):
                bound = clase(data={"fecha_pago": fecha}, periodo_mes=2, periodo_anio=2024)
                bound.is_valid()
                self.assertEqual("fecha_pago" not in bound.errors, valida)
        query = f"?organizacion={self.org_a.pk}&periodo_mes=2&periodo_anio=2024"
        for ruta in ("profesor:pago_crear", "profesor:pago_masivo"):
            response = self.client.get(reverse(ruta) + query)
            self.assertEqual(response.context["form"].initial["fecha_pago"], date(2024, 2, 1))

    def test_detalle_lectura_consolidada_y_aislamiento(self):
        query = "?organizacion=todos&periodo=todos"
        response = self.client.get(reverse("profesor:pagos") + query)
        self.assertContains(response, reverse("profesor:pago_detalle", args=[self.pago_a.pk]))
        self.assertNotContains(response, reverse("profesor:pago_crear"))
        for pago in (self.pago_a, self.pago_b):
            url = reverse("profesor:pago_detalle", args=[pago.pk]) + query
            self.assertEqual(self.client.get(url).status_code, 200)
            self.assertEqual(self.client.post(url, {}).status_code, 405)
        ajeno = reverse("profesor:pago_detalle", args=[self.pago_b.pk])
        self.assertEqual(self.client.get(ajeno + f"?organizacion={self.org_a.pk}").status_code, 404)
        fuera_periodo = reverse("profesor:pago_detalle", args=[self.pago_a.pk])
        self.assertEqual(self.client.get(fuera_periodo + f"?organizacion={self.org_a.pk}&periodo_mes=1&periodo_anio=2000").status_code, 404)

    def test_alumnos_busqueda_normalizada_paginacion_y_contexto(self):
        for indice in range(27):
            alumno = Persona.objects.create(nombres=f"Ágata {indice:02d}", apellidos="Prueba")
            PersonaRol.objects.create(persona=alumno, rol=self.rol_estudiante, organizacion=self.org_a, activo=True)
            AlumnoDisciplina.objects.create(disciplina=self.disciplina_a, alumno=alumno)
        url = reverse("profesor:alumnos") + f"?organizacion={self.org_a.pk}&periodo=todos&q=agata"
        primera = self.client.get(url)
        segunda = self.client.get(url + "&pagina=2")
        self.assertEqual(primera.context["page_obj"].paginator.count, 27)
        self.assertEqual(len(primera.context["alumnos"]), 25)
        self.assertEqual(len(segunda.context["alumnos"]), 2)
        self.assertFalse({p.pk for p in primera.context["alumnos"]} & {p.pk for p in segunda.context["alumnos"]})
        self.assertContains(primera, "q=agata&amp;pagina=2")
        self.assertNotContains(primera, self.alumno_b.nombre_completo)
        vacio = self.client.get(url.replace("agata", "inexistente"))
        self.assertContains(vacio, "Sin resultados")
        self.assertContains(vacio, "Limpiar búsqueda")

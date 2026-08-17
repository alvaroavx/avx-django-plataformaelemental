from datetime import timedelta
from decimal import Decimal
import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from auditoria.models import AuditLog
from finanzas.models import Category, LotePago, Payment, PaymentPlan, Transaction
from finanzas.services import confirmar_lote_pagos
from personas.models import Organizacion, Persona, PersonaRol, Rol

from .models import (
    AlumnoDisciplina,
    AsignacionProfesorDisciplina,
    Asistencia,
    Disciplina,
    LiberacionSesion,
    SesionClase,
)


PASSWORD = "profesor-test-password"


class OperacionProfesorAcceptanceTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.org = Organizacion.objects.create(nombre="Elementos QA", razon_social="Elementos QA", rut="77.111.111-1")
        self.otra_org = Organizacion.objects.create(nombre="Ajena QA", razon_social="Ajena QA", rut="77.222.222-2")
        self.rol_profesor = Rol.objects.create(nombre="Profesor QA", codigo="PROFESOR")
        self.rol_estudiante = Rol.objects.create(nombre="Estudiante QA", codigo="ESTUDIANTE")
        self.rol_admin = Rol.objects.create(nombre="Admin QA", codigo="ADMIN")
        self.user = User.objects.create_user("profesor.qa", password=PASSWORD)
        self.profesor = Persona.objects.create(
            nombres="Paula",
            apellidos="Profesora",
            email="paula.profesor@example.com",
            user=self.user,
        )
        PersonaRol.objects.create(persona=self.profesor, rol=self.rol_profesor, organizacion=self.org, activo=True)
        self.disciplina = Disciplina.objects.create(organizacion=self.org, nombre="Yoga Profesor")
        self.disciplina_ajena = Disciplina.objects.create(organizacion=self.otra_org, nombre="Pilates Ajeno")
        AsignacionProfesorDisciplina.objects.create(disciplina=self.disciplina, profesor=self.profesor)
        self.alumno = Persona.objects.create(
            nombres="Ana",
            apellidos="Asignada",
            email="ana.asignada@example.com",
        )
        PersonaRol.objects.create(persona=self.alumno, rol=self.rol_estudiante, organizacion=self.org, activo=True)
        AlumnoDisciplina.objects.create(disciplina=self.disciplina, alumno=self.alumno)
        self.alumno_sin_clase = Persona.objects.create(
            nombres="Sonia",
            apellidos="Sin clase",
            email="sonia.sinclase@example.com",
        )
        PersonaRol.objects.create(
            persona=self.alumno_sin_clase,
            rol=self.rol_estudiante,
            organizacion=self.org,
            activo=True,
        )
        self.sesion = SesionClase.objects.create(disciplina=self.disciplina, fecha=timezone.localdate())
        self.sesion.profesores.add(self.profesor)
        self.sesion_ajena = SesionClase.objects.create(disciplina=self.disciplina_ajena, fecha=timezone.localdate())
        self.plan = PaymentPlan.objects.create(
            organizacion=self.org,
            nombre="Plan profesor",
            num_clases=4,
            precio=20000,
        )
        self.client.force_login(self.user)

    def _url_profesor(self, nombre, *args):
        return f"{reverse(nombre, args=args or None)}?organizacion={self.org.pk}"

    def _parametros_profesor(self, **extra):
        return {"organizacion": self.org.pk, **extra}

    def test_login_operativo_redirige_al_tablero_y_no_expone_admin_global(self):
        inicio = self.client.get(reverse("elemental_apps"))
        self.assertRedirects(inicio, reverse("profesor:inicio"))
        tablero = self.client.get(self._url_profesor("profesor:inicio"))
        self.assertEqual(tablero.status_code, 200)
        self.assertNotContains(tablero, "Tablero Elemental Operativo")
        self.assertContains(tablero, "Contexto de trabajo")
        self.assertContains(tablero, "Inicio")
        self.assertContains(tablero, "Mis clases")
        self.assertNotContains(tablero, "Pilates Ajeno")
        self.assertContains(tablero, "Sesión de hoy")
        sesion_form = self.client.get(self._url_profesor("profesor:sesion_crear")).context["form"]
        pago_form = self.client.get(self._url_profesor("profesor:pago_crear")).context["form"]
        lote_form = self.client.get(self._url_profesor("profesor:pago_masivo")).context["form"]
        self.assertEqual(sesion_form.initial["fecha"], timezone.localdate())
        self.assertEqual(pago_form.initial["fecha_pago"], timezone.localdate())
        self.assertTrue(pago_form.initial["clave_idempotencia"])
        self.assertEqual(lote_form.initial["fecha_pago"], timezone.localdate())
        self.assertTrue(lote_form.initial["clave_idempotencia"])
        self.assertEqual(self.client.get(reverse("personas:organizaciones_list")).status_code, 403)
        self.assertEqual(self.client.get(reverse("finanzas:dashboard")).status_code, 403)
        self.assertEqual(
            self.client.get(
                self._url_profesor(
                    "asistencias:sesion_detail",
                    self.sesion_ajena.pk,
                )
            ).status_code,
            404,
        )

    def test_crea_y_libera_sesion_propia_con_motivo_y_auditoria(self):
        fecha = timezone.localdate() + timedelta(days=3)
        crear = self.client.post(
            self._url_profesor("profesor:sesion_crear"),
            {"disciplina": self.disciplina.pk, "fecha": fecha.isoformat()},
        )
        self.assertEqual(crear.status_code, 302)
        sesion = SesionClase.objects.get(fecha=fecha, disciplina=self.disciplina)
        self.assertEqual(list(sesion.profesores.all()), [self.profesor])
        sin_motivo = self.client.post(
            self._url_profesor("profesor:sesion_liberar", sesion.pk),
            {"motivo": ""},
        )
        self.assertEqual(sin_motivo.status_code, 302)
        self.assertFalse(LiberacionSesion.objects.filter(sesion=sesion).exists())
        with self.captureOnCommitCallbacks(execute=True):
            liberar = self.client.post(
                self._url_profesor("profesor:sesion_liberar", sesion.pk),
                {"motivo": "Profesor con licencia"},
            )
        self.assertRedirects(liberar, self._url_profesor("profesor:sesiones"))
        sesion.refresh_from_db()
        self.assertEqual(sesion.estado, SesionClase.Estado.CANCELADA)
        self.assertTrue(
            AuditLog.objects.filter(resumen="Sesión liberada por profesor", organizacion=self.org).exists()
        )

    def test_alta_alumno_exige_telefono_o_email_y_asocia_solo_clase_propia(self):
        invalido = self.client.post(
            self._url_profesor("profesor:alumno_crear"),
            {"disciplina": self.disciplina.pk, "nombres": "Sin", "apellidos": "Contacto"},
        )
        self.assertEqual(invalido.status_code, 200)
        self.assertContains(invalido, "teléfono o un correo válido")
        self.assertFalse(Persona.objects.filter(nombres="Sin", apellidos="Contacto").exists())
        valido = self.client.post(
            self._url_profesor("profesor:alumno_crear"),
            {
                "disciplina": self.disciplina.pk,
                "nombres": "Nuevo",
                "apellidos": "Alumno",
                "email": "nuevo.alumno@example.com",
                "telefono": "",
            },
        )
        self.assertRedirects(valido, self._url_profesor("profesor:alumnos"))
        nuevo = Persona.objects.get(email="nuevo.alumno@example.com")
        self.assertTrue(AlumnoDisciplina.objects.filter(alumno=nuevo, disciplina=self.disciplina, activa=True).exists())
        ajeno = self.client.post(
            self._url_profesor("profesor:alumno_crear"),
            {
                "disciplina": self.disciplina_ajena.pk,
                "nombres": "No",
                "apellidos": "Autorizado",
                "email": "no.autorizado@example.com",
            },
        )
        self.assertEqual(ajeno.status_code, 200)
        self.assertFalse(Persona.objects.filter(email="no.autorizado@example.com").exists())

    def test_busqueda_asistencia_limita_matricula_y_correccion_queda_auditada(self):
        buscar = self.client.get(
            reverse("asistencias:sesion_asistentes_buscar", args=[self.sesion.pk]),
            self._parametros_profesor(q="Ana"),
        )
        ids = {item["id"] for item in buscar.json()["resultados"]}
        self.assertIn(self.alumno.pk, ids)
        self.assertNotIn(self.alumno_sin_clase.pk, ids)
        agregar = self.client.post(
            self._url_profesor("asistencias:sesion_asistente_agregar", self.sesion.pk),
            {"persona_id": self.alumno.pk},
        )
        self.assertEqual(agregar.status_code, 201)
        self.sesion.refresh_from_db()
        self.assertEqual(self.sesion.estado, SesionClase.Estado.ABIERTA)
        asistencia = Asistencia.objects.get(sesion=self.sesion, persona=self.alumno)
        with self.captureOnCommitCallbacks(execute=True):
            corregir = self.client.post(
                self._url_profesor(
                    "asistencias:sesion_asistencia_estado",
                    self.sesion.pk,
                    asistencia.pk,
                ),
                {"estado": Asistencia.Estado.JUSTIFICADA},
            )
        self.assertEqual(corregir.status_code, 200)
        asistencia.refresh_from_db()
        self.assertEqual(asistencia.estado, Asistencia.Estado.JUSTIFICADA)
        self.assertTrue(AuditLog.objects.filter(objeto_id=str(asistencia.pk), dominio="asistencias").exists())

    def test_busquedas_de_alumnos_aceptan_nombre_completo_sin_tildes(self):
        alumna = Persona.objects.create(
            nombres="Ángela María",
            apellidos="Núñez Peña",
            email="angela.nunez@example.com",
        )
        PersonaRol.objects.create(
            persona=alumna,
            rol=self.rol_estudiante,
            organizacion=self.org,
            activo=True,
        )
        AlumnoDisciplina.objects.create(disciplina=self.disciplina, alumno=alumna)

        asistentes = self.client.get(
            reverse("asistencias:sesion_asistentes_buscar", args=[self.sesion.pk]),
            self._parametros_profesor(q="angela nunez"),
        )
        pagos_masivos = self.client.get(
            reverse("profesor:pago_masivo_alumnos"),
            self._parametros_profesor(
                disciplina=self.disciplina.pk,
                q="angela nunez",
            ),
        )

        self.assertEqual(asistentes.status_code, 200)
        self.assertEqual(pagos_masivos.status_code, 200)
        self.assertIn(alumna.pk, {item["id"] for item in asistentes.json()["resultados"]})
        self.assertIn(alumna.pk, {item["id"] for item in pagos_masivos.json()["resultados"]})

    def test_pago_individual_crea_transaccion_unica_actor_y_alcance(self):
        payload = {
            "disciplina": self.disciplina.pk,
            "persona": self.alumno.pk,
            "plan": self.plan.pk,
            "fecha_pago": timezone.localdate().isoformat(),
            "metodo_pago": Payment.Metodo.EFECTIVO,
            "numero_comprobante": "",
            "monto": "20000",
            "clases_asignadas": "4",
            "glosa": "Pago mensual Yoga",
            "clave_idempotencia": "profesor-individual-1",
        }
        primero = self.client.post(self._url_profesor("profesor:pago_crear"), payload)
        self.assertEqual(primero.status_code, 302)
        segundo = self.client.post(self._url_profesor("profesor:pago_crear"), payload)
        self.assertEqual(segundo.status_code, 302)
        self.assertEqual(Payment.objects.filter(clave_idempotencia="profesor-individual-1").count(), 1)
        pago = Payment.objects.get(clave_idempotencia="profesor-individual-1")
        self.assertEqual(pago.registrado_por, self.user)
        self.assertEqual(pago.disciplina, self.disciplina)
        self.assertIsNotNone(pago.transaccion_id)
        self.assertEqual(pago.transaccion.monto, pago.monto_total)
        self.assertEqual(pago.transaccion.creado_por, self.user)
        self.assertEqual(pago.transaccion.pago_operacional, pago)
        self.assertEqual(Transaction.objects.filter(pago_operacional=pago).count(), 1)

    def test_correccion_pago_permanece_restringida_sin_contramovimiento_contable(self):
        payload = {
            "disciplina": self.disciplina.pk,
            "persona": self.alumno.pk,
            "plan": self.plan.pk,
            "fecha_pago": timezone.localdate().isoformat(),
            "metodo_pago": Payment.Metodo.TRANSFERENCIA,
            "numero_comprobante": "TRX-PRUEBA-REVERSA",
            "monto": "24000",
            "clases_asignadas": "4",
            "glosa": "Pago que requiere corrección",
            "clave_idempotencia": "profesor-reversa-1",
        }
        self.assertEqual(
            self.client.post(self._url_profesor("profesor:pago_crear"), payload).status_code,
            302,
        )
        pago = Payment.objects.get(clave_idempotencia="profesor-reversa-1")
        monto_original = pago.monto_total
        transaccion_original = pago.transaccion_id

        detalle = self.client.get(self._url_profesor("profesor:pago_detalle", pago.pk))
        self.assertNotContains(detalle, "Revertir pago")
        self.assertNotContains(detalle, f"/profesor/pagos/{pago.pk}/revertir/")
        denegada = self.client.post(
            f"/profesor/pagos/{pago.pk}/revertir/?organizacion={self.org.pk}",
            {"motivo": "No debe existir esta operación"},
        )
        self.assertEqual(denegada.status_code, 404)
        pago.refresh_from_db()
        self.assertIsNone(pago.revertido_en)
        self.assertEqual(pago.monto_total, monto_original)
        self.assertEqual(pago.transaccion_id, transaccion_original)
        self.assertEqual(Transaction.objects.filter(pago_operacional=pago).count(), 1)


class ProfesorMultiOrganizacionTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.org_a = Organizacion.objects.create(
            nombre="Espacio Elementos",
            razon_social="Espacio Elementos SpA",
            rut="76.600.001-1",
        )
        self.org_b = Organizacion.objects.create(
            nombre="Latin Rengo",
            razon_social="Latin Rengo SpA",
            rut="76.600.002-K",
        )
        self.org_ajena = Organizacion.objects.create(
            nombre="Organización Ajena",
            razon_social="Organización Ajena SpA",
            rut="76.600.003-8",
        )
        self.org_sin_rol_profesor = Organizacion.objects.create(
            nombre="Organización Estudiante",
            razon_social="Organización Estudiante SpA",
            rut="76.600.004-6",
        )
        self.rol_profesor = Rol.objects.create(
            nombre="Profesor multi organización",
            codigo="PROFESOR",
        )
        self.rol_estudiante = Rol.objects.create(
            nombre="Estudiante multi organización",
            codigo="ESTUDIANTE",
        )
        self.user = User.objects.create_user("alvax.multi", password=PASSWORD)
        self.profesor = Persona.objects.create(
            nombres="Álvaro",
            apellidos="Multi Organización",
            email="alvax.multi@example.test",
            user=self.user,
        )
        self.rol_a = PersonaRol.objects.create(
            persona=self.profesor,
            rol=self.rol_profesor,
            organizacion=self.org_a,
            activo=True,
        )
        self.rol_b = PersonaRol.objects.create(
            persona=self.profesor,
            rol=self.rol_profesor,
            organizacion=self.org_b,
            activo=True,
        )
        PersonaRol.objects.create(
            persona=self.profesor,
            rol=self.rol_estudiante,
            organizacion=self.org_sin_rol_profesor,
            activo=True,
        )
        self.disciplina_a = Disciplina.objects.create(
            organizacion=self.org_a,
            nombre="Aéreos Elementos",
        )
        self.disciplina_b = Disciplina.objects.create(
            organizacion=self.org_b,
            nombre="Salsa Latin Rengo",
        )
        for disciplina in (self.disciplina_a, self.disciplina_b):
            AsignacionProfesorDisciplina.objects.create(
                disciplina=disciplina,
                profesor=self.profesor,
            )
        self.alumno_a = self._crear_alumno(
            organizacion=self.org_a,
            disciplina=self.disciplina_a,
            nombres="Alumno Elementos",
        )
        self.alumno_b = self._crear_alumno(
            organizacion=self.org_b,
            disciplina=self.disciplina_b,
            nombres="Alumno Latin",
        )
        self.sesion_a = self._crear_sesion(self.disciplina_a)
        self.sesion_b = self._crear_sesion(self.disciplina_b)
        self.sesion_a_no_asignada = SesionClase.objects.create(
            disciplina=self.disciplina_a,
            fecha=timezone.localdate(),
        )
        self.plan_a = PaymentPlan.objects.create(
            organizacion=self.org_a,
            nombre="Plan Elementos",
            num_clases=4,
            precio=11111,
        )
        self.plan_b = PaymentPlan.objects.create(
            organizacion=self.org_b,
            nombre="Plan Latin",
            num_clases=4,
            precio=22222,
        )
        self.pago_a = self._crear_pago(
            organizacion=self.org_a,
            disciplina=self.disciplina_a,
            alumno=self.alumno_a,
            plan=self.plan_a,
            monto=11111,
        )
        self.pago_b = self._crear_pago(
            organizacion=self.org_b,
            disciplina=self.disciplina_b,
            alumno=self.alumno_b,
            plan=self.plan_b,
            monto=22222,
        )
        self.client.force_login(self.user)

    def _crear_alumno(self, *, organizacion, disciplina, nombres):
        alumno = Persona.objects.create(
            nombres=nombres,
            apellidos="Prueba",
            email=f"{disciplina.pk}.{organizacion.pk}@example.test",
        )
        PersonaRol.objects.create(
            persona=alumno,
            rol=self.rol_estudiante,
            organizacion=organizacion,
            activo=True,
        )
        AlumnoDisciplina.objects.create(disciplina=disciplina, alumno=alumno)
        return alumno

    def _crear_sesion(self, disciplina):
        sesion = SesionClase.objects.create(
            disciplina=disciplina,
            fecha=timezone.localdate(),
        )
        sesion.profesores.add(self.profesor)
        return sesion

    def _crear_pago(self, *, organizacion, disciplina, alumno, plan, monto):
        return Payment.objects.create(
            organizacion=organizacion,
            disciplina=disciplina,
            persona=alumno,
            plan=plan,
            fecha_pago=timezone.localdate(),
            metodo_pago=Payment.Metodo.EFECTIVO,
            aplica_iva=False,
            monto_referencia=monto,
            clases_asignadas=4,
        )

    def _url(self, nombre, organizacion, *args):
        return f"{reverse(nombre, args=args or None)}?organizacion={organizacion.pk}"

    def test_selector_expone_ambas_organizaciones_y_abre_cada_contexto(self):
        selector = self.client.get(reverse("profesor:inicio"))

        self.assertEqual(selector.status_code, 200)
        self.assertContains(selector, self.org_a.nombre)
        self.assertContains(selector, self.org_b.nombre)
        self.assertContains(selector, f"organizacion={self.org_a.pk}")
        self.assertContains(selector, f"organizacion={self.org_b.pk}")

        contexto_a = self.client.get(self._url("profesor:inicio", self.org_a))
        contexto_b = self.client.get(self._url("profesor:inicio", self.org_b))
        self.assertEqual(contexto_a.context["organizacion_activa"], self.org_a)
        self.assertEqual(contexto_b.context["organizacion_activa"], self.org_b)
        self.assertContains(contexto_a, '<select class="form-select" id="contexto-organizacion"', html=False)
        self.assertContains(contexto_a, "Todas mis organizaciones")
        self.assertContains(contexto_b, self.org_b.nombre)

    def test_organizacion_autorizada_sin_asignacion_es_visible_pero_no_operable(self):
        organizacion = Organizacion.objects.create(
            nombre="Organización sin clases",
            razon_social="Organización sin clases SpA",
            rut="76.600.005-4",
        )
        PersonaRol.objects.create(
            persona=self.profesor,
            rol=self.rol_profesor,
            organizacion=organizacion,
            activo=True,
        )

        selector = self.client.get(reverse("profesor:inicio"))
        inicio = self.client.get(self._url("profesor:inicio", organizacion))

        self.assertContains(selector, organizacion.nombre)
        self.assertEqual(inicio.status_code, 200)
        self.assertContains(inicio, "Sin clases asignadas")
        self.assertNotContains(inicio, reverse("profesor:sesion_crear"))
        self.assertNotContains(inicio, reverse("profesor:alumno_crear"))
        self.assertNotContains(inicio, reverse("profesor:pago_crear"))

        for nombre in (
            "profesor:sesion_crear",
            "profesor:alumno_crear",
            "profesor:pago_crear",
            "profesor:pago_masivo",
        ):
            with self.subTest(nombre=nombre):
                self.assertEqual(self.client.get(self._url(nombre, organizacion)).status_code, 403)

    def test_hoy_y_detalle_conservan_selector_profesor_estricto(self):
        hoy = self.client.get(self._url("asistencias:sesiones_hoy", self.org_a))
        detalle = self.client.get(
            self._url("asistencias:sesion_detail", self.org_a, self.sesion_a.pk)
        )

        for respuesta in (hoy, detalle):
            self.assertEqual(respuesta.status_code, 200)
            self.assertTrue(respuesta.context["profesor_mode"])
            self.assertContains(respuesta, self.org_a.nombre)
            self.assertContains(respuesta, self.org_b.nombre)
            self.assertNotContains(respuesta, self.org_sin_rol_profesor.nombre)
            self.assertContains(respuesta, '<option value="todos"', html=False)
            self.assertContains(respuesta, f"organizacion={self.org_a.pk}")

        self.assertContains(hoy, self.disciplina_a.nombre)
        self.assertNotContains(hoy, self.disciplina_b.nombre)

    def test_rol_administrativo_no_rompe_asignaciones_del_contexto_profesor(self):
        rol_admin = Rol.objects.create(
            nombre="Administración multi organización",
            codigo="ADMINISTRADOR",
        )
        PersonaRol.objects.create(
            persona=self.profesor,
            rol=rol_admin,
            organizacion=self.org_a,
            activo=True,
        )

        hoy_a = self.client.get(self._url("asistencias:sesiones_hoy", self.org_a))

        self.assertEqual(hoy_a.status_code, 200)
        self.assertTrue(hoy_a.context["profesor_mode"])
        self.assertEqual(
            [sesion.pk for sesion in hoy_a.context["sesiones"]],
            [self.sesion_a.pk],
        )
        self.assertContains(hoy_a, self.disciplina_a.nombre)
        self.assertNotContains(hoy_a, self.disciplina_b.nombre)

    def test_listados_y_formularios_quedan_aislados_por_contexto(self):
        for organizacion, disciplina_propia, alumno_propio, disciplina_ajena, alumno_ajeno in (
            (
                self.org_a,
                self.disciplina_a.nombre,
                self.alumno_a.nombre_completo,
                self.disciplina_b.nombre,
                self.alumno_b.nombre_completo,
            ),
            (
                self.org_b,
                self.disciplina_b.nombre,
                self.alumno_b.nombre_completo,
                self.disciplina_a.nombre,
                self.alumno_a.nombre_completo,
            ),
        ):
            with self.subTest(organizacion=organizacion.nombre):
                inicio = self.client.get(self._url("profesor:inicio", organizacion))
                sesiones = self.client.get(self._url("profesor:sesiones", organizacion))
                alumnos = self.client.get(self._url("profesor:alumnos", organizacion))
                pagos = self.client.get(self._url("profesor:pagos", organizacion))
                for respuesta in (inicio, sesiones, alumnos, pagos):
                    self.assertEqual(respuesta.status_code, 200)
                for respuesta in (inicio, sesiones, pagos):
                    self.assertContains(respuesta, disciplina_propia)
                    self.assertNotContains(respuesta, disciplina_ajena)
                for respuesta in (inicio, alumnos, pagos):
                    self.assertContains(respuesta, alumno_propio)
                    self.assertNotContains(respuesta, alumno_ajeno)

        form_a = self.client.get(self._url("profesor:pago_crear", self.org_a)).context["form"]
        form_b = self.client.get(self._url("profesor:pago_crear", self.org_b)).context["form"]
        self.assertQuerySetEqual(form_a.fields["plan"].queryset, [self.plan_a])
        self.assertQuerySetEqual(form_b.fields["plan"].queryset, [self.plan_b])
        self.assertQuerySetEqual(form_a.fields["persona"].queryset, [self.alumno_a])
        self.assertQuerySetEqual(form_b.fields["persona"].queryset, [self.alumno_b])

    def test_todas_mis_organizaciones_agrega_lectura_e_impide_mutaciones(self):
        query = "?organizacion=todos"
        respuestas = {
            "sesiones": self.client.get(reverse("profesor:sesiones") + query),
            "alumnos": self.client.get(reverse("profesor:alumnos") + query),
            "pagos": self.client.get(reverse("profesor:pagos") + query),
        }

        for respuesta in respuestas.values():
            self.assertEqual(respuesta.status_code, 200)
            self.assertTrue(respuesta.context["organizacion_todas"])
            self.assertFalse(respuesta.context["contexto_mutable"])
            self.assertContains(respuesta, "lectura")
        self.assertContains(respuestas["sesiones"], self.disciplina_a.nombre)
        self.assertContains(respuestas["sesiones"], self.disciplina_b.nombre)
        self.assertContains(respuestas["sesiones"], self.org_a.nombre)
        self.assertContains(respuestas["sesiones"], self.org_b.nombre)
        self.assertContains(respuestas["alumnos"], self.alumno_a.nombre_completo)
        self.assertContains(respuestas["alumnos"], self.alumno_b.nombre_completo)
        self.assertContains(respuestas["pagos"], self.pago_a.persona.nombre_completo)
        self.assertContains(respuestas["pagos"], self.pago_b.persona.nombre_completo)

        sesiones_antes = SesionClase.objects.count()
        mutacion = self.client.post(
            reverse("profesor:sesion_crear") + query,
            {
                "disciplina": self.disciplina_a.pk,
                "fecha": (timezone.localdate() + timedelta(days=3)).isoformat(),
            },
        )
        self.assertEqual(mutacion.status_code, 403)
        self.assertEqual(SesionClase.objects.count(), sesiones_antes)

    def test_periodo_explicito_filtra_inicio_clases_y_pagos(self):
        hoy = timezone.localdate()
        fecha_anterior = hoy.replace(day=1) - timedelta(days=1)
        sesion_anterior = SesionClase.objects.create(
            disciplina=self.disciplina_a,
            fecha=fecha_anterior,
        )
        sesion_anterior.profesores.add(self.profesor)
        pago_anterior = self._crear_pago(
            organizacion=self.org_a,
            disciplina=self.disciplina_a,
            alumno=self.alumno_a,
            plan=self.plan_a,
            monto=33333,
        )
        Payment.objects.filter(pk=pago_anterior.pk).update(fecha_pago=fecha_anterior)

        query_anterior = (
            f"?organizacion={self.org_a.pk}&periodo_mes={fecha_anterior.month}"
            f"&periodo_anio={fecha_anterior.year}"
        )
        inicio = self.client.get(reverse("profesor:inicio") + query_anterior)
        sesiones = self.client.get(reverse("profesor:sesiones") + query_anterior)
        pagos = self.client.get(reverse("profesor:pagos") + query_anterior)

        self.assertEqual(inicio.context["proxima_sesion"], sesion_anterior)
        self.assertEqual(
            [sesion.pk for sesion in sesiones.context["sesiones_historicas"]],
            [sesion_anterior.pk],
        )
        self.assertEqual([pago.pk for pago in pagos.context["pagos"]], [pago_anterior.pk])
        self.assertNotIn(self.pago_a.pk, [pago.pk for pago in pagos.context["pagos"]])

    def test_todos_los_periodos_pagina_de_25_y_es_solo_lectura(self):
        hoy = timezone.localdate()
        for desplazamiento in range(1, 31):
            sesion = SesionClase.objects.create(
                disciplina=self.disciplina_a,
                fecha=hoy - timedelta(days=desplazamiento),
            )
            sesion.profesores.add(self.profesor)
            self._crear_pago(
                organizacion=self.org_a,
                disciplina=self.disciplina_a,
                alumno=self.alumno_a,
                plan=self.plan_a,
                monto=10000 + desplazamiento,
            )

        query = f"?organizacion={self.org_a.pk}&periodo=todos"
        sesiones = self.client.get(reverse("profesor:sesiones") + query)
        pagos = self.client.get(reverse("profesor:pagos") + query)

        self.assertFalse(sesiones.context["contexto_mutable"])
        self.assertEqual(len(sesiones.context["page_obj"]), 25)
        self.assertGreater(sesiones.context["page_obj"].paginator.count, 25)
        self.assertEqual(len(pagos.context["page_obj"]), 25)
        self.assertEqual(pagos.context["monto_total_label"], "Total histórico")
        self.assertNotContains(sesiones, reverse("profesor:sesion_crear"))
        self.assertNotContains(pagos, reverse("profesor:pago_crear"))

        pagina_dos = self.client.get(reverse("profesor:sesiones") + query + "&pagina=2")
        ids_uno = {sesion.pk for sesion in sesiones.context["page_obj"]}
        ids_dos = {sesion.pk for sesion in pagina_dos.context["page_obj"]}
        self.assertFalse(ids_uno & ids_dos)

    def test_contrato_periodo_invalido_o_ambiguo_devuelve_404(self):
        base = reverse("profesor:sesiones")
        casos = (
            f"?organizacion={self.org_a.pk}&periodo=todos&periodo_mes=8&periodo_anio=2026",
            f"?organizacion={self.org_a.pk}&periodo_mes=8",
            f"?organizacion={self.org_a.pk}&periodo_mes=13&periodo_anio=2026",
        )
        for query in casos:
            with self.subTest(query=query):
                self.assertEqual(self.client.get(base + query).status_code, 404)

    def test_contextos_invalidos_inactivos_y_staff_sin_bypass_devuelven_404(self):
        self.assertEqual(self.client.get(reverse("profesor:sesiones")).status_code, 404)
        self.assertEqual(
            self.client.get(f"{reverse('profesor:sesiones')}?organizacion=999999").status_code,
            404,
        )
        self.assertEqual(self.client.get(self._url("profesor:sesiones", self.org_ajena)).status_code, 404)
        self.assertEqual(
            self.client.get(
                self._url("profesor:sesiones", self.org_sin_rol_profesor)
            ).status_code,
            404,
        )

        self.rol_b.activo = False
        self.rol_b.save(update_fields=["activo"])
        self.assertEqual(self.client.get(self._url("profesor:sesiones", self.org_b)).status_code, 404)

        self.user.is_staff = True
        self.user.save(update_fields=["is_staff"])
        self.assertEqual(self.client.get(self._url("profesor:sesiones", self.org_ajena)).status_code, 404)

    def test_post_y_recursos_manipulados_no_escriben_ni_filtran_datos(self):
        sesiones_b_antes = SesionClase.objects.filter(disciplina=self.disciplina_b).count()
        pagos_antes = Payment.objects.count()
        asistencia_corrupta = Asistencia.objects.create(
            sesion=self.sesion_a,
            persona=self.alumno_b,
        )

        sesion_manipulada = self.client.post(
            self._url("profesor:sesion_crear", self.org_a),
            {
                "disciplina": self.disciplina_b.pk,
                "fecha": (timezone.localdate() + timedelta(days=2)).isoformat(),
            },
        )
        pago_manipulado = self.client.post(
            self._url("profesor:pago_crear", self.org_a),
            {
                "disciplina": self.disciplina_b.pk,
                "persona": self.alumno_b.pk,
                "plan": self.plan_b.pk,
                "fecha_pago": timezone.localdate().isoformat(),
                "metodo_pago": Payment.Metodo.EFECTIVO,
                "monto": "22222",
                "clases_asignadas": "4",
                "glosa": "Pago manipulado",
                "clave_idempotencia": "multi-org-manipulado",
            },
        )
        detalle_ajeno = self.client.get(
            self._url("asistencias:sesion_detail", self.org_a, self.sesion_b.pk)
        )
        agregar_ajeno = self.client.post(
            self._url(
                "asistencias:sesion_asistente_agregar",
                self.org_a,
                self.sesion_b.pk,
            ),
            {"persona_id": self.alumno_b.pk},
        )
        quitar_ajeno = self.client.post(
            self._url("asistencias:sesion_detail", self.org_a, self.sesion_a.pk),
            {
                "eliminar_asistente": "1",
                "asistencia_id": asistencia_corrupta.pk,
            },
        )

        self.assertEqual(sesion_manipulada.status_code, 200)
        self.assertEqual(pago_manipulado.status_code, 200)
        self.assertEqual(detalle_ajeno.status_code, 404)
        self.assertEqual(agregar_ajeno.status_code, 404)
        self.assertEqual(quitar_ajeno.status_code, 403)
        self.assertEqual(
            SesionClase.objects.filter(disciplina=self.disciplina_b).count(),
            sesiones_b_antes,
        )
        self.assertEqual(Payment.objects.count(), pagos_antes)
        self.assertFalse(
            Asistencia.objects.filter(
                sesion=self.sesion_b,
                persona=self.alumno_b,
            ).exists()
        )
        self.assertTrue(Asistencia.objects.filter(pk=asistencia_corrupta.pk).exists())

    def test_asignacion_de_disciplina_y_sesion_siguen_siendo_obligatorias(self):
        self.assertEqual(
            self.client.get(
                self._url(
                    "asistencias:sesion_detail",
                    self.org_a,
                    self.sesion_a_no_asignada.pk,
                )
            ).status_code,
            404,
        )


class PagoMasivoProfesorIntegrityTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.org = Organizacion.objects.create(nombre="Lotes Profesor", razon_social="Lotes Profesor", rut="78.333.333-3")
        self.rol_profesor = Rol.objects.create(nombre="Profesor lote", codigo="PROFESOR")
        self.rol_estudiante = Rol.objects.create(nombre="Estudiante lote", codigo="ESTUDIANTE")
        self.user = User.objects.create_user("profesor.lote", password=PASSWORD)
        self.profesor = Persona.objects.create(nombres="Profesor", apellidos="Lote", user=self.user)
        PersonaRol.objects.create(persona=self.profesor, rol=self.rol_profesor, organizacion=self.org, activo=True)
        self.disciplina = Disciplina.objects.create(organizacion=self.org, nombre="Clase lote")
        AsignacionProfesorDisciplina.objects.create(disciplina=self.disciplina, profesor=self.profesor)
        self.plan = PaymentPlan.objects.create(organizacion=self.org, nombre="Plan lote profesor", num_clases=2, precio=10000)
        self.alumnos = []
        for indice in range(20):
            alumno = Persona.objects.create(
                nombres=f"Alumno {indice}",
                apellidos="Lote",
                email=f"alumno.{indice}@example.com",
            )
            PersonaRol.objects.create(persona=alumno, rol=self.rol_estudiante, organizacion=self.org, activo=True)
            AlumnoDisciplina.objects.create(disciplina=self.disciplina, alumno=alumno)
            self.alumnos.append(alumno)
        self.client.force_login(self.user)

    def _url_profesor(self, nombre, *args):
        return f"{reverse(nombre, args=args or None)}?organizacion={self.org.pk}"

    def _filas(self, cantidad, clave):
        return [
            {
                "persona_id": alumno.pk,
                "disciplina_id": self.disciplina.pk,
                "plan_id": self.plan.pk,
                "documento_tributario_id": None,
                "fecha_pago": timezone.localdate(),
                "metodo_pago": Payment.Metodo.EFECTIVO,
                "monto_referencia": Decimal("10000"),
                "aplica_iva": False,
                "clases_asignadas": 2,
                "observaciones": "Lote profesor",
                "clave_idempotencia": f"{clave}:{indice}:{alumno.pk}",
            }
            for indice, alumno in enumerate(self.alumnos[:cantidad])
        ]

    def test_lotes_10_15_20_crean_pagos_transacciones_y_actor_sin_huerfanos(self):
        for cantidad in (10, 15, 20):
            clave = f"profesor-lote-{cantidad}"
            lote, creado = confirmar_lote_pagos(
                usuario=self.user,
                organizacion_id=self.org.pk,
                clave_idempotencia=clave,
                filas=self._filas(cantidad, clave),
                metadatos={"origen": "profesor_masivo", "disciplina_id": self.disciplina.pk},
            )
            self.assertTrue(creado)
            pagos = Payment.objects.filter(lote=lote)
            self.assertEqual(pagos.count(), cantidad)
            self.assertEqual(Transaction.objects.filter(pago_operacional__lote=lote).count(), cantidad)
            self.assertFalse(pagos.filter(transaccion__isnull=True).exists())
            self.assertFalse(pagos.exclude(registrado_por=self.user).exists())

    def test_reintento_no_duplica_y_error_controlado_revierte_lote_completo(self):
        clave = "profesor-reintento"
        filas = self._filas(10, clave)
        lote, creado = confirmar_lote_pagos(
            usuario=self.user,
            organizacion_id=self.org.pk,
            clave_idempotencia=clave,
            filas=filas,
        )
        repetido, creado_repetido = confirmar_lote_pagos(
            usuario=self.user,
            organizacion_id=self.org.pk,
            clave_idempotencia=clave,
            filas=filas,
        )
        self.assertTrue(creado)
        self.assertFalse(creado_repetido)
        self.assertEqual(repetido.pk, lote.pk)
        self.assertEqual(Payment.objects.filter(lote=lote).count(), 10)

        from finanzas.services import pagos as pagos_service

        original = pagos_service.crear_pago_operacional
        llamadas = {"cantidad": 0}

        def fallar_en_quinta(*args, **kwargs):
            llamadas["cantidad"] += 1
            if llamadas["cantidad"] == 5:
                raise ValidationError("Fallo controlado de persistencia")
            return original(*args, **kwargs)

        with patch("finanzas.services.pagos.crear_pago_operacional", side_effect=fallar_en_quinta):
            with self.assertRaisesMessage(ValidationError, "Fallo controlado"):
                confirmar_lote_pagos(
                    usuario=self.user,
                    organizacion_id=self.org.pk,
                    clave_idempotencia="profesor-rollback",
                    filas=self._filas(10, "profesor-rollback"),
                )
        self.assertFalse(LotePago.objects.filter(clave_idempotencia="profesor-rollback").exists())
        self.assertFalse(Payment.objects.filter(clave_idempotencia__startswith="profesor-rollback:").exists())
        self.assertFalse(Transaction.objects.filter(pago_operacional__clave_idempotencia__startswith="profesor-rollback:").exists())

    def test_vista_previa_error_por_fila_confirmacion_y_resultado_verificado(self):
        seleccion = ",".join(str(alumno.pk) for alumno in self.alumnos[:10])
        payload = {
            "disciplina": self.disciplina.pk,
            "personas_seleccionadas": seleccion,
            "fecha_pago": timezone.localdate().isoformat(),
            "plan": self.plan.pk,
            "metodo_pago": Payment.Metodo.EFECTIVO,
            "numero_comprobante": "",
            "monto": "10000",
            "clases_asignadas": "2",
            "glosa": "Lote desde interfaz profesor",
            "filas_json": json.dumps({str(self.alumnos[3].pk): {"monto": "0"}}),
            "clave_idempotencia": "profesor-vista-lote",
            "accion": "preview",
        }
        invalido = self.client.post(self._url_profesor("profesor:pago_masivo"), payload)
        self.assertEqual(invalido.status_code, 200)
        self.assertContains(invalido, "El lote completo permanece sin confirmar")
        self.assertFalse(LotePago.objects.filter(clave_idempotencia="profesor-vista-lote").exists())

        payload["filas_json"] = "{}"
        preview = self.client.post(self._url_profesor("profesor:pago_masivo"), payload)
        self.assertEqual(preview.status_code, 200)
        self.assertContains(preview, "Vista previa del lote")
        payload["accion"] = "confirmar"
        confirmado = self.client.post(self._url_profesor("profesor:pago_masivo"), payload)
        lote = LotePago.objects.get(clave_idempotencia="profesor-vista-lote")
        self.assertRedirects(
            confirmado,
            self._url_profesor("profesor:pago_masivo_resultado", lote.pk),
        )
        resultado = self.client.get(
            self._url_profesor("profesor:pago_masivo_resultado", lote.pk)
        )
        self.assertEqual(resultado.status_code, 200)
        self.assertContains(resultado, "Lote confirmado íntegramente")
        self.assertTrue(resultado.context["resultado_integro"])

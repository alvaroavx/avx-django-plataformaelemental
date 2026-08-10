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

    def test_login_operativo_redirige_al_tablero_y_no_expone_admin_global(self):
        inicio = self.client.get(reverse("elemental_apps"))
        self.assertRedirects(inicio, reverse("profesor:inicio"))
        tablero = self.client.get(reverse("profesor:inicio"))
        self.assertEqual(tablero.status_code, 200)
        self.assertContains(tablero, "Tablero Elemental Operativo")
        self.assertContains(tablero, "Inicio")
        self.assertContains(tablero, "Mis clases")
        self.assertNotContains(tablero, "Pilates Ajeno")
        self.assertContains(tablero, "Sesión en curso o próxima")
        sesion_form = self.client.get(reverse("profesor:sesion_crear")).context["form"]
        pago_form = self.client.get(reverse("profesor:pago_crear")).context["form"]
        lote_form = self.client.get(reverse("profesor:pago_masivo")).context["form"]
        self.assertEqual(sesion_form.initial["fecha"], timezone.localdate())
        self.assertEqual(pago_form.initial["fecha_pago"], timezone.localdate())
        self.assertTrue(pago_form.initial["clave_idempotencia"])
        self.assertEqual(lote_form.initial["fecha_pago"], timezone.localdate())
        self.assertTrue(lote_form.initial["clave_idempotencia"])
        self.assertEqual(self.client.get(reverse("personas:organizaciones_list")).status_code, 403)
        self.assertEqual(self.client.get(reverse("finanzas:dashboard")).status_code, 403)
        self.assertEqual(self.client.get(reverse("asistencias:sesion_detail", args=[self.sesion_ajena.pk])).status_code, 404)

    def test_crea_y_libera_sesion_propia_con_motivo_y_auditoria(self):
        fecha = timezone.localdate() + timedelta(days=3)
        crear = self.client.post(
            reverse("profesor:sesion_crear"),
            {"disciplina": self.disciplina.pk, "fecha": fecha.isoformat()},
        )
        self.assertEqual(crear.status_code, 302)
        sesion = SesionClase.objects.get(fecha=fecha, disciplina=self.disciplina)
        self.assertEqual(list(sesion.profesores.all()), [self.profesor])
        sin_motivo = self.client.post(reverse("profesor:sesion_liberar", args=[sesion.pk]), {"motivo": ""})
        self.assertEqual(sin_motivo.status_code, 302)
        self.assertFalse(LiberacionSesion.objects.filter(sesion=sesion).exists())
        with self.captureOnCommitCallbacks(execute=True):
            liberar = self.client.post(
                reverse("profesor:sesion_liberar", args=[sesion.pk]),
                {"motivo": "Profesor con licencia"},
            )
        self.assertRedirects(liberar, reverse("profesor:sesiones"))
        sesion.refresh_from_db()
        self.assertEqual(sesion.estado, SesionClase.Estado.CANCELADA)
        self.assertTrue(
            AuditLog.objects.filter(resumen="Sesión liberada por profesor", organizacion=self.org).exists()
        )

    def test_alta_alumno_exige_telefono_o_email_y_asocia_solo_clase_propia(self):
        invalido = self.client.post(
            reverse("profesor:alumno_crear"),
            {"disciplina": self.disciplina.pk, "nombres": "Sin", "apellidos": "Contacto"},
        )
        self.assertEqual(invalido.status_code, 200)
        self.assertContains(invalido, "teléfono o un correo válido")
        self.assertFalse(Persona.objects.filter(nombres="Sin", apellidos="Contacto").exists())
        valido = self.client.post(
            reverse("profesor:alumno_crear"),
            {
                "disciplina": self.disciplina.pk,
                "nombres": "Nuevo",
                "apellidos": "Alumno",
                "email": "nuevo.alumno@example.com",
                "telefono": "",
            },
        )
        self.assertRedirects(valido, reverse("profesor:alumnos"))
        nuevo = Persona.objects.get(email="nuevo.alumno@example.com")
        self.assertTrue(AlumnoDisciplina.objects.filter(alumno=nuevo, disciplina=self.disciplina, activa=True).exists())
        ajeno = self.client.post(
            reverse("profesor:alumno_crear"),
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
            {"q": "Ana"},
        )
        ids = {item["id"] for item in buscar.json()["resultados"]}
        self.assertIn(self.alumno.pk, ids)
        self.assertNotIn(self.alumno_sin_clase.pk, ids)
        agregar = self.client.post(
            reverse("asistencias:sesion_asistente_agregar", args=[self.sesion.pk]),
            {"persona_id": self.alumno.pk},
        )
        self.assertEqual(agregar.status_code, 201)
        self.sesion.refresh_from_db()
        self.assertEqual(self.sesion.estado, SesionClase.Estado.ABIERTA)
        asistencia = Asistencia.objects.get(sesion=self.sesion, persona=self.alumno)
        with self.captureOnCommitCallbacks(execute=True):
            corregir = self.client.post(
                reverse("asistencias:sesion_asistencia_estado", args=[self.sesion.pk, asistencia.pk]),
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
            {"q": "angela nunez"},
        )
        pagos_masivos = self.client.get(
            reverse("profesor:pago_masivo_alumnos"),
            {"disciplina": self.disciplina.pk, "q": "angela nunez"},
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
        primero = self.client.post(reverse("profesor:pago_crear"), payload)
        self.assertEqual(primero.status_code, 302)
        segundo = self.client.post(reverse("profesor:pago_crear"), payload)
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
        invalido = self.client.post(reverse("profesor:pago_masivo"), payload)
        self.assertEqual(invalido.status_code, 200)
        self.assertContains(invalido, "El lote completo permanece sin confirmar")
        self.assertFalse(LotePago.objects.filter(clave_idempotencia="profesor-vista-lote").exists())

        payload["filas_json"] = "{}"
        preview = self.client.post(reverse("profesor:pago_masivo"), payload)
        self.assertEqual(preview.status_code, 200)
        self.assertContains(preview, "Vista previa del lote")
        payload["accion"] = "confirmar"
        confirmado = self.client.post(reverse("profesor:pago_masivo"), payload)
        lote = LotePago.objects.get(clave_idempotencia="profesor-vista-lote")
        self.assertRedirects(confirmado, reverse("profesor:pago_masivo_resultado", args=[lote.pk]))
        resultado = self.client.get(reverse("profesor:pago_masivo_resultado", args=[lote.pk]))
        self.assertEqual(resultado.status_code, 200)
        self.assertContains(resultado, "Lote confirmado íntegramente")
        self.assertTrue(resultado.context["resultado_integro"])

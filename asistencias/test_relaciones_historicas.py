import importlib
import io
from datetime import timedelta

from django.apps import apps
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.core.exceptions import PermissionDenied
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone

from auditoria.models import AuditLog
from finanzas.models import Payment
from personas.models import Organizacion, Persona, PersonaRol, Rol

from .admin import AsignacionProfesorDisciplinaAdmin
from .models import (
    AlumnoDisciplina,
    AsignacionProfesorDisciplina,
    Asistencia,
    Disciplina,
    SesionClase,
)
from .management.commands.reportar_relaciones_historicas import construir_reporte
from .services import (
    activar_asignacion_profesor,
    activar_asignaciones_profesor_en_lote,
    activar_matricula_alumno,
    activar_matriculas_alumno_en_lote,
)


class RelacionesHistoricasPermisosTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.organizacion = Organizacion.objects.create(
            nombre="Organización relaciones históricas",
            razon_social="Organización relaciones históricas",
            rut="77.333.333-3",
        )
        rol_admin = Rol.objects.create(nombre="Admin histórico", codigo="ADMIN")
        rol_profesor = Rol.objects.create(nombre="Profesor histórico", codigo="PROFESOR")
        rol_estudiante = Rol.objects.create(nombre="Estudiante histórico", codigo="ESTUDIANTE")

        self.admin_user = User.objects.create_user("admin.historico")
        admin = Persona.objects.create(nombres="Ada", apellidos="Admin", user=self.admin_user)
        PersonaRol.objects.create(
            persona=admin,
            rol=rol_admin,
            organizacion=self.organizacion,
            activo=True,
        )

        self.profesor_user = User.objects.create_user("profesor.historico")
        self.profesor = Persona.objects.create(
            nombres="Pablo",
            apellidos="Profesor",
            user=self.profesor_user,
        )
        PersonaRol.objects.create(
            persona=self.profesor,
            rol=rol_profesor,
            organizacion=self.organizacion,
            activo=True,
        )
        self.alumno = Persona.objects.create(
            nombres="Alba",
            apellidos="Alumna",
            email="alba.historica@example.com",
        )
        PersonaRol.objects.create(
            persona=self.alumno,
            rol=rol_estudiante,
            organizacion=self.organizacion,
            activo=True,
        )
        self.disciplina = Disciplina.objects.create(
            organizacion=self.organizacion,
            nombre="Disciplina histórica",
        )
        self.sesion = SesionClase.objects.create(
            disciplina=self.disciplina,
            fecha=timezone.localdate(),
        )
        self.sesion.profesores.add(self.profesor)
        self.asignacion = AsignacionProfesorDisciplina.objects.create(
            disciplina=self.disciplina,
            profesor=self.profesor,
            activa=False,
            origen=AsignacionProfesorDisciplina.Origen.HISTORICA,
        )
        self.matricula = AlumnoDisciplina.objects.create(
            disciplina=self.disciplina,
            alumno=self.alumno,
            activa=False,
            origen=AlumnoDisciplina.Origen.HISTORICA,
        )
        self.client.force_login(self.profesor_user)

    def _url_profesor(self, nombre, *args):
        return (
            f"{reverse(nombre, args=args or None)}"
            f"?organizacion={self.organizacion.pk}"
        )

    def test_asignacion_historica_inactiva_o_sin_revision_no_otorga_acceso(self):
        detalle = self._url_profesor("asistencias:sesion_detail", self.sesion.pk)
        self.assertEqual(self.client.get(detalle).status_code, 404)
        self.assertFalse(AsignacionProfesorDisciplina.objects.operativas().filter(pk=self.asignacion.pk).exists())

        self.asignacion.activa = True
        self.asignacion.save(update_fields=["activa"])

        self.assertEqual(self.client.get(detalle).status_code, 404)
        self.assertFalse(AsignacionProfesorDisciplina.objects.operativas().filter(pk=self.asignacion.pk).exists())

    def test_administrador_activa_relaciones_historicas_de_forma_explicita(self):
        with self.captureOnCommitCallbacks(execute=True):
            activar_asignacion_profesor(user=self.admin_user, asignacion=self.asignacion)
            activar_matricula_alumno(user=self.admin_user, matricula=self.matricula)

        self.asignacion.refresh_from_db()
        self.matricula.refresh_from_db()
        self.assertTrue(self.asignacion.activa)
        self.assertEqual(self.asignacion.revisada_por, self.admin_user)
        self.assertIsNotNone(self.asignacion.revisada_en)
        self.assertTrue(self.matricula.activa)
        self.assertEqual(self.matricula.revisada_por, self.admin_user)
        self.assertIsNotNone(self.matricula.revisada_en)
        self.assertTrue(AsignacionProfesorDisciplina.objects.operativas().filter(pk=self.asignacion.pk).exists())
        self.assertTrue(AlumnoDisciplina.objects.operativas().filter(pk=self.matricula.pk).exists())
        self.assertEqual(
            self.client.get(
                self._url_profesor("asistencias:sesion_detail", self.sesion.pk)
            ).status_code,
            200,
        )

    def test_activacion_masiva_es_explicita_y_auditable(self):
        otra_disciplina = Disciplina.objects.create(
            organizacion=self.organizacion,
            nombre="Otra disciplina histórica",
        )
        otra_asignacion = AsignacionProfesorDisciplina.objects.create(
            disciplina=otra_disciplina,
            profesor=self.profesor,
            activa=False,
            origen=AsignacionProfesorDisciplina.Origen.HISTORICA,
        )
        otra_matricula = AlumnoDisciplina.objects.create(
            disciplina=otra_disciplina,
            alumno=self.alumno,
            activa=False,
            origen=AlumnoDisciplina.Origen.HISTORICA,
        )
        with self.captureOnCommitCallbacks(execute=True):
            profesores = activar_asignaciones_profesor_en_lote(
                user=self.admin_user,
                relaciones=AsignacionProfesorDisciplina.objects.filter(
                    pk__in=[self.asignacion.pk, otra_asignacion.pk]
                ),
            )
            alumnos = activar_matriculas_alumno_en_lote(
                user=self.admin_user,
                relaciones=AlumnoDisciplina.objects.filter(
                    pk__in=[self.matricula.pk, otra_matricula.pk]
                ),
            )
        self.assertEqual(profesores, 2)
        self.assertEqual(alumnos, 2)
        self.assertEqual(
            AsignacionProfesorDisciplina.objects.operativas().filter(
                pk__in=[self.asignacion.pk, otra_asignacion.pk]
            ).count(),
            2,
        )
        self.assertEqual(
            AlumnoDisciplina.objects.operativas().filter(
                pk__in=[self.matricula.pk, otra_matricula.pk]
            ).count(),
            2,
        )
        self.assertEqual(
            AuditLog.objects.filter(
                usuario=self.admin_user,
                dominio="asistencias",
                accion=AuditLog.ACCION_CAMBIAR_ESTADO,
            ).count(),
            4,
        )

    def test_activacion_masiva_revierte_todo_si_incluye_otra_organizacion(self):
        otra_organizacion = Organizacion.objects.create(
            nombre="Organización fuera de alcance",
            razon_social="Organización fuera de alcance",
            rut="77.555.555-5",
        )
        otra_disciplina = Disciplina.objects.create(
            organizacion=otra_organizacion,
            nombre="Disciplina fuera de alcance",
        )
        otra_asignacion = AsignacionProfesorDisciplina.objects.create(
            disciplina=otra_disciplina,
            profesor=self.profesor,
            activa=False,
            origen=AsignacionProfesorDisciplina.Origen.HISTORICA,
        )
        with self.assertRaises(PermissionDenied):
            activar_asignaciones_profesor_en_lote(
                user=self.admin_user,
                relaciones=AsignacionProfesorDisciplina.objects.filter(
                    pk__in=[self.asignacion.pk, otra_asignacion.pk]
                ),
            )
        self.asignacion.refresh_from_db()
        otra_asignacion.refresh_from_db()
        self.assertFalse(self.asignacion.activa)
        self.assertFalse(otra_asignacion.activa)

    def test_desactivacion_administrativa_es_reversible_y_auditada(self):
        activar_asignacion_profesor(user=self.admin_user, asignacion=self.asignacion)
        self.asignacion.refresh_from_db()
        self.asignacion.activa = False
        request = RequestFactory().post("/admin/asistencias/asignacion/")
        request.user = self.admin_user
        administrador = AsignacionProfesorDisciplinaAdmin(
            AsignacionProfesorDisciplina,
            admin.site,
        )
        with self.captureOnCommitCallbacks(execute=True):
            administrador.save_model(request, self.asignacion, form=None, change=True)

        self.asignacion.refresh_from_db()
        self.assertFalse(self.asignacion.activa)
        self.assertFalse(
            AsignacionProfesorDisciplina.objects.operativas().filter(pk=self.asignacion.pk).exists()
        )
        self.assertTrue(
            AuditLog.objects.filter(
                usuario=self.admin_user,
                dominio="asistencias",
                resumen="Relación operativa desactivada administrativamente",
            ).exists()
        )

    def test_comando_activacion_tiene_preview_y_confirmacion_literal(self):
        salida = io.StringIO()
        call_command(
            "activar_relaciones_operativas",
            "--tipo=profesor",
            f"--ids={self.asignacion.pk}",
            f"--actor-username={self.admin_user.username}",
            stdout=salida,
        )
        self.asignacion.refresh_from_db()
        self.assertFalse(self.asignacion.activa)
        self.assertIn("PREVIEW", salida.getvalue())

        with self.captureOnCommitCallbacks(execute=True):
            call_command(
                "activar_relaciones_operativas",
                "--tipo=profesor",
                f"--ids={self.asignacion.pk}",
                f"--actor-username={self.admin_user.username}",
                "--confirmar=ACTIVAR_RELACIONES_REVISADAS",
                stdout=io.StringIO(),
            )
        self.asignacion.refresh_from_db()
        self.assertTrue(
            AsignacionProfesorDisciplina.objects.operativas().filter(pk=self.asignacion.pk).exists()
        )
        self.assertTrue(
            AuditLog.objects.filter(
                usuario=self.admin_user,
                dominio="asistencias",
                objeto_id=str(self.asignacion.pk),
            ).exists()
        )

    def test_matricula_historica_no_habilita_busqueda_ni_pago(self):
        activar_asignacion_profesor(user=self.admin_user, asignacion=self.asignacion)
        pagos_antes = Payment.objects.count()
        busqueda = self.client.get(
            reverse("asistencias:sesion_asistentes_buscar", args=[self.sesion.pk]),
            {"q": "Alba", "organizacion": self.organizacion.pk},
        )
        self.assertEqual(busqueda.status_code, 200)
        self.assertEqual(busqueda.json()["resultados"], [])

        respuesta = self.client.post(
            self._url_profesor("profesor:pago_crear"),
            {
                "disciplina": self.disciplina.pk,
                "persona": self.alumno.pk,
                "fecha_pago": timezone.localdate().isoformat(),
                "metodo_pago": Payment.Metodo.EFECTIVO,
                "monto": "10000",
                "clases_asignadas": "1",
                "glosa": "Pago no autorizado",
            },
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(Payment.objects.count(), pagos_antes)

        activar_matricula_alumno(user=self.admin_user, matricula=self.matricula)
        busqueda = self.client.get(
            reverse("asistencias:sesion_asistentes_buscar", args=[self.sesion.pk]),
            {"q": "Alba", "organizacion": self.organizacion.pk},
        )
        self.assertEqual([item["id"] for item in busqueda.json()["resultados"]], [self.alumno.pk])

    def test_profesor_no_puede_autoactivar_relacion_historica(self):
        with self.assertRaises(PermissionDenied):
            activar_asignacion_profesor(user=self.profesor_user, asignacion=self.asignacion)
        with self.assertRaises(PermissionDenied):
            activar_matricula_alumno(user=self.profesor_user, matricula=self.matricula)

    def test_guardar_asistencia_no_reactiva_matricula_historica(self):
        Asistencia.objects.create(sesion=self.sesion, persona=self.alumno)
        self.matricula.refresh_from_db()
        self.assertFalse(self.matricula.activa)
        self.assertEqual(self.matricula.origen, AlumnoDisciplina.Origen.HISTORICA)

    def test_reporte_falla_si_hay_historia_activa_sin_revision(self):
        self.asignacion.activa = True
        self.asignacion.save(update_fields=["activa"])
        with self.assertRaises(CommandError):
            call_command(
                "reportar_relaciones_historicas",
                "--fallar-si-inseguro",
                stdout=io.StringIO(),
            )

    def test_reporte_transicion_identifica_futuro_sin_autoactivar(self):
        Asistencia.objects.create(sesion=self.sesion, persona=self.alumno)
        sesion_antigua = SesionClase.objects.create(
            disciplina=self.disciplina,
            fecha=timezone.localdate() - timedelta(days=180),
        )
        profesor_antiguo = Persona.objects.create(nombres="Profesor", apellidos="Antiguo")
        sesion_antigua.profesores.add(profesor_antiguo)
        AsignacionProfesorDisciplina.objects.create(
            disciplina=self.disciplina,
            profesor=profesor_antiguo,
            activa=False,
            origen=AsignacionProfesorDisciplina.Origen.HISTORICA,
        )

        reporte = construir_reporte(
            fecha_corte=timezone.localdate(),
            incluir_detalle_operativo=True,
        )

        profesores = reporte["transicion_permisos"]["profesores"]
        alumnos = reporte["transicion_permisos"]["alumnos"]
        self.assertEqual(profesores["relaciones_que_requieren_activacion_administrativa"], 1)
        self.assertEqual(profesores["pares_que_requieren_revision_manual"], 0)
        self.assertEqual(alumnos["relaciones_no_operativas_con_asistencia_reciente_para_revision"], 1)
        self.assertTrue(reporte["contiene_datos_sensibles"])
        detalle = reporte["detalle_operativo_protegido"]
        self.assertEqual(detalle["profesores"][0]["profesor"], self.profesor.nombre_completo)
        self.assertNotIn(
            profesor_antiguo.nombre_completo,
            {item["profesor"] for item in detalle["profesores"]},
        )
        self.assertEqual(
            detalle["alumnos_para_revision_manual"][0]["clasificacion"],
            "revisar_y_activar_solo_si_sigue_vigente",
        )
        self.asignacion.refresh_from_db()
        self.matricula.refresh_from_db()
        self.assertFalse(self.asignacion.activa)
        self.assertFalse(self.matricula.activa)

    def test_pago_historico_permanece_sin_transaccion_ni_imputacion_inventada(self):
        pago = Payment.objects.create(
            organizacion=self.organizacion,
            persona=self.alumno,
            fecha_pago=timezone.localdate(),
            metodo_pago=Payment.Metodo.EFECTIVO,
            monto_referencia=10000,
        )
        pago.refresh_from_db()
        self.assertIsNone(pago.transaccion_id)
        self.assertIsNone(pago.disciplina_id)
        self.assertIsNone(pago.registrado_por_id)
        self.assertIsNone(pago.clave_idempotencia)
        self.assertFalse(pago.respaldo)


class BackfillRelacionesHistoricasTests(TestCase):
    def test_backfill_crea_relaciones_historicas_inactivas_y_reporte_sin_pii(self):
        organizacion = Organizacion.objects.create(
            nombre="Organización backfill",
            razon_social="Organización backfill",
            rut="77.444.444-4",
        )
        profesor = Persona.objects.create(nombres="NombreProfesorSecreto")
        alumno = Persona.objects.create(nombres="NombreAlumnoSecreto")
        disciplina = Disciplina.objects.create(organizacion=organizacion, nombre="Backfill")
        sesion = SesionClase.objects.create(disciplina=disciplina, fecha=timezone.localdate())
        sesion.profesores.add(profesor)
        Asistencia.objects.create(sesion=sesion, persona=alumno)
        AlumnoDisciplina.objects.all().delete()

        migracion = importlib.import_module(
            "asistencias.migrations.0004_alter_sesionclase_estado_liberacionsesion_and_more"
        )
        migracion.migrar_asignaciones_historicas(apps, None)

        asignacion = AsignacionProfesorDisciplina.objects.get(
            disciplina=disciplina,
            profesor=profesor,
        )
        matricula = AlumnoDisciplina.objects.get(disciplina=disciplina, alumno=alumno)
        self.assertFalse(asignacion.activa)
        self.assertEqual(asignacion.origen, AsignacionProfesorDisciplina.Origen.HISTORICA)
        self.assertFalse(matricula.activa)
        self.assertEqual(matricula.origen, AlumnoDisciplina.Origen.HISTORICA)

        salida = io.StringIO()
        call_command("reportar_relaciones_historicas", "--formato=json", stdout=salida)
        contenido = salida.getvalue()
        self.assertIn('"creadas_desde_historia": 1', contenido)
        self.assertNotIn("NombreProfesorSecreto", contenido)
        self.assertNotIn("NombreAlumnoSecreto", contenido)

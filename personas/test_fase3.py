"""Regresiones de seguridad y concurrencia para el cierre de Fase 3.

Estas pruebas se descubren con ``python manage.py test``. Las de concurrencia
usan PostgreSQL y conexiones independientes; no reemplazan los locks por
llamadas secuenciales.
"""

from threading import Event, Thread
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, connections, transaction
from django.test import Client, RequestFactory, TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.contrib.sessions.middleware import SessionMiddleware

from allauth.socialaccount.models import EmailAddress, SocialAccount, SocialLogin, SocialToken

from auditoria.models import AuditLog
from asistencias.models import Asistencia, Disciplina, SesionClase

from .models import Organizacion, Persona, PersonaRol, Rol, SolicitudAcceso
from .auth_google import AdaptadorSocialGoogleElemental
from .identidades_google import bloquear_identidad_google
from .resolucion_solicitudes import aprobar_solicitud, rechazar_solicitud, reabrir_solicitud
from .solicitudes_acceso import crear_o_recuperar_solicitud


TEST_PASSWORD = "not-a-real-test-password"


class _SesionDict(dict):
    modified = False


class _RequestSolicitud:
    def __init__(self):
        self.session = _SesionDict()


@override_settings(ACCESS_REQUESTS_ENABLED=True, ACCESS_REQUEST_APPROVAL_ENABLED=True)
class SolicitudesAccesoAdministracionTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.gestor = User.objects.create_user("gestor_fase3", password=TEST_PASSWORD)
        self.gestor.user_permissions.add(Permission.objects.get(codename="gestionar_solicitudes_acceso"))
        self.staff_sin_permiso = User.objects.create_user("staff_fase3", password=TEST_PASSWORD, is_staff=True)
        self.org_a = Organizacion.objects.create(nombre="Org A F3", razon_social="Org A F3 SpA", rut="61.001.001-1")
        self.org_b = Organizacion.objects.create(nombre="Org B F3", razon_social="Org B F3 SpA", rut="61.001.002-K")
        self.rol = Rol.objects.create(nombre="Rol F3", codigo="ROL_F3")
        self.solicitud = SolicitudAcceso.objects.create(provider="google", provider_subject="sub-fase3", email="fase3@example.test")

    def test_listado_filtra_paginas_y_no_expone_directorio_sin_busqueda(self):
        for numero in range(26):
            SolicitudAcceso.objects.create(
                provider="google",
                provider_subject=f"sub-listado-{numero}",
                email=f"listado-{numero}@example.test",
            )
        self.client.force_login(self.gestor)
        respuesta = self.client.get(reverse("personas:solicitudes_acceso_list"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Pendientes")
        self.assertEqual(len(respuesta.context["solicitudes"]), 25)
        respuesta = self.client.get(reverse("personas:solicitudes_acceso_list"), {"q": "listado-25"})
        self.assertContains(respuesta, "listado-25@example.test")

    def test_detalle_busca_de_forma_acotada_y_aprobacion_guarda_org_rol(self):
        User = get_user_model()
        usuario = User.objects.create_user("candidato_fase3", email="fase3@example.test", password=TEST_PASSWORD)
        persona = Persona.objects.create(nombres="Candidata", apellidos="Fase Tres", email="persona-fase3@example.test", user=usuario)
        self.client.force_login(self.gestor)
        url = reverse("personas:solicitud_acceso_detail", args=[self.solicitud.pk])
        sin_busqueda = self.client.get(url)
        self.assertNotContains(sin_busqueda, "candidato_fase3")
        con_busqueda = self.client.get(url, {"usuario_q": "candidato"})
        self.assertContains(con_busqueda, "candidato_fase3")
        aprobacion = self.client.post(
            reverse("personas:solicitud_acceso_aprobar", args=[self.solicitud.pk]),
            {
                "tipo_resolucion": SolicitudAcceso.TipoResolucion.USUARIO_EXISTENTE,
                "usuario": usuario.pk,
                "organizacion": self.org_a.pk,
                "rol": self.rol.pk,
                "confirmar_correo_distinto": "on",
                "nota_interna": "La diferencia fue revisada por el gestor.",
            },
        )
        self.assertEqual(aprobacion.status_code, 302)
        self.solicitud.refresh_from_db()
        self.assertEqual(self.solicitud.usuario_resuelto, usuario)
        self.assertEqual(self.solicitud.organizacion_resuelta, self.org_a)
        self.assertEqual(self.solicitud.rol_resuelto, self.rol)
        self.assertTrue(PersonaRol.objects.filter(persona=persona, rol=self.rol, organizacion=self.org_a, activo=True).exists())

    def test_reapertura_exige_nota_y_no_recrea_historial(self):
        rechazar_solicitud(solicitud_id=self.solicitud.pk, administrador=self.gestor, motivo_rechazo="Revisión incompleta")
        with self.assertRaises(ValidationError):
            reabrir_solicitud(solicitud_id=self.solicitud.pk, administrador=self.gestor, nota_interna="")
        reabrir_solicitud(solicitud_id=self.solicitud.pk, administrador=self.gestor, nota_interna="Nuevos antecedentes revisados")
        self.solicitud.refresh_from_db()
        self.assertEqual(self.solicitud.estado, SolicitudAcceso.Estado.PENDIENTE)

    def test_staff_y_post_manual_sin_permiso_no_modifican_solicitud(self):
        self.client.force_login(self.staff_sin_permiso)
        url = reverse("personas:solicitud_acceso_aprobar", args=[self.solicitud.pk])
        with self.captureOnCommitCallbacks(execute=True):
            respuesta = self.client.post(url, {"tipo_resolucion": SolicitudAcceso.TipoResolucion.USUARIO_NUEVO})
        self.assertEqual(respuesta.status_code, 403)
        self.solicitud.refresh_from_db()
        self.assertEqual(self.solicitud.estado, SolicitudAcceso.Estado.PENDIENTE)
        self.assertTrue(
            AuditLog.objects.filter(
                objeto_id=str(self.solicitud.pk),
                resumen="Acceso a gestión de solicitudes denegado",
            ).exists()
        )


class MatrizAislamientoOrganizacionalTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.org_a = Organizacion.objects.create(nombre="Aislamiento A", razon_social="Aislamiento A SpA", rut="62.001.001-1")
        self.org_b = Organizacion.objects.create(nombre="Aislamiento B", razon_social="Aislamiento B SpA", rut="62.001.002-K")
        self.rol_admin = Rol.objects.create(nombre="Administrador aislamiento", codigo="ADMINISTRADOR")
        self.rol_estudiante = Rol.objects.create(nombre="Estudiante aislamiento", codigo="ESTUDIANTE")
        self.admin_a = User.objects.create_user("admin_org_a", password=TEST_PASSWORD)
        self.persona_admin_a = Persona.objects.create(nombres="Admin", apellidos="A", email="admin-a@example.test", user=self.admin_a)
        PersonaRol.objects.create(persona=self.persona_admin_a, rol=self.rol_admin, organizacion=self.org_a, activo=True)
        self.persona_a = Persona.objects.create(nombres="Visible", apellidos="A", email="visible-a@example.test")
        self.persona_b = Persona.objects.create(nombres="Oculta", apellidos="B", email="oculta-b@example.test")
        PersonaRol.objects.create(persona=self.persona_a, rol=self.rol_estudiante, organizacion=self.org_a, activo=True)
        PersonaRol.objects.create(persona=self.persona_b, rol=self.rol_estudiante, organizacion=self.org_b, activo=True)
        self.disciplina_a = Disciplina.objects.create(organizacion=self.org_a, nombre="Disciplina A")
        self.disciplina_b = Disciplina.objects.create(organizacion=self.org_b, nombre="Disciplina B")
        self.sesion_b = SesionClase.objects.create(disciplina=self.disciplina_b, fecha="2026-07-20")
        self.sesion_a = SesionClase.objects.create(disciplina=self.disciplina_a, fecha="2026-07-20")
        self.client.force_login(self.admin_a)

    def _query_a(self):
        return {"organizacion": self.org_a.pk, "periodo_mes": "7", "periodo_anio": "2026"}

    def test_listado_y_busqueda_no_exponen_organizacion_b(self):
        respuesta = self.client.get(reverse("personas:personas_list"), self._query_a())
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Visible A")
        self.assertNotContains(respuesta, "Oculta B")
        respuesta_busqueda = self.client.get(reverse("personas:personas_list"), {**self._query_a(), "q": "Oculta"})
        self.assertNotContains(respuesta_busqueda, "Oculta B")

    def test_filtros_b_todas_y_pk_ajeno_no_amplian_acceso(self):
        self.assertEqual(self.client.get(reverse("personas:personas_list"), {"organizacion": self.org_b.pk}).status_code, 403)
        self.assertEqual(self.client.get(reverse("personas:personas_list"), {"organizacion": "Todas"}).status_code, 403)
        detalle = self.client.get(reverse("personas:persona_detail", args=[self.persona_b.pk]), self._query_a())
        self.assertEqual(detalle.status_code, 404)
        edicion = self.client.post(
            f"{reverse('personas:persona_edit', args=[self.persona_b.pk])}?organizacion={self.org_a.pk}&periodo_mes=7&periodo_anio=2026",
            {"accion": "guardar_persona"},
        )
        self.assertEqual(edicion.status_code, 404)

    def test_asistencias_y_json_no_filtran_existencia_ajena(self):
        detalle_disciplina = self.client.get(reverse("asistencias:disciplina_detail", args=[self.disciplina_b.pk]), self._query_a())
        self.assertEqual(detalle_disciplina.status_code, 403)
        detalle_sesion = self.client.get(reverse("asistencias:sesion_detail", args=[self.sesion_b.pk]), self._query_a())
        self.assertEqual(detalle_sesion.status_code, 404)
        json_busqueda = self.client.get(reverse("asistencias:sesion_asistentes_buscar", args=[self.sesion_b.pk]), {"q": "Oculta"})
        self.assertEqual(json_busqueda.status_code, 404)
        self.assertNotIn("Oculta", json_busqueda.content.decode())

    def test_persona_compartida_no_expone_ni_muta_roles_de_organizacion_b(self):
        rol_privado_a = Rol.objects.create(nombre="Rol visible A", codigo="ROL_VISIBLE_A")
        rol_privado_b = Rol.objects.create(nombre="Rol privado B", codigo="ROL_PRIVADO_B")
        compartida = Persona.objects.create(nombres="Compartida", apellidos="A y B", email="compartida@example.test")
        rol_a = PersonaRol.objects.create(persona=compartida, rol=rol_privado_a, organizacion=self.org_a, activo=True)
        rol_b = PersonaRol.objects.create(persona=compartida, rol=rol_privado_b, organizacion=self.org_b, activo=True)

        detalle = self.client.get(reverse("personas:persona_detail", args=[compartida.pk]), self._query_a())
        self.assertEqual(detalle.status_code, 200)
        self.assertEqual([asignacion.pk for asignacion in detalle.context["roles_asignados"]], [rol_a.pk])

        editar = self.client.get(reverse("personas:persona_edit", args=[compartida.pk]), self._query_a())
        self.assertEqual(editar.status_code, 200)
        self.assertEqual([asignacion.pk for asignacion in editar.context["roles_asignados"]], [rol_a.pk])
        respuesta = self.client.post(
            f"{reverse('personas:persona_detail', args=[compartida.pk])}?organizacion={self.org_a.pk}&periodo_mes=7&periodo_anio=2026",
            {"accion": "toggle_rol", "persona_rol_id": rol_b.pk},
        )
        self.assertEqual(respuesta.status_code, 404)
        rol_b.refresh_from_db()
        self.assertTrue(rol_b.activo)

    def test_exportacion_rechaza_b_y_todas_y_no_incluye_asistencia_b(self):
        Asistencia.objects.create(sesion=self.sesion_a, persona=self.persona_a, estado=Asistencia.Estado.PRESENTE, comentario="Visible exportación")
        Asistencia.objects.create(sesion=self.sesion_b, persona=self.persona_b, estado=Asistencia.Estado.PRESENTE, comentario="Privada exportación B")
        url = reverse("asistencias:export_asistencias_xlsx")
        self.assertEqual(self.client.get(url, {**self._query_a(), "organizacion": self.org_b.pk}).status_code, 403)
        self.assertEqual(self.client.get(url, {**self._query_a(), "organizacion": "Todas"}).status_code, 403)
        respuesta = self.client.get(url, self._query_a())
        self.assertEqual(respuesta.status_code, 200)
        self.assertNotIn("Privada exportación B", respuesta.content.decode("latin1"))

    @override_settings(ACCESS_REQUESTS_ENABLED=True, ACCESS_REQUEST_APPROVAL_ENABLED=True)
    def test_admin_organizacional_no_adquiere_permiso_global_de_solicitudes(self):
        solicitud = SolicitudAcceso.objects.create(provider="google", provider_subject="sub-matriz", email="matriz@example.test")
        respuesta = self.client.get(reverse("personas:solicitudes_acceso_list"))
        self.assertEqual(respuesta.status_code, 403)
        respuesta = self.client.post(reverse("personas:solicitud_acceso_rechazar", args=[solicitud.pk]), {"motivo_rechazo": "manual"})
        self.assertEqual(respuesta.status_code, 403)
        solicitud.refresh_from_db()
        self.assertEqual(solicitud.estado, SolicitudAcceso.Estado.PENDIENTE)


@override_settings(ACCESS_REQUESTS_ENABLED=True, ACCESS_REQUEST_APPROVAL_ENABLED=True)
class AuditoriaSolicitudesAccesoTests(TransactionTestCase):
    def setUp(self):
        User = get_user_model()
        self.gestor = User.objects.create_user("gestor_auditoria_f3", password=TEST_PASSWORD)
        self.gestor.user_permissions.add(Permission.objects.get(codename="gestionar_solicitudes_acceso"))
        self.sin_permiso = User.objects.create_user("sin_permiso_auditoria_f3", password=TEST_PASSWORD, is_staff=True)
        self.org = Organizacion.objects.create(nombre="Org auditoría F3", razon_social="Org auditoría F3 SpA", rut="64.001.001-1")
        self.rol = Rol.objects.create(nombre="Rol auditoría F3", codigo="ROL_AUDITORIA_F3")

    def test_eventos_relevantes_persisten_sin_pii_en_metadata(self):
        identidad = {"provider": "google", "provider_subject": "sub-auditoria-f3", "email": "auditoria-f3@example.test", "nombre": "Nombre temporal"}
        solicitud, creada = crear_o_recuperar_solicitud(_RequestSolicitud(), identidad)
        self.assertTrue(creada)
        crear_o_recuperar_solicitud(_RequestSolicitud(), identidad)
        aprobar_solicitud(
            solicitud_id=solicitud.pk,
            administrador=self.gestor,
            tipo_resolucion=SolicitudAcceso.TipoResolucion.USUARIO_NUEVO,
            organizacion=self.org,
            rol=self.rol,
            nombres="Auditada",
            apellidos="Acceso",
        )
        solicitud.refresh_from_db()
        with self.assertRaises(ValidationError):
            aprobar_solicitud(
                solicitud_id=solicitud.pk,
                administrador=self.gestor,
                tipo_resolucion=SolicitudAcceso.TipoResolucion.USUARIO_NUEVO,
                organizacion=self.org,
                rol=self.rol,
                nombres="Otra",
                apellidos="Persona",
            )
        resumentes = set(AuditLog.objects.filter(objeto_id=str(solicitud.pk)).values_list("resumen", flat=True))
        self.assertTrue({"Solicitud de acceso creada", "Solicitud de acceso pendiente recuperada", "Solicitud de acceso aprobada", "Usuario creado para resolución de acceso", "Persona creada para resolución de acceso", "Rol asignado durante resolución de acceso", "Resolución de solicitud revertida"}.issubset(resumentes))
        for metadata in AuditLog.objects.filter(objeto_id=str(solicitud.pk)).values_list("metadata", flat=True):
            contenido = str(metadata)
            self.assertNotIn("auditoria-f3@example.test", contenido)
            self.assertNotIn("sub-auditoria-f3", contenido)

    def test_rechazo_reapertura_conflicto_y_denegacion_quedan_auditados(self):
        solicitud = SolicitudAcceso.objects.create(provider="google", provider_subject="sub-auditoria-estados", email="estados@example.test")
        rechazar_solicitud(solicitud_id=solicitud.pk, administrador=self.gestor, motivo_rechazo="Interno")
        reabrir_solicitud(solicitud_id=solicitud.pk, administrador=self.gestor, nota_interna="Revisión nueva")
        usuario_externo = get_user_model().objects.create_user("externo_auditoria", password=TEST_PASSWORD)
        SocialAccount.objects.create(user=usuario_externo, provider="google", uid=solicitud.provider_subject, extra_data={})
        with self.assertRaises(ValidationError):
            aprobar_solicitud(
                solicitud_id=solicitud.pk,
                administrador=self.gestor,
                tipo_resolucion=SolicitudAcceso.TipoResolucion.USUARIO_NUEVO,
                organizacion=self.org,
                rol=self.rol,
                nombres="Conflicto",
                apellidos="Google",
            )
        with self.assertRaises(ValidationError):
            rechazar_solicitud(solicitud_id=solicitud.pk, administrador=self.sin_permiso, motivo_rechazo="Manual")
        resumentes = set(AuditLog.objects.filter(objeto_id=str(solicitud.pk)).values_list("resumen", flat=True))
        self.assertTrue({"Solicitud de acceso rechazada", "Solicitud de acceso reabierta", "Intento conflictivo de resolución Google", "Intento de gestión de solicitud sin permiso"}.issubset(resumentes))


@override_settings(GOOGLE_AUTH_ENABLED=True, ACCESS_REQUESTS_ENABLED=True, ACCESS_REQUEST_APPROVAL_ENABLED=True)
class FlujoGooglePosteriorAprobacionTests(TestCase):
    def test_siguiente_sociallogin_valido_vincula_por_sub_sin_creacion_administrativa(self):
        User = get_user_model()
        gestor = User.objects.create_user("gestor_flujo_google", password=TEST_PASSWORD)
        gestor.user_permissions.add(Permission.objects.get(codename="gestionar_solicitudes_acceso"))
        organizacion = Organizacion.objects.create(nombre="Org flujo Google", razon_social="Org flujo Google SpA", rut="65.001.001-1")
        rol = Rol.objects.create(nombre="Rol flujo Google", codigo="ROL_FLUJO_GOOGLE")
        solicitud = SolicitudAcceso.objects.create(provider="google", provider_subject="sub-flujo-google", email="flujo-google@example.test")
        aprobar_solicitud(
            solicitud_id=solicitud.pk,
            administrador=gestor,
            tipo_resolucion=SolicitudAcceso.TipoResolucion.USUARIO_NUEVO,
            organizacion=organizacion,
            rol=rol,
            nombres="Flujo",
            apellidos="Google",
        )
        solicitud.refresh_from_db()
        self.assertEqual(SocialAccount.objects.count(), 0)
        request = self.client.get("/cuenta-interna-de-prueba/").wsgi_request
        request.session.save()
        social_login = SocialLogin(
            user=User(username="temporal-flujo", email=solicitud.email),
            account=SocialAccount(provider="google", uid=solicitud.provider_subject, extra_data={"email": solicitud.email, "token": "no-persistir"}),
            email_addresses=[EmailAddress(email=solicitud.email, verified=True, primary=True)],
        )
        with patch.object(SocialAccount, "get_provider"):
            AdaptadorSocialGoogleElemental().pre_social_login(request, social_login)
        cuenta = SocialAccount.objects.get(provider="google", uid=solicitud.provider_subject)
        self.assertEqual(cuenta.user, solicitud.usuario_resuelto)
        self.assertEqual(cuenta.extra_data, {})
        self.assertFalse(SocialToken.objects.exists())
        self.assertTrue(PersonaRol.objects.filter(persona__user=cuenta.user, organizacion=organizacion, rol=rol, activo=True).exists())


@override_settings(ACCESS_REQUESTS_ENABLED=True, ACCESS_REQUEST_APPROVAL_ENABLED=True)
class ConcurrenciaSolicitudesPostgreSQLTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        if connection.vendor != "postgresql":
            self.fail("Las pruebas de concurrencia requieren PostgreSQL real.")
        User = get_user_model()
        self.gestor = User.objects.create_user("gestor_concurrencia", password=TEST_PASSWORD)
        self.gestor.user_permissions.add(Permission.objects.get(codename="gestionar_solicitudes_acceso"))
        self.org = Organizacion.objects.create(nombre="Org concurrencia", razon_social="Org concurrencia SpA", rut="63.001.001-1")
        self.rol = Rol.objects.create(nombre="Rol concurrencia", codigo="ROL_CONCURRENCIA")

    def tearDown(self):
        connections.close_all()
        super().tearDown()

    def _aprobar_nuevo(self, solicitud_id):
        admin = get_user_model().objects.get(pk=self.gestor.pk)
        return aprobar_solicitud(
            solicitud_id=solicitud_id,
            administrador=admin,
            tipo_resolucion=SolicitudAcceso.TipoResolucion.USUARIO_NUEVO,
            organizacion=Organizacion.objects.get(pk=self.org.pk),
            rol=Rol.objects.get(pk=self.rol.pk),
            nombres="Nueva",
            apellidos="Concurrencia",
        )

    def _correr_con_bloqueo(self, solicitud, operacion_a, operacion_b):
        bloqueo_tomado = Event()
        operacion_b_iniciada = Event()
        resultados = []

        def primero():
            connections.close_all()
            try:
                with transaction.atomic():
                    SolicitudAcceso.objects.select_for_update().get(pk=solicitud.pk)
                    bloqueo_tomado.set()
                    self.assertTrue(operacion_b_iniciada.wait(10))
                    resultados.append(("a", "ok", operacion_a()))
            except Exception as error:  # la aserción se realiza en el hilo principal
                resultados.append(("a", "error", error))
            finally:
                connections.close_all()

        def segundo():
            connections.close_all()
            try:
                self.assertTrue(bloqueo_tomado.wait(10))
                operacion_b_iniciada.set()
                resultados.append(("b", "ok", operacion_b()))
            except Exception as error:
                resultados.append(("b", "error", error))
            finally:
                connections.close_all()

        hilo_a = Thread(target=primero)
        hilo_b = Thread(target=segundo)
        hilo_a.start()
        hilo_b.start()
        hilo_a.join(15)
        hilo_b.join(15)
        self.assertFalse(hilo_a.is_alive(), "La primera transacción no terminó.")
        self.assertFalse(hilo_b.is_alive(), "La segunda transacción no terminó.")
        return resultados

    def test_dos_aprobaciones_simultaneas_dejan_un_estado_y_una_identidad(self):
        solicitud = SolicitudAcceso.objects.create(provider="google", provider_subject="sub-concurrente", email="concurrente@example.test")
        resultados = self._correr_con_bloqueo(solicitud, lambda: self._aprobar_nuevo(solicitud.pk), lambda: self._aprobar_nuevo(solicitud.pk))
        solicitud.refresh_from_db()
        self.assertEqual(solicitud.estado, SolicitudAcceso.Estado.APROBADA)
        self.assertEqual(sum(1 for _, estado, _ in resultados if estado == "ok"), 1)
        self.assertEqual(get_user_model().objects.filter(email="concurrente@example.test").count(), 1)
        self.assertEqual(PersonaRol.objects.filter(organizacion=self.org, rol=self.rol).count(), 1)

    def test_aprobacion_y_rechazo_simultaneos_son_consistentes(self):
        solicitud = SolicitudAcceso.objects.create(provider="google", provider_subject="sub-aprueba-rechaza", email="aprueba-rechaza@example.test")
        resultados = self._correr_con_bloqueo(
            solicitud,
            lambda: self._aprobar_nuevo(solicitud.pk),
            lambda: rechazar_solicitud(solicitud_id=solicitud.pk, administrador=get_user_model().objects.get(pk=self.gestor.pk), motivo_rechazo="competencia"),
        )
        solicitud.refresh_from_db()
        self.assertIn(solicitud.estado, {SolicitudAcceso.Estado.APROBADA, SolicitudAcceso.Estado.RECHAZADA})
        self.assertEqual(sum(1 for _, estado, _ in resultados if estado == "ok"), 1)

    def test_dos_creaciones_simultaneas_recuperan_una_solicitud_pendiente(self):
        inicio = Event()
        resultados = []
        identidad = {"provider": "google", "provider_subject": "sub-crear-concurrente", "email": "crear-concurrente@example.test", "nombre": ""}

        def crear():
            connections.close_all()
            try:
                self.assertTrue(inicio.wait(10))
                solicitud, creada = crear_o_recuperar_solicitud(_RequestSolicitud(), identidad)
                resultados.append((solicitud.pk, creada))
            finally:
                connections.close_all()

        hilos = [Thread(target=crear), Thread(target=crear)]
        for hilo in hilos:
            hilo.start()
        inicio.set()
        for hilo in hilos:
            hilo.join(15)
            self.assertFalse(hilo.is_alive(), "La creación concurrente no terminó.")
        self.assertEqual(SolicitudAcceso.objects.filter(provider_subject=identidad["provider_subject"], estado=SolicitudAcceso.Estado.PENDIENTE).count(), 1)
        self.assertEqual(len({pk for pk, _ in resultados}), 1)

    def test_dos_resoluciones_hacia_misma_persona_crean_un_solo_user(self):
        persona = Persona.objects.create(nombres="Persona", apellidos="Compartida", email="persona-compartida@example.test")
        primera = SolicitudAcceso.objects.create(provider="google", provider_subject="sub-persona-uno", email="uno-persona@example.test")
        segunda = SolicitudAcceso.objects.create(provider="google", provider_subject="sub-persona-dos", email="dos-persona@example.test")

        def resolver(solicitud):
            admin = get_user_model().objects.get(pk=self.gestor.pk)
            return aprobar_solicitud(solicitud_id=solicitud.pk, administrador=admin, tipo_resolucion=SolicitudAcceso.TipoResolucion.PERSONA_EXISTENTE, persona=Persona.objects.get(pk=persona.pk), organizacion=Organizacion.objects.get(pk=self.org.pk), rol=Rol.objects.get(pk=self.rol.pk))

        resultados = self._correr_con_bloqueo(primera, lambda: resolver(primera), lambda: resolver(segunda))
        persona.refresh_from_db()
        primera.refresh_from_db()
        segunda.refresh_from_db()
        self.assertIsNotNone(persona.user_id)
        self.assertEqual(sum(1 for solicitud in (primera, segunda) if solicitud.estado == SolicitudAcceso.Estado.APROBADA), 1)
        self.assertEqual(sum(1 for _, estado, _ in resultados if estado == "ok"), 1)

    def test_reapertura_y_rechazo_simultaneos_terminan_en_un_estado_valido(self):
        solicitud = SolicitudAcceso.objects.create(
            provider="google", provider_subject="sub-reabre-rechaza", email="reabre-rechaza@example.test", estado=SolicitudAcceso.Estado.RECHAZADA
        )
        resultados = self._correr_con_bloqueo(
            solicitud,
            lambda: reabrir_solicitud(solicitud_id=solicitud.pk, administrador=get_user_model().objects.get(pk=self.gestor.pk), nota_interna="Revisión concurrente"),
            lambda: rechazar_solicitud(solicitud_id=solicitud.pk, administrador=get_user_model().objects.get(pk=self.gestor.pk), motivo_rechazo="Nueva decisión"),
        )
        solicitud.refresh_from_db()
        self.assertEqual(solicitud.estado, SolicitudAcceso.Estado.RECHAZADA)
        self.assertEqual(sum(1 for _, estado, _ in resultados if estado == "ok"), 2)

    def test_reapertura_y_aprobacion_simultaneas_no_dejan_estado_intermedio(self):
        solicitud = SolicitudAcceso.objects.create(
            provider="google", provider_subject="sub-reabre-aprueba", email="reabre-aprueba@example.test", estado=SolicitudAcceso.Estado.RECHAZADA
        )
        resultados = self._correr_con_bloqueo(
            solicitud,
            lambda: reabrir_solicitud(solicitud_id=solicitud.pk, administrador=get_user_model().objects.get(pk=self.gestor.pk), nota_interna="Revisión concurrente"),
            lambda: self._aprobar_nuevo(solicitud.pk),
        )
        solicitud.refresh_from_db()
        self.assertIn(solicitud.estado, {SolicitudAcceso.Estado.PENDIENTE, SolicitudAcceso.Estado.APROBADA})
        self.assertGreaterEqual(sum(1 for _, estado, _ in resultados if estado == "ok"), 1)
        self.assertLessEqual(PersonaRol.objects.filter(organizacion=self.org, rol=self.rol).count(), 1)

    def test_dos_resoluciones_hacia_mismo_user_bloquean_segundo_google_sub(self):
        User = get_user_model()
        usuario = User.objects.create_user("usuario_compartido", email="usuario-compartido@example.test", password=TEST_PASSWORD)
        Persona.objects.create(nombres="Usuario", apellidos="Compartido", email="persona-compartida-user@example.test", user=usuario)
        primera = SolicitudAcceso.objects.create(provider="google", provider_subject="sub-user-uno", email="usuario-compartido@example.test")
        segunda = SolicitudAcceso.objects.create(provider="google", provider_subject="sub-user-dos", email="otro-user-compartido@example.test")

        def resolver(solicitud, confirmar=False):
            return aprobar_solicitud(
                solicitud_id=solicitud.pk,
                administrador=User.objects.get(pk=self.gestor.pk),
                tipo_resolucion=SolicitudAcceso.TipoResolucion.USUARIO_EXISTENTE,
                usuario=User.objects.get(pk=usuario.pk),
                organizacion=Organizacion.objects.get(pk=self.org.pk),
                rol=Rol.objects.get(pk=self.rol.pk),
                confirmar_correo_distinto=confirmar,
                nota_interna="Excepción revisada" if confirmar else "",
            )

        resultados = self._correr_con_bloqueo(primera, lambda: resolver(primera), lambda: resolver(segunda, confirmar=True))
        primera.refresh_from_db()
        segunda.refresh_from_db()
        self.assertEqual(sum(1 for solicitud in (primera, segunda) if solicitud.estado == SolicitudAcceso.Estado.APROBADA), 1)
        self.assertEqual(sum(1 for _, estado, _ in resultados if estado == "ok"), 1)

    def test_conflicto_social_insertado_por_flujo_externo_se_detecta_antes_de_aprobar(self):
        solicitud = SolicitudAcceso.objects.create(provider="google", provider_subject="sub-social-carrera", email="social-carrera@example.test")
        usuario_externo = get_user_model().objects.create_user("social_externo", password=TEST_PASSWORD)
        bloqueo_tomado = Event()
        social_creado = Event()
        resultados = []

        def resolver():
            connections.close_all()
            try:
                with transaction.atomic():
                    SolicitudAcceso.objects.select_for_update().get(pk=solicitud.pk)
                    bloqueo_tomado.set()
                    self.assertTrue(social_creado.wait(10))
                    self._aprobar_nuevo(solicitud.pk)
                    resultados.append("ok")
            except Exception as error:
                resultados.append(error)
            finally:
                connections.close_all()

        def vinculo_externo():
            connections.close_all()
            try:
                self.assertTrue(bloqueo_tomado.wait(10))
                SocialAccount.objects.create(user=get_user_model().objects.get(pk=usuario_externo.pk), provider="google", uid="sub-social-carrera", extra_data={})
                social_creado.set()
            finally:
                connections.close_all()

        hilo_a = Thread(target=resolver)
        hilo_b = Thread(target=vinculo_externo)
        hilo_a.start(); hilo_b.start(); hilo_a.join(15); hilo_b.join(15)
        self.assertFalse(hilo_a.is_alive())
        self.assertFalse(hilo_b.is_alive())
        solicitud.refresh_from_db()
        self.assertEqual(solicitud.estado, SolicitudAcceso.Estado.PENDIENTE)
        self.assertEqual(len(resultados), 1)
        self.assertIsInstance(resultados[0], ValidationError)

    def test_bloqueo_advisory_serializa_decision_y_sociallogin_por_mismo_sub(self):
        """Una cuenta sin fila SocialAccount también queda excluida de carreras."""
        solicitud = SolicitudAcceso.objects.create(provider="google", provider_subject="sub-advisory", email="advisory@example.test")
        bloqueo_tomado = Event()
        segundo_intento = Event()
        segundo_adquirio = Event()
        errores = []

        def resolver():
            connections.close_all()
            try:
                with transaction.atomic():
                    SolicitudAcceso.objects.select_for_update().get(pk=solicitud.pk)
                    bloquear_identidad_google(provider="google", subject="sub-advisory")
                    bloqueo_tomado.set()
                    self.assertTrue(segundo_intento.wait(10))
                    # El segundo flujo no puede atravesar el advisory lock
                    # mientras esta transacción decide la aprobación.
                    self.assertFalse(segundo_adquirio.wait(0.1))
                    self._aprobar_nuevo(solicitud.pk)
            except Exception as error:
                errores.append(error)
            finally:
                connections.close_all()

        def siguiente_sociallogin():
            connections.close_all()
            try:
                self.assertTrue(bloqueo_tomado.wait(10))
                segundo_intento.set()
                with transaction.atomic():
                    bloquear_identidad_google(provider="google", subject="sub-advisory")
                    segundo_adquirio.set()
                    aprobada = SolicitudAcceso.objects.get(pk=solicitud.pk)
                    SocialAccount.objects.create(
                        user=aprobada.usuario_resuelto,
                        provider="google",
                        uid="sub-advisory",
                        extra_data={},
                    )
            except Exception as error:
                errores.append(error)
            finally:
                connections.close_all()

        primero = Thread(target=resolver)
        segundo = Thread(target=siguiente_sociallogin)
        primero.start(); segundo.start(); primero.join(15); segundo.join(15)
        self.assertFalse(primero.is_alive())
        self.assertFalse(segundo.is_alive())
        self.assertEqual(errores, [])
        solicitud.refresh_from_db()
        self.assertEqual(solicitud.estado, SolicitudAcceso.Estado.APROBADA)
        self.assertEqual(SocialAccount.objects.filter(provider="google", uid="sub-advisory", user=solicitud.usuario_resuelto).count(), 1)

    @override_settings(GOOGLE_AUTH_ENABLED=True, ACCESS_REQUESTS_ENABLED=True)
    def test_dos_callbacks_reales_con_subs_distintos_no_conectan_mismo_user(self):
        """El callback posterior al primero se revisa, no añade otro sub al User."""
        User = get_user_model()
        usuario = User.objects.create_user("usuario_callbacks", email="callbacks@example.test", password=TEST_PASSWORD)
        primero_listo_para_conectar = Event()
        segundo_iniciado = Event()
        resultados = []
        fabrica = RequestFactory()

        def request_con_sesion():
            request = fabrica.get("/accounts/google/login/callback/")
            SessionMiddleware(lambda request: None).process_request(request)
            request.session.save()
            return request

        def callback(subject, es_primero):
            connections.close_all()
            try:
                if not es_primero:
                    self.assertTrue(primero_listo_para_conectar.wait(10))
                    segundo_iniciado.set()
                social_login = SocialLogin(
                    user=User(username=f"temporal-{subject}", email=usuario.email),
                    account=SocialAccount(provider="google", uid=subject, extra_data={}),
                    email_addresses=[EmailAddress(email=usuario.email, verified=True, primary=True)],
                )
                AdaptadorSocialGoogleElemental().pre_social_login(request_con_sesion(), social_login)
                resultados.append((subject, "conectado"))
            except Exception as error:
                resultados.append((subject, type(error).__name__))
            finally:
                connections.close_all()

        original_connect = SocialLogin.connect

        def conectar_controlado(social_login, request, user):
            if social_login.account.uid == "sub-callback-uno":
                primero_listo_para_conectar.set()
                self.assertTrue(segundo_iniciado.wait(10))
            return original_connect(social_login, request, user)

        with patch.object(SocialAccount, "get_provider"), patch.object(SocialLogin, "connect", new=conectar_controlado):
            primero = Thread(target=callback, args=("sub-callback-uno", True))
            segundo = Thread(target=callback, args=("sub-callback-dos", False))
            primero.start(); segundo.start(); primero.join(15); segundo.join(15)
        self.assertFalse(primero.is_alive())
        self.assertFalse(segundo.is_alive())
        self.assertEqual(SocialAccount.objects.filter(user=usuario, provider="google").count(), 1)
        self.assertEqual(dict(resultados)["sub-callback-uno"], "conectado")
        self.assertNotEqual(dict(resultados)["sub-callback-dos"], "conectado")

    def test_fallo_despues_de_locks_revierte_y_audita_una_vez(self):
        solicitud = SolicitudAcceso.objects.create(provider="google", provider_subject="sub-rollback-lock", email="rollback-lock@example.test")
        with patch("personas.resolucion_solicitudes.PersonaRol.objects.get_or_create", side_effect=RuntimeError("falla controlada")):
            with self.assertRaises(RuntimeError):
                self._aprobar_nuevo(solicitud.pk)
        solicitud.refresh_from_db()
        self.assertEqual(solicitud.estado, SolicitudAcceso.Estado.PENDIENTE)
        self.assertFalse(get_user_model().objects.filter(email="rollback-lock@example.test").exists())
        self.assertEqual(AuditLog.objects.filter(objeto_id=str(solicitud.pk), resumen="Resolución de solicitud revertida").count(), 1)

    def test_repeticion_posterior_no_duplica_registros(self):
        solicitud = SolicitudAcceso.objects.create(provider="google", provider_subject="sub-reintento", email="reintento@example.test")
        self._aprobar_nuevo(solicitud.pk)
        with self.assertRaises(ValidationError):
            self._aprobar_nuevo(solicitud.pk)
        self.assertEqual(get_user_model().objects.filter(email="reintento@example.test").count(), 1)
        self.assertEqual(PersonaRol.objects.filter(organizacion=self.org, rol=self.rol).count(), 1)

from io import StringIO
from datetime import timedelta
from time import time
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import connection
from django.http import HttpResponse
from django.test import Client, TestCase
from django.test.utils import CaptureQueriesContext, override_settings
from django.urls import reverse
from django.utils import timezone

from allauth.core.exceptions import ImmediateHttpResponse
from allauth.core.context import request_context
from allauth.socialaccount.models import EmailAddress, SocialAccount, SocialLogin, SocialToken
from allauth.socialaccount.providers.google.views import GoogleOAuth2Adapter

from auditoria.models import AuditLog
from asistencias.forms import PersonaRapidaForm
from asistencias.models import Asistencia, Disciplina, SesionClase
from finanzas.models import AttendanceConsumption, Payment

from .admin import PersonaRolBulkForm
from .auth_google import AdaptadorSocialGoogleElemental
from .auth_views import GoogleOAuth2AdapterElemental
from .forms import PersonaCRMForm
from .models import Organizacion, Persona, PersonaRol, Rol, SolicitudAcceso
from .solicitudes_acceso import SESION_IDENTIDAD_PENDIENTE
from .resolucion_solicitudes import aprobar_solicitud, rechazar_solicitud


TEST_PASSWORD = "not-a-real-test-password"


class PersonaRolBulkFormTests(TestCase):
    def setUp(self):
        self.organizacion = Organizacion.objects.create(
            nombre="Org Bulk",
            razon_social="Org Bulk SPA",
            rut="44.444.444-4",
        )
        self.rol = Rol.objects.create(nombre="Estudiante", codigo="ESTUDIANTE")
        self.persona = Persona.objects.create(
            nombres="Ana",
            apellidos="Bulk",
            email="ana.bulk@example.com",
        )

    def test_persona_rol_bulk_form_sin_organizacion_falla(self):
        form = PersonaRolBulkForm(
            data={
                "personas": [self.persona.pk],
                "rol": self.rol.pk,
                "activo": "on",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("organizacion", form.errors)

    def test_persona_rol_bulk_form_con_organizacion_valida_pasa(self):
        form = PersonaRolBulkForm(
            data={
                "personas": [self.persona.pk],
                "rol": self.rol.pk,
                "organizacion": self.organizacion.pk,
                "activo": "on",
            }
        )

        self.assertTrue(form.is_valid(), form.errors)


class AuditarIdentidadesAccesoCommandTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.organizacion = Organizacion.objects.create(
            nombre="Org Auditoria Identidades",
            razon_social="Org Auditoria Identidades SPA",
            rut="11.111.111-1",
        )
        self.rol = Rol.objects.create(nombre="Lectura Auditoria", codigo="LECTURA")
        self.usuario_sin_email = User.objects.create_user("sin_email", password=TEST_PASSWORD)
        self.usuario_duplicado_a = User.objects.create_user(
            "duplicado_a",
            email="Duplicado@example.com",
            password=TEST_PASSWORD,
        )
        self.usuario_duplicado_b = User.objects.create_user(
            "duplicado_b",
            email=" duplicado@example.com ",
            password=TEST_PASSWORD,
        )
        self.usuario_distinto = User.objects.create_user(
            "correo_distinto",
            email="user@example.com",
            password=TEST_PASSWORD,
            is_active=False,
        )
        self.superusuario = User.objects.create_superuser(
            "super_auditoria",
            "super@example.com",
            TEST_PASSWORD,
        )
        self.persona_distinta = Persona.objects.create(
            nombres="Correo",
            apellidos="Distinto",
            email="persona@example.com",
            user=self.usuario_distinto,
        )
        self.persona_sin_usuario = Persona.objects.create(
            nombres="Sin",
            apellidos="Usuario",
            email="sin.usuario@example.com",
        )
        PersonaRol.objects.create(
            persona=self.persona_distinta,
            rol=self.rol,
            organizacion=self.organizacion,
            activo=True,
        )

    def test_auditoria_identidades_es_read_only_y_no_expone_correos_completos(self):
        salida = StringIO()
        usuarios_antes = get_user_model().objects.count()
        personas_antes = Persona.objects.count()
        roles_antes = PersonaRol.objects.count()

        call_command("auditar_identidades_acceso", stdout=salida)

        contenido = salida.getvalue()
        self.assertIn("Users sin email: 1", contenido)
        self.assertIn("Emails User duplicados (trim/lower): 1 grupos", contenido)
        self.assertIn("User.email distinto de Persona.email: 1", contenido)
        self.assertIn("Users sin Persona:", contenido)
        self.assertIn("Personas sin User: 1", contenido)
        self.assertIn("Usuarios inactivos: 1", contenido)
        self.assertIn("Superusuarios: 1", contenido)
        self.assertIn(f"User {self.usuario_distinto.id}: rol={self.rol.id}/org={self.organizacion.id}", contenido)
        self.assertNotIn("Duplicado@example.com", contenido)
        self.assertNotIn("persona@example.com", contenido)
        self.assertEqual(get_user_model().objects.count(), usuarios_antes)
        self.assertEqual(Persona.objects.count(), personas_antes)
        self.assertEqual(PersonaRol.objects.count(), roles_antes)


class AutenticacionGoogleFaseUnoTests(TestCase):
    def setUp(self):
        self.usuario = get_user_model().objects.create_user(
            "usuario_google",
            email="acceso@example.com",
            password=TEST_PASSWORD,
        )
        self.adaptador = AdaptadorSocialGoogleElemental()

    def _solicitud(self):
        solicitud = self.client.post("/cuenta-interna-de-prueba/").wsgi_request
        solicitud.session.save()
        return solicitud

    def _social_login(self, *, email="acceso@example.com", verificado=True, subject="google-sub-1"):
        cuenta = SocialAccount(
            provider="google",
            uid=subject,
            extra_data={"email": email, "token": "no-persistir"},
        )
        candidato = get_user_model()(username="temporal_google", email=email)
        return SocialLogin(
            user=candidato,
            account=cuenta,
            email_addresses=[EmailAddress(email=email, verified=verificado, primary=True)],
        )

    @override_settings(GOOGLE_AUTH_ENABLED=True)
    def test_vincula_solo_un_user_activo_con_correo_verificado(self):
        solicitud = self._solicitud()
        social_login = self._social_login()

        with patch.object(SocialLogin, "connect", autospec=True) as conectar:
            self.adaptador.pre_social_login(solicitud, social_login)

        conectar.assert_called_once_with(social_login, solicitud, self.usuario)
        self.assertEqual(social_login.account.extra_data, {})

    @override_settings(GOOGLE_AUTH_ENABLED=True)
    @patch.object(SocialAccount, "get_provider")
    def test_primer_vinculo_persiste_solo_la_identidad_social_sin_token(self, _get_provider):
        solicitud = self._solicitud()
        social_login = self._social_login()

        self.adaptador.pre_social_login(solicitud, social_login)

        cuenta = SocialAccount.objects.get(provider="google", uid="google-sub-1")
        self.assertEqual(cuenta.user, self.usuario)
        self.assertEqual(cuenta.extra_data, {})
        self.assertFalse(SocialToken.objects.exists())

    @override_settings(GOOGLE_AUTH_ENABLED=True)
    def test_identidad_social_existente_conserva_el_mismo_user_activo(self):
        cuenta = SocialAccount.objects.create(
            user=self.usuario,
            provider="google",
            uid="google-sub-existente",
            extra_data={"dato": "temporal"},
        )
        social_login = SocialLogin(user=self.usuario, account=cuenta)

        self.adaptador.pre_social_login(self._solicitud(), social_login)

        cuenta.refresh_from_db()
        self.assertEqual(social_login.user, self.usuario)
        self.assertEqual(cuenta.extra_data, {})

    @override_settings(GOOGLE_AUTH_ENABLED=True)
    def test_google_vinculado_no_otorga_acceso_funcional_a_profesora(self):
        organizacion = Organizacion.objects.create(
            nombre="Org profesora Google",
            razon_social="Org profesora Google SpA",
            rut="91.111.111-1",
        )
        rol_profesor = Rol.objects.create(nombre="Profesora Google", codigo="PROFESOR")
        persona = Persona.objects.create(
            nombres="Profesora",
            apellidos="Google",
            email=self.usuario.email,
            user=self.usuario,
        )
        PersonaRol.objects.create(
            persona=persona,
            rol=rol_profesor,
            organizacion=organizacion,
            activo=True,
        )
        cuenta = SocialAccount.objects.create(
            user=self.usuario,
            provider="google",
            uid="google-sub-profesora",
            extra_data={},
        )
        social_login = SocialLogin(user=self.usuario, account=cuenta)

        self.adaptador.pre_social_login(self._solicitud(), social_login)
        self.client.force_login(self.usuario)
        respuesta = self.client.get(
            reverse("personas:dashboard"),
            {"organizacion": organizacion.pk},
        )

        self.assertEqual(respuesta.status_code, 403)
        self.assertEqual(
            set(persona.roles.values_list("rol__codigo", flat=True)),
            {"PROFESOR"},
        )

    def test_adaptador_oauth_limpia_claims_antes_del_lookup_de_allauth(self):
        social_login = self._social_login()
        solicitud = self._solicitud()
        adaptador_oauth = GoogleOAuth2AdapterElemental(solicitud)

        with patch.object(GoogleOAuth2Adapter, "complete_login", return_value=social_login):
            resultado = adaptador_oauth.complete_login(solicitud, app=None, token=None, response={})

        self.assertIs(resultado, social_login)
        self.assertEqual(resultado.account.extra_data, {})

    def test_lookup_recibe_extra_data_vacio_antes_de_actualizar_cuenta_existente(self):
        SocialAccount.objects.create(
            user=self.usuario,
            provider="google",
            uid="google-sub-1",
            extra_data={},
        )
        social_login = self._social_login()
        solicitud = self._solicitud()
        adaptador_oauth = GoogleOAuth2AdapterElemental(solicitud)

        with patch.object(GoogleOAuth2Adapter, "complete_login", return_value=social_login):
            resultado = adaptador_oauth.complete_login(solicitud, app=None, token=None, response={})
        with request_context(solicitud):
            resultado.lookup()

        cuenta = SocialAccount.objects.get(provider="google", uid="google-sub-1")
        self.assertEqual(cuenta.extra_data, {})
        self.assertEqual(resultado.user, self.usuario)

    @override_settings(GOOGLE_AUTH_ENABLED=True)
    def test_rechaza_correo_sin_verificar(self):
        with self.assertRaises(ImmediateHttpResponse):
            self.adaptador.pre_social_login(self._solicitud(), self._social_login(verificado=False))

    @override_settings(GOOGLE_AUTH_ENABLED=True)
    def test_rechaza_correo_duplicado_normalizado(self):
        get_user_model().objects.create_user(
            "usuario_google_duplicado",
            email=" ACCESO@example.com ",
            password=TEST_PASSWORD,
        )

        with self.assertRaises(ImmediateHttpResponse):
            self.adaptador.pre_social_login(self._solicitud(), self._social_login())

    @override_settings(GOOGLE_AUTH_ENABLED=True)
    def test_rechaza_user_inactivo(self):
        self.usuario.is_active = False
        self.usuario.save(update_fields=["is_active"])

        with self.assertRaises(ImmediateHttpResponse):
            self.adaptador.pre_social_login(self._solicitud(), self._social_login())

    @override_settings(GOOGLE_AUTH_ENABLED=True)
    def test_rechaza_un_segundo_google_sub_para_el_mismo_user(self):
        SocialAccount.objects.create(
            user=self.usuario,
            provider="google",
            uid="google-sub-anterior",
            extra_data={},
        )

        with self.assertRaises(ImmediateHttpResponse):
            self.adaptador.pre_social_login(self._solicitud(), self._social_login())

    @override_settings(GOOGLE_AUTH_ENABLED=False)
    def test_callback_no_vincula_si_el_flag_google_se_apaga(self):
        with self.assertRaises(ImmediateHttpResponse):
            self.adaptador.pre_social_login(self._solicitud(), self._social_login())

    @override_settings(GOOGLE_AUTH_ENABLED=False, GOOGLE_OAUTH_CONFIGURED=False)
    def test_inicio_google_es_solo_post_y_esta_apagado_por_defecto(self):
        respuesta_get = self.client.get(reverse("google_login_iniciar"))
        respuesta_post = self.client.post(reverse("google_login_iniciar"))

        self.assertRedirects(respuesta_get, reverse("login"), fetch_redirect_response=False)
        self.assertRedirects(respuesta_post, reverse("login"), fetch_redirect_response=False)

    def test_inicio_google_exige_csrf(self):
        cliente_csrf = Client(enforce_csrf_checks=True)

        respuesta = cliente_csrf.post(reverse("google_login_iniciar"))

        self.assertEqual(respuesta.status_code, 403)

    @override_settings(GOOGLE_AUTH_ENABLED=True, GOOGLE_OAUTH_CONFIGURED=True)
    def test_inicio_google_rechaza_next_externo_antes_del_provider(self):
        with patch.object(GoogleOAuth2AdapterElemental, "get_provider") as provider:
            respuesta = self.client.post(
                reverse("google_login_iniciar"),
                {"next": "https://ejemplo-invalido.test/"},
            )

        self.assertRedirects(respuesta, reverse("login"), fetch_redirect_response=False)
        provider.assert_not_called()

    @override_settings(GOOGLE_AUTH_ENABLED=True, GOOGLE_OAUTH_CONFIGURED=True)
    def test_inicio_google_fuerza_parametros_invariantes_ante_post_malicioso(self):
        with patch.object(GoogleOAuth2AdapterElemental, "get_provider") as get_provider:
            get_provider.return_value.redirect.return_value = HttpResponse(status=204)
            respuesta = self.client.post(
                reverse("google_login_iniciar"),
                {
                    "next": "/personas/",
                    "scope": "openid,email,perfil-adicional",
                    "auth_params": "access_type=offline",
                    "process": "connect",
                },
            )

        self.assertEqual(respuesta.status_code, 204)
        get_provider.return_value.redirect.assert_called_once_with(
            respuesta.wsgi_request,
            process="login",
            next_url="/personas/",
            scope=["openid", "email", "profile"],
            auth_params={"access_type": "online"},
        )

    def test_rutas_allauth_no_expuestas_responden_404(self):
        for ruta in (
            "/accounts/signup/",
            "/accounts/password/reset/",
            "/accounts/google/login/",
            "/accounts/google/login/token/",
        ):
            with self.subTest(ruta=ruta):
                self.assertEqual(self.client.post(ruta).status_code, 404)

    @override_settings(GOOGLE_AUTH_ENABLED=True, GOOGLE_OAUTH_CONFIGURED=True)
    def test_callback_google_cancelado_consumo_el_state_y_vuelve_al_login(self):
        state_id = "state-cancelado-prueba"
        sesion = self.client.session
        sesion["socialaccount_states"] = {state_id: [{"process": "login"}, time()]}
        sesion.save()

        with patch.object(
            GoogleOAuth2AdapterElemental,
            "get_provider",
            return_value=SimpleNamespace(id="google"),
        ):
            respuesta = self.client.get(
                reverse("google_callback"),
                {"error": "access_denied", "state": state_id},
            )

        self.assertRedirects(respuesta, reverse("login"), fetch_redirect_response=False)
        self.assertNotIn(state_id, self.client.session.get("socialaccount_states", {}))
        self.assertFalse(SocialToken.objects.exists())

    @override_settings(GOOGLE_AUTH_ENABLED=True, GOOGLE_AUTH_ENFORCED=True)
    def test_login_operacional_rechaza_password_cuando_google_se_fuerza(self):
        respuesta = self.client.post(
            reverse("login"),
            {"username": self.usuario.username, "password": TEST_PASSWORD},
        )

        self.assertRedirects(respuesta, reverse("login"), fetch_redirect_response=False)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_emergencia_autentica_solo_superusuario_y_next_es_seguro(self):
        superusuario = get_user_model().objects.create_superuser(
            "super_emergencia", "super@example.com", TEST_PASSWORD
        )
        respuesta_normal = self.client.post(
            reverse("login_emergencia"),
            {"username": self.usuario.username, "password": TEST_PASSWORD},
        )
        self.assertEqual(respuesta_normal.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

        respuesta_super = self.client.post(
            f"{reverse('login_emergencia')}?next=/personas/",
            {"username": superusuario.username, "password": TEST_PASSWORD},
        )
        self.assertRedirects(respuesta_super, "/personas/", fetch_redirect_response=False)

        self.client.logout()
        respuesta_externa = self.client.post(
            f"{reverse('login_emergencia')}?next=https://ejemplo-invalido.test/",
            {"username": superusuario.username, "password": TEST_PASSWORD},
        )
        self.assertRedirects(respuesta_externa, "/", fetch_redirect_response=False)


class SolicitudAccesoTests(TestCase):
    identidad = {
        "provider": "google",
        "provider_subject": "sub-prueba",
        "email": "acceso@example.com",
        "nombre": "Nombre Google",
        "expira_en": "2099-01-01T00:00:00+00:00",
    }

    def _sesion(self, identidad=None):
        sesion = self.client.session
        sesion[SESION_IDENTIDAD_PENDIENTE] = identidad or self.identidad
        sesion.save()

    @override_settings(ACCESS_REQUESTS_ENABLED=False)
    def test_flag_apagado_oculta_ruta(self):
        self._sesion()
        self.assertEqual(self.client.get(reverse("personas:solicitud_acceso")).status_code, 404)

    @override_settings(ACCESS_REQUESTS_ENABLED=True)
    def test_sesion_invalida_expirada_o_manipulada_redirige_sin_crear(self):
        for identidad in (
            None,
            {**self.identidad, "expira_en": "2000-01-01T00:00:00+00:00"},
            {"provider": "google"},
            {**self.identidad, "provider_subject": ""},
            {**self.identidad, "email": ""},
            {**self.identidad, "provider": "otro"},
        ):
            self.client.session.flush()
            if identidad is not None:
                self._sesion(identidad)
            respuesta = self.client.get(reverse("personas:solicitud_acceso"))
            self.assertRedirects(respuesta, reverse("login"), fetch_redirect_response=False)
        self.assertFalse(SolicitudAcceso.objects.exists())

    @override_settings(ACCESS_REQUESTS_ENABLED=True)
    def test_post_usa_solo_sesion_es_idempotente_y_no_crea_cuentas(self):
        self._sesion()
        url = reverse("personas:solicitud_acceso")
        usuarios, personas, roles = get_user_model().objects.count(), Persona.objects.count(), PersonaRol.objects.count()
        primera = self.client.post(url, {"email": "falso@example.com", "provider_subject": "falso"})
        segunda = self.client.post(url)
        self.assertContains(primera, "Solicitud enviada")
        self.assertContains(segunda, "Ya la recibimos")
        self.assertEqual(SolicitudAcceso.objects.count(), 1)
        self.assertEqual(get_user_model().objects.count(), usuarios)
        self.assertEqual(Persona.objects.count(), personas)
        self.assertEqual(PersonaRol.objects.count(), roles)
        self.assertNotIn("_auth_user_id", self.client.session)

    @override_settings(ACCESS_REQUESTS_ENABLED=True)
    def test_rechazada_conserva_historia_y_no_se_recrea_publicamente(self):
        anterior = SolicitudAcceso.objects.create(**{k: v for k, v in self.identidad.items() if k != "expira_en"}, email_normalizado="acceso@example.com", estado=SolicitudAcceso.Estado.RECHAZADA)
        self._sesion()
        respuesta = self.client.get(reverse("personas:solicitud_acceso"))
        self.assertContains(respuesta, "no fue aprobada")
        self.client.post(reverse("personas:solicitud_acceso"))
        self.assertEqual(SolicitudAcceso.objects.filter(provider_subject=anterior.provider_subject).count(), 1)
        self.assertEqual(SolicitudAcceso.objects.filter(estado=SolicitudAcceso.Estado.PENDIENTE).count(), 0)

    @override_settings(ACCESS_REQUESTS_ENABLED=True)
    def test_rate_limit_persistente_no_bloquea_recuperar_pendiente(self):
        for numero in range(5):
            SolicitudAcceso.objects.create(
                provider="google",
                provider_subject=f"sub-historico-{numero}",
                email=f"historico{numero}@example.com",
                nombre="Histórico",
                estado=SolicitudAcceso.Estado.RECHAZADA,
            )
        self._sesion()
        respuesta = self.client.post(reverse("personas:solicitud_acceso"))
        self.assertContains(respuesta, "Solicitud enviada")
        pendiente = SolicitudAcceso.objects.get(estado=SolicitudAcceso.Estado.PENDIENTE)
        for numero in range(5):
            SolicitudAcceso.objects.create(
                provider="google",
                provider_subject="sub-prueba",
                email=f"rechazada{numero}@example.com",
                nombre="Histórico",
                estado=SolicitudAcceso.Estado.RECHAZADA,
            )
        respuesta_reintento = self.client.post(reverse("personas:solicitud_acceso"))
        self.assertContains(respuesta_reintento, "Ya la recibimos")
        self.assertEqual(SolicitudAcceso.objects.filter(estado=SolicitudAcceso.Estado.PENDIENTE).count(), 1)
        self.assertEqual(pendiente.pk, SolicitudAcceso.objects.get(estado=SolicitudAcceso.Estado.PENDIENTE).pk)

    def test_email_normalizado_se_impone_al_guardar_modelo(self):
        solicitud = SolicitudAcceso.objects.create(
            provider="google", provider_subject="sub-normalizado", email=" Correo@Example.COM ", email_normalizado="incorrecto"
        )
        self.assertEqual(solicitud.email_normalizado, "correo@example.com")

    @override_settings(ACCESS_REQUESTS_ENABLED=True)
    def test_rate_limit_ventana_reautenticacion_y_expiracion(self):
        for numero in range(5):
            SolicitudAcceso.objects.create(
                provider="google", provider_subject="sub-prueba", email=f"limite{numero}@example.com", estado=SolicitudAcceso.Estado.RECHAZADA
            )
        self._sesion()
        respuesta = self.client.post(reverse("personas:solicitud_acceso"))
        self.assertContains(respuesta, "no fue aprobada")
        self._sesion()  # Simula una nueva autenticación Google de la misma identidad.
        self.assertContains(self.client.post(reverse("personas:solicitud_acceso")), "no fue aprobada")
        SolicitudAcceso.objects.filter(provider_subject="sub-prueba").update(creada_en=timezone.now() - timedelta(hours=25))
        self.assertContains(self.client.post(reverse("personas:solicitud_acceso")), "no fue aprobada")

    @override_settings(GOOGLE_AUTH_ENABLED=True, ACCESS_REQUESTS_ENABLED=True)
    def test_google_desconocido_verificado_guarda_solo_identidad_pendiente(self):
        solicitud = self.client.get("/integracion-google/").wsgi_request
        social_login = SocialLogin(
            user=get_user_model()(username="temporal", email="nuevo@example.com"),
            account=SocialAccount(provider="google", uid="sub-integracion", extra_data={}),
            email_addresses=[EmailAddress(email="nuevo@example.com", verified=True, primary=True)],
        )
        usuarios, personas, roles, sociales = get_user_model().objects.count(), Persona.objects.count(), PersonaRol.objects.count(), SocialAccount.objects.count()
        with self.assertRaises(ImmediateHttpResponse) as respuesta:
            AdaptadorSocialGoogleElemental().pre_social_login(solicitud, social_login)
        solicitud.session.save()
        self.assertEqual(respuesta.exception.response.url, reverse("personas:solicitud_acceso"))
        self.assertEqual(solicitud.session[SESION_IDENTIDAD_PENDIENTE]["provider_subject"], "sub-integracion")
        self.assertNotIn("_auth_user_id", solicitud.session)
        self.assertEqual((get_user_model().objects.count(), Persona.objects.count(), PersonaRol.objects.count(), SocialAccount.objects.count()), (usuarios, personas, roles, sociales))

    @override_settings(ACCESS_REQUESTS_ENABLED=True)
    def test_post_solicitud_exige_csrf(self):
        cliente_csrf = Client(enforce_csrf_checks=True)
        sesion = cliente_csrf.session
        sesion[SESION_IDENTIDAD_PENDIENTE] = self.identidad
        sesion.save()
        self.assertEqual(cliente_csrf.post(reverse("personas:solicitud_acceso")).status_code, 403)


class PersonasOrganizacionesTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.org = Organizacion.objects.create(
            nombre="Org Personas",
            razon_social="Org Personas SPA",
            rut="55.555.555-5",
        )
        self.rol_admin = Rol.objects.create(nombre="Administrador", codigo="ADMINISTRADOR")
        self.rol_estudiante = Rol.objects.create(nombre="Estudiante", codigo="ESTUDIANTE")
        self.rol_profesor = Rol.objects.create(nombre="Profesor", codigo="PROFESOR")

        self.user_admin = User.objects.create_user("admin_personas", password=TEST_PASSWORD, is_staff=True)
        self.persona_admin = Persona.objects.create(
            nombres="Admin",
            apellidos="Personas",
            email="admin.personas@example.com",
            user=self.user_admin,
        )
        PersonaRol.objects.create(
            persona=self.persona_admin,
            rol=self.rol_admin,
            organizacion=self.org,
            activo=True,
        )
        self.client.force_login(self.user_admin)

        self.estudiante = Persona.objects.create(
            nombres="Ana",
            apellidos="Diaz",
            email="ana.personas@example.com",
        )
        self.profesor = Persona.objects.create(
            nombres="Luis",
            apellidos="Rojas",
            email="luis.personas@example.com",
        )
        PersonaRol.objects.create(
            persona=self.estudiante,
            rol=self.rol_estudiante,
            organizacion=self.org,
            activo=True,
        )
        self.persona_rol_profesor = PersonaRol.objects.create(
            persona=self.profesor,
            rol=self.rol_profesor,
            organizacion=self.org,
            activo=True,
        )
        self.disciplina = Disciplina.objects.create(organizacion=self.org, nombre="Yoga")
        SesionClase.objects.create(
            disciplina=self.disciplina,
            fecha="2026-03-05",
            estado=SesionClase.Estado.COMPLETADA,
        )
        Payment.objects.create(
            persona=self.estudiante,
            organizacion=self.org,
            fecha_pago="2026-03-06",
            metodo_pago=Payment.Metodo.EFECTIVO,
            aplica_iva=False,
            monto_referencia=12000,
            clases_asignadas=2,
        )
        self.sesion_profesor = SesionClase.objects.create(
            disciplina=self.disciplina,
            fecha="2026-03-12",
            estado=SesionClase.Estado.COMPLETADA,
        )
        self.sesion_profesor.profesores.set([self.profesor])

    def test_organizaciones_list_muestra_metricas(self):
        response = self.client.get(
            reverse("personas:organizaciones_list"),
            {"periodo_mes": 3, "periodo_anio": 2026, "organizacion": self.org.pk},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Org Personas")
        self.assertContains(response, "Ingresos periodo")
        self.assertEqual(len(response.context["organizaciones"]), 1)

    def test_logo_organizacion_es_opcional(self):
        field = Organizacion._meta.get_field("logo")

        self.assertTrue(field.blank)
        self.assertTrue(field.null)
        self.assertIsNone(self.org.logo.name)

    def test_organizacion_create_redirige_a_detalle_con_filtros(self):
        query = "periodo_mes=3&periodo_anio=2026&organizacion=1"
        response = self.client.post(
            f"{reverse('personas:organizacion_create')}?{query}",
            {
                "nombre": "Org Nueva",
                "razon_social": "Org Nueva SPA",
                "rut": "66.666.666-6",
                "email_contacto": "org@example.com",
                "telefono_contacto": "123",
                "sitio_web": "",
                "direccion": "Direccion 123",
            },
        )

        self.assertEqual(response.status_code, 302)
        nueva = Organizacion.objects.get(nombre="Org Nueva")
        self.assertEqual(
            response.url,
            f"{reverse('personas:organizacion_detail', kwargs={'pk': nueva.pk})}?{query}",
        )

    def test_persona_create_genera_auditlog_sin_identificadores_completos(self):
        url = reverse("personas:persona_create")

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                url,
                {
                    "nombres": "Auditada",
                    "apellidos": "Nueva",
                    "email": "auditada.nueva@example.com",
                    "telefono": "+56 9 1111 2222",
                    "rut": "",
                    "fecha_nacimiento": "",
                    "activo": "on",
                    "user": "",
                    "rol-rol": self.rol_estudiante.pk,
                    "rol-organizacion": self.org.pk,
                    "rol-valor_clase": "",
                    "rol-retencion_sii": "",
                },
            )

        self.assertEqual(response.status_code, 302)
        persona = Persona.objects.get(email="auditada.nueva@example.com")
        logs = AuditLog.objects.filter(dominio="personas", objeto_id=str(persona.pk))
        self.assertTrue(logs.filter(accion=AuditLog.ACCION_CREAR).exists())
        self.assertNotIn("auditada.nueva@example.com", str(list(logs.values_list("metadata", flat=True))))

    def test_persona_edit_genera_auditlog_con_cambio_relevante(self):
        url = reverse("personas:persona_edit", kwargs={"pk": self.estudiante.pk})

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                url,
                {
                    "accion": "guardar_persona",
                    "nombres": "Ana Maria",
                    "apellidos": self.estudiante.apellidos,
                    "email": self.estudiante.email,
                    "telefono": self.estudiante.telefono,
                    "rut": self.estudiante.rut,
                    "fecha_nacimiento": "",
                    "activo": "on",
                    "user": "",
                },
            )

        self.assertEqual(response.status_code, 302)
        log = AuditLog.objects.filter(
            dominio="personas",
            accion=AuditLog.ACCION_EDITAR,
            objeto_id=str(self.estudiante.pk),
        ).latest("fecha")
        self.assertIn("nombres", log.metadata["cambios"])

    def test_ruta_organizaciones_sale_de_asistencias(self):
        response = self.client.get("/asistencias/organizaciones/")
        self.assertEqual(response.status_code, 404)

    def test_persona_detail_estudiante_oculta_bloque_profesor(self):
        response = self.client.get(
            reverse("personas:persona_detail", kwargs={"pk": self.estudiante.pk}),
            {"periodo_mes": 3, "periodo_anio": 2026, "organizacion": self.org.pk},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Perfil estudiante")
        self.assertNotContains(response, "Perfil profesor")
        self.assertContains(response, "Resumen financiero del estudiante")

    def test_dashboard_personas_anota_deuda_periodo(self):
        sesion = SesionClase.objects.create(
            disciplina=self.disciplina,
            fecha="2026-03-20",
            estado=SesionClase.Estado.COMPLETADA,
        )
        asistencia = Asistencia.objects.create(sesion=sesion, persona=self.estudiante)
        AttendanceConsumption.objects.filter(asistencia=asistencia).update(
            estado=AttendanceConsumption.Estado.DEUDA
        )

        response = self.client.get(
            reverse("personas:dashboard"),
            {"periodo_mes": 3, "periodo_anio": 2026, "organizacion": self.org.pk},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["personas_con_deuda_total"], 1)
        self.assertEqual(list(response.context["personas_con_deuda"]), [self.estudiante])

    def test_persona_detail_estudiante_permite_asociar_pago_a_asistencia(self):
        sesion = SesionClase.objects.create(
            disciplina=self.disciplina,
            fecha="2026-03-15",
            estado=SesionClase.Estado.COMPLETADA,
        )
        asistencia = Asistencia.objects.create(sesion=sesion, persona=self.estudiante)
        pago_nuevo = Payment.objects.create(
            persona=self.estudiante,
            organizacion=self.org,
            fecha_pago="2026-03-16",
            metodo_pago=Payment.Metodo.TRANSFERENCIA,
            aplica_iva=False,
            monto_referencia=10000,
            clases_asignadas=1,
        )

        response = self.client.get(
            reverse("personas:persona_detail", kwargs={"pk": self.estudiante.pk}),
            {"periodo_mes": 3, "periodo_anio": 2026, "organizacion": self.org.pk},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Finanzas")
        self.assertContains(response, "Pagada")
        self.assertContains(response, "Asociar")
        self.assertContains(response, 'name="asociar_pago_asistencia" value="1"', html=False)

        query = f"periodo_mes=3&periodo_anio=2026&organizacion={self.org.pk}"
        post_response = self.client.post(
            f"{reverse('personas:persona_detail', kwargs={'pk': self.estudiante.pk})}?{query}",
            {
                "asociar_pago_asistencia": "1",
                "asistencia_id": asistencia.pk,
                "pago_id": pago_nuevo.pk,
            },
        )

        self.assertEqual(post_response.status_code, 302)
        self.assertEqual(
            post_response.url,
            f"{reverse('personas:persona_detail', kwargs={'pk': self.estudiante.pk})}?{query}",
        )
        consumo = AttendanceConsumption.objects.get(asistencia=asistencia)
        self.assertEqual(consumo.estado, AttendanceConsumption.Estado.CONSUMIDO)
        self.assertEqual(consumo.pago, pago_nuevo)

    def test_persona_detail_profesor_oculta_bloque_estudiante(self):
        self.persona_rol_profesor.valor_clase = 5000
        self.persona_rol_profesor.retencion_sii = 15.25
        self.persona_rol_profesor.save(update_fields=["valor_clase", "retencion_sii"])
        response = self.client.get(
            reverse("personas:persona_detail", kwargs={"pk": self.profesor.pk}),
            {"periodo_mes": 3, "periodo_anio": 2026, "organizacion": self.org.pk},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Perfil profesor")
        self.assertNotContains(response, "Perfil estudiante")
        self.assertContains(response, "Sesiones como profesor")
        self.assertContains(response, "Sesiones completadas")
        self.assertContains(response, "1/1")
        self.assertContains(response, "Pago bruto")
        self.assertContains(response, "$ 0")
        self.assertContains(response, "Retención SII")
        self.assertContains(response, "Monto neto")
        detalle_sesion = (
            f'{reverse("asistencias:sesion_detail", kwargs={"pk": self.sesion_profesor.pk})}'
            f"?periodo_mes=3&periodo_anio=2026&organizacion={self.org.pk}"
        )
        agregar_asistentes = (
            f'{reverse("asistencias:asistencias_list")}'
            f"?periodo_mes=3&periodo_anio=2026&organizacion={self.org.pk}"
            f"&sesion_id={self.sesion_profesor.pk}&open=agregar_asistentes"
        )
        self.assertContains(response, "Acciones")
        self.assertContains(response, "Ver sesión")
        self.assertContains(response, "Agregar asistentes")
        self.assertContains(response, 'name="accion" value="cambiar_estado_sesion"', html=False)
        self.assertContains(response, 'onchange="this.form.submit()"', html=False)
        self.assertNotContains(response, ">Cambiar estado</span>", html=False)
        self.assertContains(response, f'href="{detalle_sesion}"', html=False)
        self.assertContains(response, f'href="{agregar_asistentes}"', html=False)

    def test_persona_detail_profesor_permite_cambiar_estado_de_sesion(self):
        query = f"periodo_mes=3&periodo_anio=2026&organizacion={self.org.pk}"
        response = self.client.post(
            f"{reverse('personas:persona_detail', kwargs={'pk': self.profesor.pk})}?{query}",
            {
                "accion": "cambiar_estado_sesion",
                "sesion_id": self.sesion_profesor.pk,
                "estado": SesionClase.Estado.CANCELADA,
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.url,
            f"{reverse('personas:persona_detail', kwargs={'pk': self.profesor.pk})}?{query}",
        )
        self.sesion_profesor.refresh_from_db()
        self.assertEqual(self.sesion_profesor.estado, SesionClase.Estado.CANCELADA)

    def test_persona_detail_permite_guardar_valor_clase_en_rol_profesor(self):
        query = f"periodo_mes=3&periodo_anio=2026&organizacion={self.org.pk}"
        response = self.client.post(
            f"{reverse('personas:persona_detail', kwargs={'pk': self.profesor.pk})}?{query}",
            {
                "accion": "guardar_configuracion_profesor",
                "persona_rol_id": self.persona_rol_profesor.pk,
                "valor_clase": "5000",
                "retencion_sii": "15.25",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.url,
            f"{reverse('personas:persona_detail', kwargs={'pk': self.profesor.pk})}?{query}",
        )
        self.persona_rol_profesor.refresh_from_db()
        self.assertEqual(self.persona_rol_profesor.valor_clase, 5000)
        self.assertEqual(self.persona_rol_profesor.retencion_sii, 15.25)

    def test_personas_list_filtra_profesor_inactivo_por_persona(self):
        self.profesor.activo = False
        self.profesor.save(update_fields=["activo"])
        self.persona_rol_profesor.activo = False
        self.persona_rol_profesor.save(update_fields=["activo"])

        response = self.client.get(
            reverse("personas:personas_list"),
            {
                "periodo_mes": 3,
                "periodo_anio": 2026,
                "organizacion": self.org.pk,
                "rol": "PROFESOR",
                "estado": "inactivas",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Luis Rojas")
        self.assertContains(response, "Profesor")
        self.assertContains(response, "Inactivo")

    def test_personas_list_respeta_organizacion_activa(self):
        otra_org = Organizacion.objects.create(
            nombre="Otra Org Personas",
            razon_social="Otra Org Personas SPA",
            rut="77.777.777-7",
        )
        persona_otra_org = Persona.objects.create(
            nombres="Persona",
            apellidos="Externa",
            email="externa.personas@example.com",
        )
        PersonaRol.objects.create(
            persona=persona_otra_org,
            rol=self.rol_estudiante,
            organizacion=otra_org,
            activo=True,
        )

        response = self.client.get(
            reverse("personas:personas_list"),
            {"periodo_mes": 3, "periodo_anio": 2026, "organizacion": self.org.pk},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ana Diaz")
        self.assertNotContains(response, "Persona Externa")

    def test_personas_list_busqueda_funciona(self):
        response = self.client.get(
            reverse("personas:personas_list"),
            {
                "periodo_mes": 3,
                "periodo_anio": 2026,
                "organizacion": self.org.pk,
                "q": "ana.personas@example.com",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ana Diaz")
        self.assertNotContains(response, "Luis Rojas")
        self.assertEqual(response.context["q"], "ana.personas@example.com")

    def test_personas_list_paginate_en_servidor_y_preserva_filtros(self):
        for index in range(30):
            persona = Persona.objects.create(
                nombres=f"Estudiante {index:02d}",
                apellidos="Paginacion",
                email=f"paginacion{index:02d}@example.com",
            )
            PersonaRol.objects.create(
                persona=persona,
                rol=self.rol_estudiante,
                organizacion=self.org,
                activo=True,
            )

        response = self.client.get(
            reverse("personas:personas_list"),
            {
                "periodo_mes": 3,
                "periodo_anio": 2026,
                "organizacion": self.org.pk,
                "rol": "ESTUDIANTE",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["page_obj"].has_next())
        self.assertLessEqual(len(response.context["personas"]), 25)
        self.assertContains(response, "Siguiente")
        self.assertContains(response, "rol=ESTUDIANTE&amp;page=2", html=False)

    def test_personas_list_no_hace_prefetch_por_todo_el_resultado(self):
        for index in range(30):
            persona = Persona.objects.create(
                nombres=f"Query {index:02d}",
                apellidos="Control",
                email=f"querycontrol{index:02d}@example.com",
            )
            PersonaRol.objects.create(
                persona=persona,
                rol=self.rol_estudiante,
                organizacion=self.org,
                activo=True,
            )

        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(
                reverse("personas:personas_list"),
                {"periodo_mes": 3, "periodo_anio": 2026, "organizacion": self.org.pk},
            )

        self.assertEqual(response.status_code, 200)
        self.assertLessEqual(len(response.context["personas"]), 25)
        self.assertLessEqual(len(queries), 20)

    def test_personas_list_pagina_antes_de_calcular_metricas(self):
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(
                reverse("personas:personas_list"),
                {"periodo_mes": 3, "periodo_anio": 2026, "organizacion": self.org.pk},
            )

        consultas_paginador = [
            query["sql"]
            for query in queries.captured_queries
            if query["sql"].startswith("SELECT COUNT(*) FROM (SELECT DISTINCT")
        ]
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(consultas_paginador), 1)
        self.assertNotIn("COALESCE((SELECT", consultas_paginador[0])

    def test_botones_agregar_rol_son_visibles_y_tienen_area_tactil(self):
        for url_name in ("personas:persona_detail", "personas:persona_edit"):
            with self.subTest(url_name=url_name):
                response = self.client.get(
                    reverse(url_name, kwargs={"pk": self.estudiante.pk}),
                    {"periodo_mes": 3, "periodo_anio": 2026, "organizacion": self.org.pk},
                )

                self.assertEqual(response.status_code, 200)
                self.assertContains(
                    response,
                    'class="btn btn-success w-100 d-inline-flex align-items-center justify-content-center"',
                    html=False,
                )
                self.assertContains(response, 'style="min-height: 44px;"', html=False)
                self.assertContains(response, ">Agregar</button>", html=False)


class PersonasRutFormTests(TestCase):
    def _data_persona(self, **overrides):
        data = {
            "nombres": "Julia",
            "apellidos": "Perez",
            "email": "",
            "telefono": "",
            "rut": "",
            "fecha_nacimiento": "",
            "activo": "on",
            "user": "",
        }
        data.update(overrides)
        return data

    def test_persona_form_valida_y_formatea_rut_chileno(self):
        form = PersonaCRMForm(data=self._data_persona(rut="12345678-5"))

        self.assertTrue(form.is_valid(), form.errors)
        persona = form.save()
        self.assertEqual(persona.rut, "12.345.678-5")

    def test_persona_form_rechaza_rut_chileno_invalido(self):
        form = PersonaCRMForm(data=self._data_persona(rut="12.345.678-9"))

        self.assertFalse(form.is_valid())
        self.assertIn("rut", form.errors)

    def test_persona_form_rechaza_persona_sin_identidad_minima(self):
        form = PersonaCRMForm(data=self._data_persona())

        self.assertFalse(form.is_valid())
        self.assertIn("__all__", form.errors)

    def test_persona_form_acepta_solo_email(self):
        form = PersonaCRMForm(data=self._data_persona(email="julia@example.com"))

        self.assertTrue(form.is_valid(), form.errors)

    def test_persona_form_acepta_solo_telefono_y_normaliza(self):
        form = PersonaCRMForm(data=self._data_persona(telefono="(9) 1234-5678"))

        self.assertTrue(form.is_valid(), form.errors)
        persona = form.save()
        self.assertEqual(persona.telefono, "+56912345678")

    def test_persona_form_no_bloquea_telefono_repetido(self):
        Persona.objects.create(nombres="Ana", apellidos="Uno", telefono="+56911111111")
        form = PersonaCRMForm(data=self._data_persona(telefono="9 1111-1111"))

        self.assertTrue(form.is_valid(), form.errors)

    def test_persona_form_bloquea_rut_duplicado(self):
        Persona.objects.create(nombres="Ana", apellidos="Uno", rut="12.345.678-5")
        form = PersonaCRMForm(data=self._data_persona(rut="12345678-5"))

        self.assertFalse(form.is_valid())
        self.assertIn("rut", form.errors)

    def test_alta_rapida_exige_identidad_minima_y_normaliza_telefono(self):
        form = PersonaRapidaForm(data={"nombres": "Julia", "apellidos": "Perez", "telefono": ""})
        self.assertFalse(form.is_valid())
        self.assertIn("__all__", form.errors)

        form = PersonaRapidaForm(data={"nombres": "Julia", "apellidos": "Perez", "telefono": "(9) 1234-5678"})
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["telefono"], "+56912345678")


class AuditarDatosV1CommandTests(TestCase):
    def test_auditoria_corre_sin_modificar_datos(self):
        persona = Persona.objects.create(nombres="Sin", apellidos="Identidad")
        before = list(Persona.objects.values_list("id", "nombres", "apellidos", "telefono", "rut", "email"))
        out = StringIO()

        call_command("auditar_datos_v1", stdout=out)

        after = list(Persona.objects.values_list("id", "nombres", "apellidos", "telefono", "rut", "email"))
        self.assertEqual(before, after)
        self.assertIn("Personas sin RUT, email ni telefono: 1", out.getvalue())
        self.assertIn(str(persona.id), out.getvalue())
        self.assertIn("No se modificaron datos.", out.getvalue())


class ResolucionSolicitudAccesoTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_user("gestor", password=TEST_PASSWORD)
        self.admin.user_permissions.add(Permission.objects.get(codename="gestionar_solicitudes_acceso"))
        self.sin_permiso = User.objects.create_user("staff_sin_permiso", password=TEST_PASSWORD, is_staff=True)
        self.org = Organizacion.objects.create(nombre="Org resolución", razon_social="Org resolución SPA", rut="66.666.666-6")
        self.rol = Rol.objects.create(nombre="Rol resolución", codigo="RESOLUCION")
        self.solicitud = SolicitudAcceso.objects.create(provider="google", provider_subject="sub-resolver", email="resolver@example.com")

    @override_settings(ACCESS_REQUESTS_ENABLED=True, ACCESS_REQUEST_APPROVAL_ENABLED=True)
    def test_aprobacion_crea_identidad_y_rol_explicitos_sin_socialaccount(self):
        solicitud, _ = aprobar_solicitud(solicitud_id=self.solicitud.pk, administrador=self.admin, tipo_resolucion=SolicitudAcceso.TipoResolucion.USUARIO_NUEVO, organizacion=self.org, rol=self.rol, nombres="Resuelta", apellidos="Persona")
        solicitud.refresh_from_db()
        self.assertEqual(solicitud.estado, SolicitudAcceso.Estado.APROBADA)
        self.assertTrue(PersonaRol.objects.filter(persona__user=solicitud.usuario_resuelto, organizacion=self.org, rol=self.rol, activo=True).exists())
        self.assertEqual(SocialAccount.objects.count(), 0)
        with self.assertRaises(ValidationError):
            aprobar_solicitud(solicitud_id=self.solicitud.pk, administrador=self.admin, tipo_resolucion=SolicitudAcceso.TipoResolucion.USUARIO_NUEVO, organizacion=self.org, rol=self.rol, nombres="Otra", apellidos="Persona")

    @override_settings(ACCESS_REQUESTS_ENABLED=True, ACCESS_REQUEST_APPROVAL_ENABLED=True)
    def test_rollback_total_si_falla_personarol(self):
        with patch("personas.resolucion_solicitudes.PersonaRol.objects.get_or_create", side_effect=RuntimeError("falla")):
            with self.assertRaises(RuntimeError):
                aprobar_solicitud(solicitud_id=self.solicitud.pk, administrador=self.admin, tipo_resolucion=SolicitudAcceso.TipoResolucion.USUARIO_NUEVO, organizacion=self.org, rol=self.rol, nombres="Rollback", apellidos="Persona")
        self.solicitud.refresh_from_db()
        self.assertEqual(self.solicitud.estado, SolicitudAcceso.Estado.PENDIENTE)
        self.assertFalse(get_user_model().objects.filter(email="resolver@example.com").exists())

    @override_settings(ACCESS_REQUESTS_ENABLED=False, ACCESS_REQUEST_APPROVAL_ENABLED=False)
    def test_flags_y_permiso_bloquean_servicio(self):
        with self.assertRaises(ValidationError):
            aprobar_solicitud(solicitud_id=self.solicitud.pk, administrador=self.admin, tipo_resolucion=SolicitudAcceso.TipoResolucion.USUARIO_NUEVO, organizacion=self.org, rol=self.rol, nombres="No", apellidos="Persona")
        with self.settings(ACCESS_REQUESTS_ENABLED=True, ACCESS_REQUEST_APPROVAL_ENABLED=True):
            with self.assertRaises(ValidationError):
                aprobar_solicitud(solicitud_id=self.solicitud.pk, administrador=self.sin_permiso, tipo_resolucion=SolicitudAcceso.TipoResolucion.USUARIO_NUEVO, organizacion=self.org, rol=self.rol, nombres="No", apellidos="Persona")

    @override_settings(ACCESS_REQUESTS_ENABLED=False, ACCESS_REQUEST_APPROVAL_ENABLED=False)
    def test_endpoints_exigen_flags_permiso_y_post(self):
        listado = reverse("personas:solicitudes_acceso_list")
        aprobar = reverse("personas:solicitud_acceso_aprobar", args=[self.solicitud.pk])
        rechazar = reverse("personas:solicitud_acceso_rechazar", args=[self.solicitud.pk])
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(listado).status_code, 404)
        self.assertEqual(self.client.post(aprobar).status_code, 404)
        with self.settings(ACCESS_REQUESTS_ENABLED=True):
            self.assertEqual(self.client.get(listado).status_code, 200)
            self.assertEqual(self.client.post(aprobar).status_code, 404)
            self.assertEqual(self.client.post(rechazar).status_code, 404)
        with self.settings(ACCESS_REQUESTS_ENABLED=True, ACCESS_REQUEST_APPROVAL_ENABLED=True):
            self.assertEqual(self.client.get(aprobar).status_code, 404)
            self.assertEqual(self.client.get(rechazar).status_code, 404)
        self.client.force_login(self.sin_permiso)
        with self.settings(ACCESS_REQUESTS_ENABLED=True):
            self.assertEqual(self.client.get(listado).status_code, 403)

    @override_settings(ACCESS_REQUESTS_ENABLED=True, ACCESS_REQUEST_APPROVAL_ENABLED=True)
    def test_conflictos_google_y_excepcion_correo_fallan_cerrado(self):
        usuario = get_user_model().objects.create_user("destino", email="otro@example.com")
        persona = Persona.objects.create(nombres="Destino", apellidos="Uno", email="destino@example.com", user=usuario)
        SocialAccount.objects.create(user=usuario, provider="google", uid="otro-sub", extra_data={})
        with self.assertRaises(ValidationError):
            aprobar_solicitud(solicitud_id=self.solicitud.pk, administrador=self.admin, tipo_resolucion=SolicitudAcceso.TipoResolucion.USUARIO_EXISTENTE, organizacion=self.org, rol=self.rol, usuario=usuario)
        self.assertEqual(self.solicitud.estado, SolicitudAcceso.Estado.PENDIENTE)
        SocialAccount.objects.filter(user=usuario).delete()
        with self.assertRaises(ValidationError):
            aprobar_solicitud(solicitud_id=self.solicitud.pk, administrador=self.admin, tipo_resolucion=SolicitudAcceso.TipoResolucion.USUARIO_EXISTENTE, organizacion=self.org, rol=self.rol, usuario=usuario)
        aprobado, _ = aprobar_solicitud(solicitud_id=self.solicitud.pk, administrador=self.admin, tipo_resolucion=SolicitudAcceso.TipoResolucion.USUARIO_EXISTENTE, organizacion=self.org, rol=self.rol, usuario=usuario, confirmar_correo_distinto=True, nota_interna="Confirmado por administrador")
        self.assertTrue(aprobado.excepcion_correo_confirmada)
        self.assertEqual(persona.user, usuario)

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import DEFAULT_DB_ALIAS, IntegrityError, connections, transaction
from django.urls import reverse
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase
from unittest.mock import patch

from api.models import ApiAccessKey
from api.throttles import ApiBurstRateThrottle
from asistencias.models import Asistencia, Disciplina, SesionClase
from finanzas.models import AttendanceConsumption, Category, DocumentoTributario, Payment, PaymentPlan, Transaction
from monitor.models import ConfiguracionMonitor, ConfiguracionSitio, DiscoverySitio, Proyecto, Sitio
from personas.models import Organizacion, Persona, PersonaRol, Rol


class PostgreSQLDatabaseConnectionTests(APITestCase):
    def test_default_database_usa_postgresql_y_responde_consulta_basica(self):
        connection = connections[DEFAULT_DB_ALIAS]

        self.assertEqual(connection.vendor, "postgresql")
        with connection.cursor() as cursor:
            cursor.execute("select current_database(), current_user")
            database_name, database_user = cursor.fetchone()

        self.assertTrue(database_name)
        self.assertTrue(database_user)

    def test_tablas_migradas_de_todas_las_apps_estan_disponibles(self):
        connection = connections[DEFAULT_DB_ALIAS]
        table_names = set(connection.introspection.table_names())
        expected_models = [
            Organizacion,
            Persona,
            Rol,
            PersonaRol,
            Disciplina,
            SesionClase,
            Asistencia,
            PaymentPlan,
            Payment,
            DocumentoTributario,
            AttendanceConsumption,
            Category,
            Transaction,
            ApiAccessKey,
            Proyecto,
            Sitio,
            ConfiguracionMonitor,
            ConfiguracionSitio,
            DiscoverySitio,
        ]

        missing_tables = [
            model._meta.db_table
            for model in expected_models
            if model._meta.db_table not in table_names
        ]

        self.assertEqual(missing_tables, [])


class CrossAppPostgreSQLModelTests(APITestCase):
    def setUp(self):
        self.organizacion = Organizacion.objects.create(
            nombre="Org PostgreSQL",
            razon_social="Org PostgreSQL SpA",
            rut="76.543.210-K",
        )
        self.rol_estudiante = Rol.objects.create(nombre="Estudiante", codigo="ESTUDIANTE")
        self.rol_profesor = Rol.objects.create(nombre="Profesor", codigo="PROFESOR")
        self.estudiante = Persona.objects.create(
            nombres="Data",
            apellidos="Estudiante",
            email="data.estudiante@example.com",
            rut="12.345.678-5",
        )
        self.profesor = Persona.objects.create(
            nombres="Data",
            apellidos="Profesor",
            email="data.profesor@example.com",
        )
        PersonaRol.objects.create(
            persona=self.estudiante,
            rol=self.rol_estudiante,
            organizacion=self.organizacion,
            activo=True,
        )
        self.rol_profesor_asignado = PersonaRol.objects.create(
            persona=self.profesor,
            rol=self.rol_profesor,
            organizacion=self.organizacion,
            activo=True,
            valor_clase=Decimal("15000.00"),
            retencion_sii=Decimal("13.75"),
        )
        self.disciplina = Disciplina.objects.create(
            organizacion=self.organizacion,
            nombre="PostgreSQL Funcional",
            badge_color=Disciplina.BadgeColor.VERDE,
        )
        self.sesion = SesionClase.objects.create(
            disciplina=self.disciplina,
            fecha="2026-05-04",
            estado=SesionClase.Estado.COMPLETADA,
        )
        self.sesion.profesores.set([self.profesor])
        self.asistencia = Asistencia.objects.create(
            sesion=self.sesion,
            persona=self.estudiante,
            estado=Asistencia.Estado.PRESENTE,
        )
        self.plan = PaymentPlan.objects.create(
            organizacion=self.organizacion,
            nombre="Plan PostgreSQL",
            num_clases=4,
            precio=Decimal("40000.00"),
            precio_incluye_iva=True,
        )
        self.documento = DocumentoTributario.objects.create(
            organizacion=self.organizacion,
            tipo_documento=DocumentoTributario.TipoDocumento.BOLETA_VENTA_AFECTA,
            folio="PG-1",
            fecha_emision="2026-05-04",
            nombre_emisor="Org PostgreSQL SpA",
            rut_emisor=self.organizacion.rut,
            nombre_receptor=self.estudiante.nombre_completo,
            rut_receptor=self.estudiante.rut,
            monto_neto=Decimal("33613.45"),
            monto_iva=Decimal("6386.55"),
            monto_total=Decimal("40000.00"),
            persona_relacionada=self.estudiante,
            metadata_extra={"origen": "test-postgresql", "items": ["clase"]},
        )
        self.pago = Payment.objects.create(
            persona=self.estudiante,
            organizacion=self.organizacion,
            plan=self.plan,
            documento_tributario=self.documento,
            fecha_pago="2026-05-04",
            monto_referencia=Decimal("40000.00"),
        )
        self.consumo = AttendanceConsumption.objects.get(asistencia=self.asistencia)
        self.categoria = Category.objects.create(nombre="Ingreso PostgreSQL", tipo=Category.Tipo.INGRESO)
        self.transaccion = Transaction.objects.create(
            organizacion=self.organizacion,
            categoria=self.categoria,
            fecha="2026-05-04",
            tipo=Transaction.Tipo.INGRESO,
            monto=Decimal("40000.00"),
            descripcion="Pago validado en PostgreSQL",
        )
        self.transaccion.documentos_tributarios.set([self.documento])
        self.api_key, self.api_key_plana = ApiAccessKey.crear_con_clave(nombre="postgresql-integracion")
        self.proyecto = Proyecto.objects.create(nombre="PostgreSQL Monitor", organizacion=self.organizacion)
        self.sitio = Sitio.objects.create(
            proyecto=self.proyecto,
            nombre="Apps AVX",
            url="https://apps.avx.cl/asistencias/",
        )
        self.configuracion_sitio = ConfiguracionSitio.objects.create(
            sitio=self.sitio,
            timeout_segundos=15,
            seguir_redirecciones=None,
        )
        self.discovery = DiscoverySitio.objects.create(
            sitio=self.sitio,
            estado_http=200,
            url_final="https://apps.avx.cl/asistencias/",
            titulo="Plataforma Elemental",
            ssl_valido=True,
            tiempo_respuesta_ms=120,
        )

    def test_relaciones_transversales_persisten_y_consultan_correctamente(self):
        sesion = (
            SesionClase.objects.select_related("disciplina__organizacion")
            .prefetch_related("profesores", "asistencias__persona")
            .get(pk=self.sesion.pk)
        )
        pago = Payment.objects.select_related("persona", "plan", "documento_tributario").get(pk=self.pago.pk)
        transaccion = Transaction.objects.prefetch_related("documentos_tributarios").get(pk=self.transaccion.pk)
        sitio = Sitio.objects.select_related("proyecto__organizacion", "configuracion").get(pk=self.sitio.pk)

        self.assertEqual(sesion.disciplina.organizacion, self.organizacion)
        self.assertEqual(list(sesion.profesores.all()), [self.profesor])
        self.assertEqual(sesion.asistencias.get().persona, self.estudiante)
        self.assertEqual(pago.clases_consumidas, 1)
        self.assertEqual(pago.saldo_clases, 3)
        self.assertEqual(pago.documento_tributario.metadata_extra["origen"], "test-postgresql")
        self.assertEqual(list(transaccion.documentos_tributarios.all()), [self.documento])
        self.assertEqual(sitio.dominio, "apps.avx.cl")
        self.assertEqual(sitio.configuracion.timeout_resuelto(ConfiguracionMonitor.actual()), 15)
        self.assertEqual(self.rol_profesor_asignado.valor_clase_normalizado, Decimal("15000.00"))
        self.assertEqual(ApiAccessKey.desde_clave_plana(self.api_key_plana), self.api_key)

    def test_constraints_unicos_clave_se_aplican_en_postgresql(self):
        duplicate_cases = [
            lambda: Organizacion.objects.create(nombre="Org duplicada", rut=self.organizacion.rut),
            lambda: Persona.objects.create(nombres="Email", apellidos="Duplicado", email=self.estudiante.email),
            lambda: Rol.objects.create(nombre="Estudiante Duplicado", codigo=self.rol_estudiante.codigo),
            lambda: PersonaRol.objects.create(
                persona=self.estudiante,
                rol=self.rol_estudiante,
                organizacion=self.organizacion,
            ),
            lambda: Disciplina.objects.create(organizacion=self.organizacion, nombre=self.disciplina.nombre),
            lambda: Asistencia.objects.create(sesion=self.sesion, persona=self.estudiante),
            lambda: PaymentPlan.objects.create(
                organizacion=self.organizacion,
                nombre=self.plan.nombre,
                precio=Decimal("10000.00"),
            ),
            lambda: DocumentoTributario.objects.create(
                organizacion=self.organizacion,
                tipo_documento=self.documento.tipo_documento,
                folio=self.documento.folio,
                rut_emisor=self.documento.rut_emisor,
                monto_total=Decimal("1.00"),
            ),
            lambda: AttendanceConsumption.objects.create(
                asistencia=self.asistencia,
                persona=self.estudiante,
                clase_fecha=self.sesion.fecha,
            ),
            lambda: ApiAccessKey.objects.create(
                nombre=self.api_key.nombre,
                prefijo="duplicado",
                hash_clave="0" * 64,
            ),
            lambda: Sitio.objects.create(
                proyecto=self.proyecto,
                nombre="Sitio duplicado",
                url=self.sitio.url,
            ),
        ]

        for duplicate_factory in duplicate_cases:
            with self.subTest(duplicate_factory=duplicate_factory):
                with self.assertRaises(IntegrityError):
                    with transaction.atomic():
                        duplicate_factory()

    def test_delete_cascade_y_set_null_se_comportan_entre_apps(self):
        documento_id = self.documento.pk
        asistencia_id = self.asistencia.pk

        self.pago.delete()
        self.consumo.refresh_from_db()
        self.assertIsNone(self.consumo.pago_id)
        self.assertTrue(DocumentoTributario.objects.filter(pk=documento_id).exists())

        self.asistencia.delete()
        self.assertFalse(AttendanceConsumption.objects.filter(asistencia_id=asistencia_id).exists())

        self.documento.delete()
        self.transaccion.refresh_from_db()
        self.assertEqual(self.transaccion.documentos_tributarios.count(), 0)


class HealthEndpointTests(APITestCase):
    def test_health_returns_ok(self):
        url = reverse("api-health")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "ok")
        self.assertIn("timestamp", response.data)


class AuthenticationFlowTests(APITestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username="martina",
            email="martina@example.com",
            password="clave-secreta",
            first_name="Martina",
            last_name="Rios",
        )
        self.login_url = reverse("auth-login")
        self.refresh_url = reverse("auth-refresh")
        self.logout_url = reverse("auth-logout")

    def test_login_returns_token_and_user_payload(self):
        response = self.client.post(
            self.login_url,
            {"username": "martina", "password": "clave-secreta"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("token", response.data)
        self.assertEqual(response.data["user"]["email"], "martina@example.com")

    def test_login_with_invalid_credentials_fails(self):
        response = self.client.post(
            self.login_url,
            {"username": "martina", "password": "otra-clave"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_refresh_rotates_token(self):
        login_response = self.client.post(
            self.login_url,
            {"username": "martina", "password": "clave-secreta"},
            format="json",
        )
        old_token = login_response.data["token"]

        refresh_response = self.client.post(
            self.refresh_url,
            {},
            format="json",
            HTTP_AUTHORIZATION=f"Token {old_token}",
        )

        self.assertEqual(refresh_response.status_code, status.HTTP_200_OK)
        self.assertNotEqual(refresh_response.data["token"], old_token)
        self.assertFalse(Token.objects.filter(key=old_token).exists())

    def test_logout_revokes_token(self):
        login_response = self.client.post(
            self.login_url,
            {"username": "martina", "password": "clave-secreta"},
            format="json",
        )
        token = login_response.data["token"]

        logout_response = self.client.post(
            self.logout_url,
            {},
            format="json",
            HTTP_AUTHORIZATION=f"Token {token}",
        )

        self.assertEqual(logout_response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Token.objects.filter(key=token).exists())


class ApiDataTests(APITestCase):
    def setUp(self):
        self.organizacion = Organizacion.objects.create(
            nombre="Org",
            razon_social="Org SpA",
            rut="44.444.444-4",
        )
        self.profesor = Persona.objects.create(
            nombres="Camila",
            apellidos="Gonzalez",
            email="profe@example.com",
        )
        self.estudiante = Persona.objects.create(
            nombres="Alumno",
            apellidos="Demo",
            email="alumno@example.com",
        )
        rol_estudiante = Rol.objects.create(nombre="Estudiante", codigo="ESTUDIANTE")
        rol_profesor = Rol.objects.create(nombre="Profesor", codigo="PROFESOR")
        PersonaRol.objects.create(
            persona=self.estudiante,
            rol=rol_estudiante,
            organizacion=self.organizacion,
            activo=True,
        )
        PersonaRol.objects.create(
            persona=self.profesor,
            rol=rol_profesor,
            organizacion=self.organizacion,
            activo=True,
        )
        self.disciplina = Disciplina.objects.create(
            organizacion=self.organizacion,
            nombre="Flex",
        )
        self.sesion = SesionClase.objects.create(
            disciplina=self.disciplina,
            fecha="2025-01-15",
        )
        self.sesion.profesores.set([self.profesor])
        Asistencia.objects.create(
            sesion=self.sesion,
            persona=self.estudiante,
        )
        self.plan = PaymentPlan.objects.create(
            organizacion=self.organizacion,
            nombre="Mensual",
            num_clases=8,
            precio=40000,
        )
        self.pago = Payment.objects.create(
            persona=self.estudiante,
            organizacion=self.organizacion,
            plan=self.plan,
            fecha_pago="2025-01-10",
            monto_referencia=40000,
            clases_asignadas=8,
        )
        self.documento = DocumentoTributario.objects.create(
            organizacion=self.organizacion,
            tipo_documento=DocumentoTributario.TipoDocumento.FACTURA_AFECTA,
            folio="100",
            fecha_emision="2025-01-09",
            nombre_emisor="Org SpA",
            rut_emisor=self.organizacion.rut,
            nombre_receptor="Cliente Demo",
            rut_receptor="11.111.111-1",
            monto_neto=40000,
            monto_iva=7600,
            monto_total=47600,
        )
        self.categoria = Category.objects.create(nombre="Clases", tipo=Category.Tipo.INGRESO)
        self.transaccion = Transaction.objects.create(
            organizacion=self.organizacion,
            categoria=self.categoria,
            fecha="2025-01-10",
            tipo=Transaction.Tipo.INGRESO,
            monto=47600,
            descripcion="Cobro enero",
        )
        self.transaccion.documentos_tributarios.add(self.documento)

        User = get_user_model()
        self.user = User.objects.create_user(username="apiuser", password="123456")
        self.user.persona = self.profesor
        self.profesor.user = self.user
        self.profesor.save(update_fields=["user"])
        token = Token.objects.create(user=self.user)
        self.token = token.key
        _, self.api_key = ApiAccessKey.crear_con_clave(nombre="movil-profes")

    def test_list_sesiones(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token}")
        response = self.client.get("/api/sesiones/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data), 1)

    def test_registrar_asistencia_via_api(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token}")
        response = self.client.post(
            f"/api/sesiones/{self.sesion.pk}/asistencias/",
            {"persona": self.estudiante.pk, "estado": "presente"},
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_estado_estudiante(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token}")
        response = self.client.get(f"/api/estudiantes/{self.estudiante.pk}/estado/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("asistencias_total", response.data)

    def test_reporte_resumen(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token}")
        response = self.client.get("/api/reportes/resumen/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("total_sesiones", response.data)

    def test_api_key_puede_consultar_endpoints_v1(self):
        self.client.credentials(HTTP_X_API_KEY=self.api_key)

        response_personas = self.client.get("/api/v1/personas/personas/")
        response_asistencias = self.client.get("/api/v1/asistencias/sesiones/")
        response_finanzas = self.client.get("/api/v1/finanzas/pagos/")

        self.assertEqual(response_personas.status_code, status.HTTP_200_OK)
        self.assertEqual(response_asistencias.status_code, status.HTTP_200_OK)
        self.assertEqual(response_finanzas.status_code, status.HTTP_200_OK)
        self.assertEqual(response_finanzas.data[0]["monto_total"], "47600.00")

    def test_api_key_no_puede_escribir_asistencias(self):
        self.client.credentials(HTTP_X_API_KEY=self.api_key)
        response = self.client.post(
            f"/api/v1/asistencias/sesiones/{self.sesion.pk}/asistencias/",
            {"persona": self.estudiante.pk, "estado": "presente"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_me_requires_usuario_autenticado(self):
        response = self.client.get("/api/me/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token}")
        response = self.client.get("/api/me/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["persona"]["email"], "profe@example.com")


class ThrottlingTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.organizacion = Organizacion.objects.create(
            nombre="Org Throttle",
            razon_social="Org Throttle SpA",
            rut="55.555.555-5",
        )
        _, self.api_key = ApiAccessKey.crear_con_clave(nombre="clave-throttle")

    def tearDown(self):
        cache.clear()

    def test_rate_limiting_aplica_a_api_key(self):
        self.client.credentials(HTTP_X_API_KEY=self.api_key)
        with patch.object(ApiBurstRateThrottle, "get_rate", return_value="1/min"):
            primera = self.client.get("/api/v1/personas/organizaciones/")
            segunda = self.client.get("/api/v1/personas/organizaciones/")

            self.assertEqual(primera.status_code, status.HTTP_200_OK)
            self.assertEqual(segunda.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

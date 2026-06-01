from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import DEFAULT_DB_ALIAS, IntegrityError, connections, transaction
from django.urls import reverse
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from api.models import ApiAccessKey
from asistencias.models import Asistencia, Disciplina, SesionClase
from finanzas.models import AttendanceConsumption, Category, DocumentoTributario, Payment, PaymentPlan, Transaction
from personas.models import Organizacion, Persona, PersonaRol, Rol


TEST_PASSWORD = "not-a-real-test-password"


class PostgreSQLDatabaseConnectionTests(APITestCase):
    def test_default_database_usa_postgresql_y_responde_consulta_basica(self):
        connection = connections[DEFAULT_DB_ALIAS]

        self.assertEqual(connection.vendor, "postgresql")
        with connection.cursor() as cursor:
            cursor.execute("select current_database(), current_user")
            database_name, database_user = cursor.fetchone()

        self.assertTrue(database_name)
        self.assertTrue(database_user)

    def test_tablas_migradas_de_apps_activas_estan_disponibles(self):
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

    def test_relaciones_transversales_persisten_y_consultan_correctamente(self):
        sesion = (
            SesionClase.objects.select_related("disciplina__organizacion")
            .prefetch_related("profesores", "asistencias__persona")
            .get(pk=self.sesion.pk)
        )
        pago = Payment.objects.select_related("persona", "plan", "documento_tributario").get(pk=self.pago.pk)
        transaccion = Transaction.objects.prefetch_related("documentos_tributarios").get(pk=self.transaccion.pk)

        self.assertEqual(sesion.disciplina.organizacion, self.organizacion)
        self.assertEqual(list(sesion.profesores.all()), [self.profesor])
        self.assertEqual(sesion.asistencias.get().persona, self.estudiante)
        self.assertEqual(pago.clases_consumidas, 1)
        self.assertEqual(pago.saldo_clases, 3)
        self.assertEqual(pago.documento_tributario.metadata_extra["origen"], "test-postgresql")
        self.assertEqual(list(transaccion.documentos_tributarios.all()), [self.documento])
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


class ApiMinimaTests(APITestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="apiuser", password=TEST_PASSWORD)
        self.token = Token.objects.create(user=self.user).key
        _, self.api_key = ApiAccessKey.crear_con_clave(nombre="clave-conservada")

    def test_health_status_y_version_responden_sin_autenticacion(self):
        casos = [
            (reverse("api-health"), {"status": "ok"}),
            (reverse("api-status"), {"status": "ok", "service": "elemental-apps"}),
            (reverse("api-version"), {"name": "Elemental Apps", "version": "v1.0"}),
        ]

        for url, esperado in casos:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                for key, value in esperado.items():
                    self.assertEqual(response.data[key], value)

    def test_me_requiere_usuario_autenticado_y_entrega_payload_minimo(self):
        response = self.client.get(reverse("api-me"))
        self.assertIn(response.status_code, {status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN})

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token}")
        response = self.client.get(reverse("api-me"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            set(response.data.keys()),
            {"username", "is_authenticated", "timestamp"},
        )
        self.assertEqual(response.data["username"], "apiuser")
        self.assertTrue(response.data["is_authenticated"])

    def test_api_key_no_expone_me_ni_endpoints_de_datos(self):
        self.client.credentials(HTTP_X_API_KEY=self.api_key)

        response_me = self.client.get(reverse("api-me"))
        response_finanzas = self.client.get("/api/v1/finanzas/pagos/")
        response_personas = self.client.get("/api/v1/personas/personas/")

        self.assertIn(response_me.status_code, {status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN})
        self.assertEqual(response_finanzas.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response_personas.status_code, status.HTTP_404_NOT_FOUND)

    def test_endpoints_de_datos_legacy_y_v1_quedan_desactivados(self):
        rutas_desactivadas = [
            "/monitor/",
            "/api/sesiones/",
            "/api/estudiantes/",
            "/api/reportes/resumen/",
            "/api/v1/personas/",
            "/api/v1/personas/personas/",
            "/api/v1/asistencias/sesiones/",
            "/api/v1/finanzas/pagos/",
            "/api/v1/finanzas/documentos-tributarios/",
            "/api/v1/finanzas/transacciones/",
        ]

        for ruta in rutas_desactivadas:
            with self.subTest(ruta=ruta):
                response = self.client.get(ruta)
                self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

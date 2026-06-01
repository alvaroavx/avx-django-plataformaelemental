from datetime import date, datetime
from decimal import Decimal
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from personas.models import Organizacion, Persona

from .models import AuditLog
from .services import registrar_auditoria, registrar_cambio


TEST_PASSWORD = "not-a-real-test-password"


class AuditoriaServiceTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user("auditor_test", password=TEST_PASSWORD)
        self.org = Organizacion.objects.create(
            nombre="Org Auditoria",
            razon_social="Org Auditoria SPA",
            rut="76.111.111-1",
        )
        self.persona = Persona.objects.create(
            nombres="Ana",
            apellidos="Auditoria",
            email="ana.auditoria@example.com",
        )

    def test_registrar_auditoria_crea_log(self):
        with self.captureOnCommitCallbacks(execute=True):
            registrar_auditoria(
                usuario=self.user,
                accion=AuditLog.ACCION_CREAR,
                dominio="personas",
                objeto=self.persona,
                organizacion=self.org,
                resumen="Persona creada",
                metadata={"persona_id": self.persona.pk},
            )

        log = AuditLog.objects.get()
        self.assertEqual(log.usuario, self.user)
        self.assertEqual(log.dominio, "personas")
        self.assertEqual(log.modelo, "personas.Persona")
        self.assertEqual(log.objeto_id, str(self.persona.pk))
        self.assertEqual(log.metadata["persona_id"], self.persona.pk)

    def test_registrar_cambio_guarda_solo_campos_relevantes(self):
        with self.captureOnCommitCallbacks(execute=True):
            registrar_cambio(
                usuario=self.user,
                dominio="personas",
                objeto=self.persona,
                organizacion=self.org,
                resumen="Persona actualizada",
                antes={"nombres": "Ana", "apellidos": "Auditoria"},
                despues={"nombres": "Ana Maria", "apellidos": "Auditoria"},
                campos=["nombres", "apellidos"],
            )

        log = AuditLog.objects.get()
        self.assertEqual(set(log.metadata["cambios"].keys()), {"nombres"})
        self.assertEqual(log.metadata["cambios"]["nombres"]["antes"], "Ana")
        self.assertEqual(log.metadata["cambios"]["nombres"]["despues"], "Ana Maria")

    def test_metadata_serializa_tipos_simples(self):
        valor_uuid = uuid4()
        with self.captureOnCommitCallbacks(execute=True):
            registrar_auditoria(
                usuario=self.user,
                accion=AuditLog.ACCION_EDITAR,
                dominio="finanzas",
                modelo="finanzas.Payment",
                objeto_id=123,
                organizacion=self.org,
                resumen="Pago actualizado",
                metadata={
                    "decimal": Decimal("12345.67"),
                    "fecha": date(2026, 5, 1),
                    "datetime": datetime(2026, 5, 1, 10, 30),
                    "uuid": valor_uuid,
                    "modelo": self.persona,
                },
            )

        metadata = AuditLog.objects.get().metadata
        self.assertEqual(metadata["decimal"], "12345.67")
        self.assertEqual(metadata["fecha"], "2026-05-01")
        self.assertEqual(metadata["datetime"], "2026-05-01T10:30:00")
        self.assertEqual(metadata["uuid"], str(valor_uuid))
        self.assertEqual(metadata["modelo"], self.persona.pk)

    def test_metadata_persona_no_guarda_identificadores_completos(self):
        with self.captureOnCommitCallbacks(execute=True):
            registrar_cambio(
                usuario=self.user,
                dominio="personas",
                objeto=self.persona,
                organizacion=self.org,
                resumen="Persona actualizada",
                antes={"rut": "11.111.111-1", "email": "antes@example.com", "telefono": "+56911111111"},
                despues={"rut": "22.222.222-2", "email": "despues@example.com", "telefono": "+56922222222"},
                campos=["rut", "email", "telefono"],
            )

        metadata_text = str(AuditLog.objects.get().metadata)
        self.assertNotIn("11.111.111-1", metadata_text)
        self.assertNotIn("22.222.222-2", metadata_text)
        self.assertNotIn("antes@example.com", metadata_text)
        self.assertNotIn("+56911111111", metadata_text)


class AuditLogAdminTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.superuser = User.objects.create_superuser(
            "audit_admin",
            email="audit.admin@example.com",
            password=TEST_PASSWORD,
        )
        self.org = Organizacion.objects.create(
            nombre="Org Admin Auditoria",
            razon_social="Org Admin Auditoria SPA",
            rut="76.222.222-2",
        )
        self.log = AuditLog.objects.create(
            usuario=self.superuser,
            accion=AuditLog.ACCION_CREAR,
            dominio="personas",
            modelo="personas.Persona",
            objeto_id="1",
            organizacion=self.org,
            resumen="Persona creada",
            metadata={"persona_id": 1},
        )
        self.client.force_login(self.superuser)

    def test_auditlog_visible_para_superuser(self):
        response = self.client.get(reverse("admin:auditoria_auditlog_changelist"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Persona creada")

    def test_auditlog_no_permite_add_change_delete(self):
        add_response = self.client.get(reverse("admin:auditoria_auditlog_add"))
        change_response = self.client.get(reverse("admin:auditoria_auditlog_change", args=[self.log.pk]))
        delete_response = self.client.get(reverse("admin:auditoria_auditlog_delete", args=[self.log.pk]))

        self.assertEqual(add_response.status_code, 403)
        self.assertEqual(change_response.status_code, 200)
        self.assertEqual(delete_response.status_code, 403)
        self.assertNotContains(change_response, 'name="resumen"', html=False)

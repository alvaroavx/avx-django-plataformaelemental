import base64
import hashlib
import io
import json
import os
import tempfile
from datetime import date
from pathlib import Path
from unittest import mock

import requests
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat, load_pem_private_key
from django.core.management import call_command
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from finanzas.forms import PaymentForm, TransactionForm
from finanzas.models import Category, EnvioCuadratura, Payment, Transaction
from finanzas.services.cuadratura_api import construir_documento, enviar_mes, estado_envio
from finanzas.services.cuadratura_v1 import prepare_month
from finanzas.services.reversas import revertir_pago
from personas.models import Organizacion, Persona, PersonaRol, Rol

LLAVES = tempfile.mkdtemp(prefix="llave-cuadratura-test-")
LLAVE_PRIVADA = os.path.join(LLAVES, "elemental.pem")
call_command("generar_llave_cuadratura", "--salida", LLAVE_PRIVADA, stdout=io.StringIO())
CUADRATURA = {
    "CUADRATURA_API_URL": "https://cuadratura.test",
    "CUADRATURA_API_TOKEN": "cdr_prueba_token-ficticio",
    "CUADRATURA_API_TIMEOUT": 5,
    "CUADRATURA_API_PRIVATE_KEY_FILE": LLAVE_PRIVADA,
}
PUBLICA = load_pem_private_key(Path(LLAVE_PRIVADA).read_bytes(), None).public_key()
ORG_CUADRATURA = "11111111-2222-3333-4444-555555555555"


class FakeResponse:
    def __init__(self, status_code, data):
        self.status_code = status_code
        self._data = data

    def json(self):
        if self._data is None:
            raise ValueError("sin JSON")
        return self._data


def verificar_firma(metodo, url, headers, cuerpo=b""):
    """Verifica la firma como lo hace Cuadratura (integrations/security.py)."""
    ruta = url.replace("https://cuadratura.test", "")
    mensaje = "\n".join([
        metodo, ruta, headers["X-Cuadratura-Timestamp"], headers["X-Cuadratura-Nonce"],
        hashlib.sha256(cuerpo).hexdigest(),
    ]).encode()
    PUBLICA.verify(base64.b64decode(headers["X-Cuadratura-Signature"]), mensaje)


class FakeSession:
    """Imita la API v1 de Cuadratura sin red, verificando firma y redirecciones."""

    def __init__(self, *, rut="77.111.222-3", status="VALIDATED", post_status=201, error=None,
                 post_error=None, review="https://cuadratura.test/revisar/lote-cuadratura-1/", al_recibir=None):
        self.rut, self.status, self.post_status, self.error = rut, status, post_status, error
        self.post_error, self.review, self.al_recibir = post_error, review, al_recibir
        self.posted = []

    def get(self, url, headers, timeout, allow_redirects):
        assert allow_redirects is False
        if self.error:
            raise self.error
        assert url == "https://cuadratura.test/api/v1/"
        assert headers["Authorization"] == "Bearer cdr_prueba_token-ficticio"
        verificar_firma("GET", url, headers)
        return FakeResponse(200, {"organizations": [{"id": ORG_CUADRATURA, "tax_id": self.rut, "legal_name": "X"}]})

    def post(self, url, data, headers, timeout, allow_redirects):
        assert allow_redirects is False
        verificar_firma("POST", url, headers, data)
        if self.al_recibir:
            self.al_recibir()
        if self.post_error:
            raise self.post_error
        documento = json.loads(data)
        self.posted.append((url, documento))
        errors = [] if self.status == "VALIDATED" else ["El contribuyente esperado no corresponde."]
        return FakeResponse(self.post_status, {"batch": {
            "id": "lote-cuadratura-1", "status": self.status, "errors": errors,
            "links": {"review": self.review},
        }})


@override_settings(**CUADRATURA)
class EnvioCuadraturaTests(TestCase):
    def setUp(self):
        self.org = Organizacion.objects.create(nombre="Taller Ficticio", razon_social="Taller Ficticio SpA", rut="77111222-3")
        self.rol_estudiante = Rol.objects.create(nombre="Estudiante", codigo="ESTUDIANTE")
        rol_finanzas = Rol.objects.create(nombre="Finanzas", codigo="FINANZAS")
        self.usuario = get_user_model().objects.create_user("finanzas-envio", password="not-a-real-test-password")
        PersonaRol.objects.create(
            persona=Persona.objects.create(nombres="Fin", apellidos="Anzas", email="fin-envio@example.com", user=self.usuario),
            rol=rol_finanzas, organizacion=self.org, activo=True,
        )
        self.estudiante = Persona.objects.create(nombres="Alumna", apellidos="Ficticia", email="alumna-envio@example.com")
        PersonaRol.objects.create(persona=self.estudiante, rol=self.rol_estudiante, organizacion=self.org, activo=True)
        self.categoria = Category.objects.create(nombre="Cobranza envío", tipo=Category.Tipo.INGRESO)
        self.pago = self.crear_pago(date(2026, 9, 4))

    def crear_pago(self, fecha, monto=50000):
        transaccion = Transaction.objects.create(
            organizacion=self.org, categoria=self.categoria, fecha=fecha,
            tipo=Transaction.Tipo.INGRESO, monto=monto, descripcion="Taller ficticio",
        )
        return Payment.objects.create(
            persona=self.estudiante, organizacion=self.org, fecha_pago=fecha, aplica_iva=True,
            monto_incluye_iva=True, monto_referencia=monto, transaccion=transaccion,
            metodo_pago=Payment.Metodo.EFECTIVO,
        )

    def enviar(self, sesion=None):
        return enviar_mes(organizacion=self.org, anio=2026, mes=9, usuario=self.usuario, sesion=sesion or FakeSession())

    def test_documento_usa_contrato_generico_y_batch_id_estable(self):
        primero = construir_documento(prepare_month(organization=self.org, year=2026, month=9))
        segundo = construir_documento(prepare_month(organization=self.org, year=2026, month=9))
        self.assertEqual(primero["contract_version"], "cuadratura-operations-v1")
        self.assertNotIn("origin_system", primero)
        self.assertEqual(primero["batch_id"], segundo["batch_id"])
        self.assertEqual(len(primero["batch_id"]), 64)
        operacion = primero["operations"][0]
        self.assertEqual(operacion["tax"], {"classification": "TAXABLE", "net": 42017, "vat": 7983, "total": 50000})
        self.assertEqual(operacion["payments"][0]["amount"], 50000)
        self.assertEqual(primero["summary"], {"operations": 1, "payments": 1, "total_amount": 50000})

    def test_envio_aceptado_bloquea_el_mes(self):
        sesion = FakeSession()
        envio = self.enviar(sesion)
        self.assertEqual((envio.estado, envio.estado_cuadratura, envio.lote_cuadratura), ("enviado", "VALIDATED", "lote-cuadratura-1"))
        url, documento = sesion.posted[0]
        self.assertEqual(url, f"https://cuadratura.test/api/v1/organizations/{ORG_CUADRATURA}/periods/2026-09/batches/")
        self.assertEqual(documento["batch_id"], envio.batch_id)

        self.pago.observaciones = "cambio"
        with self.assertRaisesMessage(ValidationError, "Septiembre 2026 ya fue enviado"):
            self.pago.save()
        with self.assertRaises(ValidationError):
            revertir_pago(pago=self.pago, motivo="Error", usuario=self.usuario)
        with self.assertRaises(ValidationError):
            self.crear_pago(date(2026, 9, 20))
        transaccion = Transaction.objects.get(pk=self.pago.transaccion_id)
        transaccion.monto = 1
        with self.assertRaises(ValidationError):
            transaccion.save()
        self.crear_pago(date(2026, 10, 1))

        form = PaymentForm(
            data={
                "organizacion": self.org.pk, "persona": self.estudiante.pk, "fecha_pago": "2026-09-15",
                "metodo_pago": Payment.Metodo.EFECTIVO, "monto_referencia": 1000, "clases_asignadas": 1,
            },
            organizacion=self.org,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("ya fue enviado", form.errors["fecha_pago"][0])
        form_mover = PaymentForm(
            data={
                "organizacion": self.org.pk, "persona": self.estudiante.pk, "fecha_pago": "2026-10-15",
                "metodo_pago": Payment.Metodo.EFECTIVO, "monto_referencia": 50000, "clases_asignadas": 1,
            },
            instance=Payment.objects.get(pk=self.pago.pk),
            organizacion=self.org,
        )
        self.assertFalse(form_mover.is_valid())
        form_transaccion = TransactionForm(
            data={"organizacion": self.org.pk, "categoria": self.categoria.pk, "fecha": "2026-09-04", "monto": 1},
            instance=transaccion,
        )
        self.assertFalse(form_transaccion.is_valid())

        with self.assertRaisesMessage(ValidationError, "ya fue enviado"):
            self.enviar()
        self.assertEqual(EnvioCuadratura.objects.count(), 1)

    def test_lote_bloqueado_en_cuadratura_no_bloquea_elemental(self):
        envio = self.enviar(FakeSession(status="BLOCKED"))
        self.assertEqual(envio.estado, "rechazado")
        self.assertIn("contribuyente", envio.detalle_error)
        self.pago.save()
        self.assertEqual(self.enviar().estado, "enviado")

    def test_sin_conexion_queda_fallido_y_se_puede_reintentar(self):
        envio = self.enviar(FakeSession(error=requests.ConnectionError("sin red")))
        self.assertEqual(envio.estado, "fallido")
        self.assertNotIn("cdr_", envio.detalle_error)
        self.pago.save()
        self.assertEqual(self.enviar().estado, "enviado")

    def test_organizacion_no_habilitada_en_cuadratura(self):
        envio = self.enviar(FakeSession(rut="76.000.000-0"))
        self.assertEqual(envio.estado, "fallido")
        self.assertIn("RUT", envio.detalle_error)

    def test_condiciones_previas_impiden_enviar(self):
        Payment.objects.create(
            persona=self.estudiante, organizacion=self.org, fecha_pago=date(2026, 9, 10),
            aplica_iva=False, monto_referencia=1000, metodo_pago=Payment.Metodo.EFECTIVO,
        )
        sesion = FakeSession()
        with self.assertRaisesMessage(ValidationError, "pendiente(s) de aclaración"):
            self.enviar(sesion)
        self.assertEqual(sesion.posted, [])
        hoy = timezone.localdate()
        estado = estado_envio(
            organizacion=self.org, anio=hoy.year, mes=hoy.month,
            preparacion=prepare_month(organization=self.org, year=hoy.year, month=hoy.month),
        )
        self.assertIn("Solo se pueden enviar meses terminados.", estado["motivos"])
        with override_settings(CUADRATURA_API_URL="http://cuadratura.test", DEBUG=False):
            estado = estado_envio(organizacion=self.org, anio=2026, mes=9, preparacion=prepare_month(organization=self.org, year=2026, month=9))
            self.assertTrue(any("https" in motivo for motivo in estado["motivos"]))
        with override_settings(CUADRATURA_API_TOKEN=""):
            estado = estado_envio(organizacion=self.org, anio=2026, mes=9, preparacion=prepare_month(organization=self.org, year=2026, month=9))
            self.assertTrue(any("no está configurada" in motivo for motivo in estado["motivos"]))

    def test_pago_revertido_no_impide_enviar(self):
        revertir_pago(pago=self.crear_pago(date(2026, 9, 12)), motivo="Duplicado", usuario=self.usuario)
        self.assertEqual(self.enviar().estado, "enviado")

    def test_vista_exige_confirmacion_y_envia(self):
        self.client.force_login(self.usuario)
        params = "?organizacion=%s&periodo_mes=9&periodo_anio=2026" % self.org.pk
        pagina = self.client.get(reverse("finanzas:preparar_mes") + params)
        self.assertContains(pagina, "Enviar 1 operaciones a Cuadratura")
        self.client.post(reverse("finanzas:enviar_cuadratura") + params)
        self.assertFalse(EnvioCuadratura.objects.exists())
        with mock.patch("finanzas.services.cuadratura_api.requests.Session", return_value=FakeSession()):
            respuesta = self.client.post(reverse("finanzas:enviar_cuadratura") + params, {"confirmo_bloqueo": "1"}, follow=True)
        self.assertContains(respuesta, "quedó bloqueado")
        self.assertEqual(EnvioCuadratura.objects.get().estado, "enviado")

    def test_mes_queda_bloqueado_mientras_se_envia(self):
        def editar_durante_envio():
            pago = Payment.objects.get(pk=self.pago.pk)
            pago.observaciones = "cambio a mitad del envío"
            with self.assertRaisesMessage(ValidationError, "en curso o sin confirmar"):
                pago.save()

        self.assertEqual(self.enviar(FakeSession(al_recibir=editar_durante_envio)).estado, "enviado")

    def test_respuesta_perdida_deja_incierto_bloqueado_y_reintento_reenvia_lo_mismo(self):
        primero = self.enviar(FakeSession(post_error=requests.ReadTimeout("sin respuesta")))
        self.assertEqual(primero.estado, "incierto")
        with self.assertRaisesMessage(ValidationError, "sin confirmar"):
            self.pago.save()
        sesion = FakeSession()
        segundo = self.enviar(sesion)
        self.assertEqual(segundo.estado, "enviado")
        self.assertEqual(segundo.batch_id, primero.batch_id)

    def test_error_al_conectar_no_bloquea(self):
        envio = self.enviar(FakeSession(post_error=requests.ConnectTimeout("no conecta")))
        self.assertEqual(envio.estado, "fallido")
        self.pago.save()

    def test_url_de_revision_ajena_se_descarta(self):
        envio = self.enviar(FakeSession(review="javascript:alert(1)"))
        self.assertEqual(envio.url_revision, "")

    def test_sin_llave_privada_fuera_de_debug_no_se_puede_enviar(self):
        with override_settings(CUADRATURA_API_PRIVATE_KEY_FILE=""):
            estado = estado_envio(organizacion=self.org, anio=2026, mes=9, preparacion=prepare_month(organization=self.org, year=2026, month=9))
        self.assertTrue(any("PRIVATE_KEY_FILE" in motivo for motivo in estado["motivos"]))

    def test_generar_llave_no_escribe_dentro_del_repo_y_protege_el_archivo(self):
        self.assertEqual(os.stat(LLAVE_PRIVADA).st_mode & 0o777, 0o600)
        from django.core.management.base import CommandError

        with self.assertRaises(CommandError):
            call_command("generar_llave_cuadratura", "--salida", "finanzas/llave.pem", stdout=io.StringIO())
        publica = base64.b64encode(PUBLICA.public_bytes(Encoding.Raw, PublicFormat.Raw)).decode()
        self.assertEqual(len(base64.b64decode(publica)), 32)

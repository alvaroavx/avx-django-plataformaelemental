from pathlib import Path
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError
from django.test import TestCase
from django.urls import reverse
from decimal import Decimal
from unittest.mock import patch

from finanzas.documentos.services import parse_tax_document
from finanzas.documentos.temp_storage import SESSION_KEY
from finanzas.forms import DocumentoTributarioForm, PaymentForm, TransactionForm
from finanzas.services import asociar_asistencia_a_pago

from asistencias.models import Asistencia, Disciplina, SesionClase
from personas.models import Organizacion, Persona, PersonaRol, Rol

from finanzas.models import (
    AttendanceConsumption,
    Category,
    DocumentoTributario,
    Payment,
    PaymentPlan,
    Transaction,
)


class FinanzasAccessTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.org = Organizacion.objects.create(
            nombre="Org Finanzas",
            razon_social="Org Finanzas SPA",
            rut="22.222.222-2",
        )
        self.rol_admin = Rol.objects.create(nombre="Administrador", codigo="ADMINISTRADOR")
        self.rol_estudiante = Rol.objects.create(nombre="Estudiante", codigo="ESTUDIANTE")

        self.user_admin = User.objects.create_user("admin_fin", password="secret123")
        self.persona_admin = Persona.objects.create(
            nombres="Admin",
            apellidos="Fin",
            email="adminfin@example.com",
            user=self.user_admin,
        )
        PersonaRol.objects.create(
            persona=self.persona_admin,
            rol=self.rol_admin,
            organizacion=self.org,
            activo=True,
        )

        self.user_no_admin = User.objects.create_user("noadmin_fin", password="secret123")
        self.persona_no_admin = Persona.objects.create(
            nombres="No",
            apellidos="Admin",
            email="noadmin@example.com",
            user=self.user_no_admin,
        )
        PersonaRol.objects.create(
            persona=self.persona_no_admin,
            rol=self.rol_estudiante,
            organizacion=self.org,
            activo=True,
        )

    def test_finanzas_dashboard_requiere_admin(self):
        self.client.force_login(self.user_no_admin)
        response = self.client.get(reverse("finanzas:dashboard"))
        self.assertEqual(response.status_code, 403)

    def test_finanzas_dashboard_admin_ok(self):
        self.client.force_login(self.user_admin)
        response = self.client.get(reverse("finanzas:dashboard"))
        self.assertEqual(response.status_code, 200)

    def test_pago_edit_back_url_usa_referer_si_existe(self):
        pago = Payment.objects.create(
            persona=self.persona_no_admin,
            organizacion=self.org,
            fecha_pago="2026-02-27",
            metodo_pago=Payment.Metodo.EFECTIVO,
            aplica_iva=False,
            monto_referencia=10000,
            clases_asignadas=1,
        )
        self.client.force_login(self.user_admin)
        query = "periodo_mes=2&periodo_anio=2026&organizacion=1&q=ana&metodo=transferencia"
        referer = f"{reverse('finanzas:pago_detail', kwargs={'pk': pago.pk})}?{query}"
        response = self.client.get(
            f"{reverse('finanzas:pago_edit', kwargs={'pk': pago.pk})}?{query}",
            HTTP_REFERER=referer,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["back_url"], referer)

    def test_pago_edit_back_url_vuelve_a_listado_si_no_hay_referer(self):
        pago = Payment.objects.create(
            persona=self.persona_no_admin,
            organizacion=self.org,
            fecha_pago="2026-02-27",
            metodo_pago=Payment.Metodo.EFECTIVO,
            aplica_iva=False,
            monto_referencia=10000,
            clases_asignadas=1,
        )
        self.client.force_login(self.user_admin)
        query = "periodo_mes=2&periodo_anio=2026&organizacion=1&q=ana&metodo=transferencia"
        response = self.client.get(f"{reverse('finanzas:pago_edit', kwargs={'pk': pago.pk})}?{query}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["back_url"], f"{reverse('finanzas:pagos_list')}?{query}")

    def test_transaccion_detail_muestra_iframe_pdf(self):
        categoria = Category.objects.create(nombre="Arriendo", tipo="egreso", activa=True)
        archivo = SimpleUploadedFile(
            "comprobante.pdf",
            b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF",
            content_type="application/pdf",
        )
        transaccion = Transaction.objects.create(
            organizacion=self.org,
            categoria=categoria,
            fecha="2026-02-27",
            tipo=Transaction.Tipo.EGRESO,
            monto=15000,
            descripcion="Pago de arriendo",
            archivo=archivo,
        )

        self.client.force_login(self.user_admin)
        query = "periodo_mes=2&periodo_anio=2026&organizacion=1"
        response = self.client.get(f"{reverse('finanzas:transaccion_detail', kwargs={'pk': transaccion.pk})}?{query}")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["archivo_es_pdf"])
        self.assertContains(response, "<iframe", html=False)
        self.assertContains(response, reverse("finanzas:transaccion_archivo", kwargs={"pk": transaccion.pk}))

    def test_transaccion_detail_muestra_imagen_inline(self):
        categoria = Category.objects.create(nombre="Movilidad", tipo="egreso", activa=True)
        archivo = SimpleUploadedFile(
            "comprobante.jpg",
            b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xd9",
            content_type="image/jpeg",
        )
        transaccion = Transaction.objects.create(
            organizacion=self.org,
            categoria=categoria,
            fecha="2026-02-27",
            tipo=Transaction.Tipo.EGRESO,
            monto=18000,
            descripcion="Taxi",
            archivo=archivo,
        )

        self.client.force_login(self.user_admin)
        response = self.client.get(reverse("finanzas:transaccion_detail", kwargs={"pk": transaccion.pk}))

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["archivo_es_pdf"])
        self.assertTrue(response.context["archivo_es_imagen"])
        self.assertContains(response, "<img", html=False)
        self.assertContains(response, reverse("finanzas:transaccion_archivo", kwargs={"pk": transaccion.pk}))

    def test_transaccion_archivo_permite_iframe_sameorigin(self):
        categoria = Category.objects.create(nombre="Honorarios", tipo="egreso", activa=True)
        archivo = SimpleUploadedFile(
            "respaldo.pdf",
            b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF",
            content_type="application/pdf",
        )
        transaccion = Transaction.objects.create(
            organizacion=self.org,
            categoria=categoria,
            fecha="2026-02-27",
            tipo=Transaction.Tipo.EGRESO,
            monto=9900,
            descripcion="Honorarios",
            archivo=archivo,
        )

        self.client.force_login(self.user_admin)
        response = self.client.get(reverse("finanzas:transaccion_archivo", kwargs={"pk": transaccion.pk}))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["X-Frame-Options"], "SAMEORIGIN")
        self.assertIn("inline;", response["Content-Disposition"])

    @patch("finanzas.views.DocumentoTributarioForm.save", side_effect=IntegrityError("conflicto"))
    def test_documento_tributario_edit_muestra_error_legible_si_falla_unicidad(self, _mock_save):
        documento = DocumentoTributario.objects.create(
            organizacion=self.org,
            tipo_documento=DocumentoTributario.TipoDocumento.BOLETA_HONORARIOS,
            folio="B-1",
            fecha_emision="2026-02-27",
            rut_emisor="11.111.111-1",
            nombre_emisor="Emisor Original",
            monto_total=10000,
        )
        self.client.force_login(self.user_admin)
        response = self.client.post(
            reverse("finanzas:documento_tributario_edit", kwargs={"pk": documento.pk}),
            {
                "organizacion": self.org.pk,
                "tipo_documento": DocumentoTributario.TipoDocumento.BOLETA_HONORARIOS,
                "fuente": DocumentoTributario.Fuente.MANUAL,
                "folio": "B-1",
                "fecha_emision": "2026-02-27",
                "nombre_emisor": "Emisor Original",
                "rut_emisor": "11.111.111-1",
                "nombre_receptor": "",
                "rut_receptor": "",
                "monto_neto": "10000",
                "monto_exento": "0",
                "iva_tasa": "0",
                "monto_iva": "0",
                "retencion_tasa": "0",
                "retencion_monto": "0",
                "monto_total": "10000",
                "documento_relacionado": "",
                "enlace_sii": "",
                "metadata_extra": "{}",
                "observaciones": "",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No se pudo guardar el documento por un conflicto de unicidad")

    def test_reporte_categorias_muestra_grafico_torta(self):
        categoria = Category.objects.create(nombre="Arriendo sala", tipo="egreso", activa=True)
        Transaction.objects.create(
            organizacion=self.org,
            categoria=categoria,
            fecha="2026-02-27",
            tipo=Transaction.Tipo.EGRESO,
            monto=25000,
            descripcion="Arriendo febrero",
        )

        self.client.force_login(self.user_admin)
        response = self.client.get(
            reverse("finanzas:reporte_categorias"),
            {"periodo_mes": 2, "periodo_anio": 2026, "organizacion": self.org.pk},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'canvas id="categoriasChart"', html=False)
        self.assertContains(response, "Chart(", html=False)
        self.assertContains(response, "Arriendo sala")

    def test_payment_plan_primer_plan_queda_por_defecto_y_se_puede_reasignar(self):
        plan_1 = PaymentPlan.objects.create(
            organizacion=self.org,
            nombre="Plan Inicial",
            num_clases=4,
            precio=20000,
            activo=True,
        )
        plan_1.refresh_from_db()
        self.assertTrue(plan_1.es_por_defecto)

        plan_2 = PaymentPlan.objects.create(
            organizacion=self.org,
            nombre="Plan Nuevo",
            num_clases=8,
            precio=35000,
            activo=True,
        )
        plan_2.refresh_from_db()
        self.assertFalse(plan_2.es_por_defecto)

        plan_2.es_por_defecto = True
        plan_2.save()
        plan_1.refresh_from_db()
        plan_2.refresh_from_db()

        self.assertFalse(plan_1.es_por_defecto)
        self.assertTrue(plan_2.es_por_defecto)

        plan_2.delete()
        plan_1.refresh_from_db()
        self.assertTrue(plan_1.es_por_defecto)

    def test_payment_form_precarga_plan_por_defecto_de_la_organizacion(self):
        PaymentPlan.objects.create(
            organizacion=self.org,
            nombre="Plan Base",
            num_clases=4,
            precio=20000,
            activo=True,
        )
        plan_destacado = PaymentPlan.objects.create(
            organizacion=self.org,
            nombre="Plan Destacado",
            num_clases=8,
            precio=30000,
            activo=True,
            es_por_defecto=True,
        )

        form = PaymentForm(initial={"organizacion": self.org.pk})

        self.assertEqual(str(form["plan"].value()), str(plan_destacado.pk))

    def test_payment_form_precarga_aplica_iva_segun_configuracion_de_organizacion(self):
        form_afecta = PaymentForm(initial={"organizacion": self.org.pk})
        self.assertTrue(form_afecta.initial["aplica_iva"])

        org_exenta = Organizacion.objects.create(
            nombre="Org Exenta",
            razon_social="Org Exenta SPA",
            rut="66.666.666-6",
            es_exenta_iva=True,
        )
        form_exenta = PaymentForm(initial={"organizacion": org_exenta.pk})
        self.assertFalse(form_exenta.initial["aplica_iva"])

    def test_plan_edit_renderiza_listado_con_edicion_inline(self):
        plan = PaymentPlan.objects.create(
            organizacion=self.org,
            nombre="Plan Editable",
            num_clases=4,
            precio=20000,
            activo=True,
        )
        self.client.force_login(self.user_admin)

        response = self.client.get(
            reverse("finanzas:plan_edit", kwargs={"pk": plan.pk}),
            {"periodo_mes": 3, "periodo_anio": 2026, "organizacion": self.org.pk},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "finanzas/planes_list.html")
        self.assertEqual(response.context["editing_plan_id"], plan.pk)
        self.assertContains(response, "Guardar cambios")
        self.assertContains(response, 'name="es_por_defecto"', html=False)
        self.assertNotContains(response, "Editar plan")

    def test_plan_edit_inline_actualiza_plan_por_defecto(self):
        plan_base = PaymentPlan.objects.create(
            organizacion=self.org,
            nombre="Plan Base",
            num_clases=4,
            precio=20000,
            activo=True,
        )
        plan_otro = PaymentPlan.objects.create(
            organizacion=self.org,
            nombre="Plan Otro",
            num_clases=8,
            precio=30000,
            activo=True,
        )
        self.client.force_login(self.user_admin)

        response = self.client.post(
            f"{reverse('finanzas:plan_edit', kwargs={'pk': plan_otro.pk})}?periodo_mes=3&periodo_anio=2026&organizacion={self.org.pk}",
            {
                "organizacion": self.org.pk,
                "nombre": "Plan Otro",
                "num_clases": 8,
                "precio": 30000,
                "precio_incluye_iva": "",
                "es_por_defecto": "on",
                "fecha_inicio": "",
                "fecha_fin": "",
                "descripcion": "",
                "activo": "on",
            },
        )

        self.assertEqual(response.status_code, 302)
        plan_base.refresh_from_db()
        plan_otro.refresh_from_db()
        self.assertFalse(plan_base.es_por_defecto)
        self.assertTrue(plan_otro.es_por_defecto)

    def test_transaction_form_deriva_tipo_desde_categoria(self):
        categoria = Category.objects.create(nombre="Venta", tipo="ingreso", activa=True)
        form = TransactionForm(
            data={
                "organizacion": self.org.pk,
                "categoria": categoria.pk,
                "fecha": "2026-02-27",
                "monto": "25000",
                "descripcion": "Ingreso evento",
                "documentos_tributarios": [],
            }
        )

        self.assertTrue(form.is_valid(), form.errors)
        transaccion = form.save(commit=False)
        self.assertEqual(transaccion.tipo, Transaction.Tipo.INGRESO)

    def test_transacciones_list_precarga_organizacion_del_filtro_en_formulario(self):
        self.client.force_login(self.user_admin)

        response = self.client.get(
            reverse("finanzas:transacciones_list"),
            {"periodo_mes": 2, "periodo_anio": 2026, "organizacion": self.org.pk},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["form"].initial["organizacion"], self.org.pk)
        self.assertContains(response, f'<option value="{self.org.pk}" selected>', html=False)

    def test_transaction_form_muestra_extracto_en_opciones_de_documentos(self):
        documento = DocumentoTributario.objects.create(
            organizacion=self.org,
            tipo_documento=DocumentoTributario.TipoDocumento.BOLETA_HONORARIOS,
            folio="BH-33",
            fecha_emision="2026-02-27",
            nombre_emisor="Artista",
            nombre_receptor="Org Finanzas",
            monto_total=50000,
            observaciones="Pago honorarios presentacion La Tarea mas Dificil en festival de febrero",
        )

        form = TransactionForm()
        etiqueta = form.fields["documentos_tributarios"].label_from_instance(documento)

        self.assertIn("Boleta de honorarios #BH-33", etiqueta)
        self.assertIn("Pago honorarios presentacion La Tarea mas Dificil", etiqueta)

    def test_documento_tributario_detail_muestra_iframe_pdf_y_asociaciones(self):
        categoria = Category.objects.create(nombre="Honorarios evento", tipo="egreso", activa=True)
        archivo_pdf = SimpleUploadedFile(
            "honorarios.pdf",
            b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF",
            content_type="application/pdf",
        )
        documento = DocumentoTributario.objects.create(
            organizacion=self.org,
            tipo_documento=DocumentoTributario.TipoDocumento.BOLETA_HONORARIOS,
            folio="H-100",
            fecha_emision="2026-02-27",
            nombre_emisor="Artista Uno",
            nombre_receptor="Org Finanzas",
            monto_total=125000,
            archivo_pdf=archivo_pdf,
        )
        transaccion = Transaction.objects.create(
            organizacion=self.org,
            categoria=categoria,
            fecha="2026-02-27",
            tipo=Transaction.Tipo.EGRESO,
            monto=125000,
            descripcion="Pago honorarios artista",
        )
        transaccion.documentos_tributarios.add(documento)

        self.client.force_login(self.user_admin)
        query = "periodo_mes=2&periodo_anio=2026&organizacion=1"
        response = self.client.get(
            f"{reverse('finanzas:documento_tributario_detail', kwargs={'pk': documento.pk})}?{query}"
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["archivo_es_pdf"])
        self.assertContains(response, "<iframe", html=False)
        self.assertContains(
            response,
            reverse("finanzas:transaccion_detail", kwargs={"pk": transaccion.pk}),
        )

    def test_documentos_tributarios_list_muestra_resumen_del_listado(self):
        categoria = Category.objects.create(nombre="Honorarios evento", tipo="egreso", activa=True)
        documento_1 = DocumentoTributario.objects.create(
            organizacion=self.org,
            tipo_documento=DocumentoTributario.TipoDocumento.FACTURA_AFECTA,
            folio="D-1",
            fecha_emision="2026-02-10",
            nombre_emisor=self.org.razon_social,
            rut_emisor=self.org.rut,
            nombre_receptor="Receptor Uno",
            rut_receptor="11.111.111-1",
            monto_neto=10000,
            monto_exento=88100,
            monto_iva=1900,
            monto_total=100000,
        )
        documento_2 = DocumentoTributario.objects.create(
            organizacion=self.org,
            tipo_documento=DocumentoTributario.TipoDocumento.BOLETA_HONORARIOS,
            folio="D-2",
            fecha_emision="2026-02-15",
            nombre_emisor="Emisor Dos",
            rut_emisor="33.333.333-3",
            nombre_receptor=self.org.razon_social,
            rut_receptor=self.org.rut,
            monto_neto=50000,
            retencion_monto=15250,
            monto_total=50000,
        )
        Payment.objects.create(
            persona=self.persona_no_admin,
            organizacion=self.org,
            documento_tributario=documento_1,
            fecha_pago="2026-02-20",
            metodo_pago=Payment.Metodo.EFECTIVO,
            aplica_iva=False,
            monto_referencia=10000,
            clases_asignadas=1,
        )
        transaccion = Transaction.objects.create(
            organizacion=self.org,
            categoria=categoria,
            fecha="2026-02-21",
            tipo=Transaction.Tipo.EGRESO,
            monto=50000,
            descripcion="Pago honorarios",
        )
        transaccion.documentos_tributarios.add(documento_2)

        self.client.force_login(self.user_admin)
        response = self.client.get(
            reverse("finanzas:documentos_tributarios_list"),
            {"periodo_mes": 2, "periodo_anio": 2026, "organizacion": self.org.pk},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["total_documentos"], 2)
        self.assertEqual(response.context["monto_total_ingresos_documentales"], 100000)
        self.assertEqual(response.context["monto_total_egresos_documentales"], 50000)
        self.assertEqual(response.context["monto_total_iva"], 1900)
        self.assertEqual(response.context["monto_total_retencion"], 15250)
        self.assertEqual(response.context["total_pagos_asociados"], 1)
        self.assertEqual(response.context["total_transacciones_asociadas"], 1)
        self.assertNotContains(response, "Total documentos")
        self.assertContains(response, "Ingresos")
        self.assertContains(response, "Egresos")
        self.assertContains(response, "IVA")
        self.assertContains(response, "Retencion")
        self.assertContains(response, "<th>Neto</th>", html=False)
        self.assertContains(response, "<th>Exento</th>", html=False)
        self.assertContains(response, "<th>IVA</th>", html=False)
        self.assertContains(response, "<th>Retencion</th>", html=False)
        self.assertNotContains(response, "<th>Organizacion</th>", html=False)
        self.assertContains(response, "$ 100.000")
        self.assertContains(response, "$ 10.000")
        self.assertContains(response, "$ 88.100")
        self.assertContains(response, "$ 1.900")
        self.assertContains(response, "$ 15.250")
        self.assertContains(response, "$ 50.000")

    def test_transacciones_list_muestra_resumen_del_listado(self):
        categoria_ingreso = Category.objects.create(nombre="Venta", tipo="ingreso", activa=True)
        categoria_egreso = Category.objects.create(nombre="Honorarios", tipo="egreso", activa=True)
        Transaction.objects.create(
            organizacion=self.org,
            categoria=categoria_ingreso,
            fecha="2026-02-05",
            tipo=Transaction.Tipo.INGRESO,
            monto=120000,
            descripcion="Ingreso evento",
        )
        Transaction.objects.create(
            organizacion=self.org,
            categoria=categoria_egreso,
            fecha="2026-02-06",
            tipo=Transaction.Tipo.EGRESO,
            monto=30000,
            descripcion="Pago artista",
        )
        Transaction.objects.create(
            organizacion=self.org,
            categoria=categoria_egreso,
            fecha="2026-03-06",
            tipo=Transaction.Tipo.EGRESO,
            monto=99999,
            descripcion="Fuera de periodo",
        )

        self.client.force_login(self.user_admin)
        response = self.client.get(
            reverse("finanzas:transacciones_list"),
            {"periodo_mes": 2, "periodo_anio": 2026, "organizacion": self.org.pk},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["total_transacciones"], 2)
        self.assertEqual(response.context["total_ingresos"], 120000)
        self.assertEqual(response.context["total_egresos"], 30000)
        self.assertEqual(response.context["balance_transacciones"], 90000)
        self.assertContains(response, "Total transacciones")
        self.assertContains(response, "Balance")

    def test_documento_tributario_importar_parsea_y_muestra_revision_sin_guardar(self):
        xml = SimpleUploadedFile(
            "boleta.xml",
            b"""
            <EnvioDTE>
              <SetDTE>
                <DTE>
                  <Documento>
                    <Encabezado>
                      <IdDoc>
                        <TipoDTE>39</TipoDTE>
                        <Folio>101</Folio>
                        <FchEmis>2026-02-27</FchEmis>
                      </IdDoc>
                      <Emisor>
                        <RUTEmisor>11.111.111-1</RUTEmisor>
                        <RznSoc>Org Finanzas</RznSoc>
                      </Emisor>
                      <Receptor>
                        <RUTRecep>22.222.222-2</RUTRecep>
                        <RznSocRecep>Ana Diaz</RznSocRecep>
                      </Receptor>
                      <Totales>
                        <MntNeto>10000</MntNeto>
                        <IVA>1900</IVA>
                        <MntTotal>11900</MntTotal>
                        <TasaIVA>19</TasaIVA>
                      </Totales>
                    </Encabezado>
                    <Detalle>
                      <NroLinDet>1</NroLinDet>
                      <NmbItem>Plan mensual</NmbItem>
                      <QtyItem>1</QtyItem>
                      <PrcItem>10000</PrcItem>
                      <MontoItem>10000</MontoItem>
                    </Detalle>
                  </Documento>
                </DTE>
              </SetDTE>
            </EnvioDTE>
            """,
            content_type="application/xml",
        )
        self.client.force_login(self.user_admin)

        upload_response = self.client.get(reverse("finanzas:documento_tributario_importar"))
        self.assertEqual(upload_response.status_code, 200)
        self.assertContains(upload_response, 'name="archivo"', html=False)
        self.assertNotContains(upload_response, 'name="archivo_xml"', html=False)
        self.assertNotContains(upload_response, 'name="archivo_pdf"', html=False)

        response = self.client.post(
            reverse("finanzas:documento_tributario_importar"),
            {"accion": "parsear", "archivo": xml},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Revision del documento tributario")
        self.assertContains(response, "101")
        self.assertEqual(response.context["documento_form"].initial["observaciones"], "Plan mensual")
        self.assertEqual(DocumentoTributario.objects.count(), 0)

    @patch("finanzas.documentos.parsers.PdfFallbackParser._extract_text_with_pdftotext")
    @patch("finanzas.documentos.parsers.PdfFallbackParser._extract_text_with_pypdf", return_value="")
    def test_documento_tributario_importar_precarga_formulario_desde_pdf(
        self,
        _extract_text_with_pypdf,
        extract_text_with_pdftotext,
    ):
        extract_text_with_pdftotext.return_value = """
        R.U.T.: 77.813.508-6
        ESPACIO CULTURAL Y DEPORTIVO ELEMENTOS SPA
        GIRO: REALIZACIÓN DE ACTIVIDADES
        FACTURA NO AFECTA O EXENTA ELECTRONICA
        Nº2
        Fecha Emision: 10 de Marzo del 2026
        SEÑOR(ES):
        PEREIRA E.I.R.L.
        R.U.T.: 77.752.651-0
        GIRO: SERVICIOS DE PRODUCCION DE OBRAS DE TEAT
        DIRECCION: AV. NVA A EINSTEIN 290 PLAZA AMERICA 808
        DESCRIPCION                CANTIDAD     PRECIO       TOTAL
        - Obra Circo Contemporaneo      1       500.000     500.000
        Función La Tarea más difícil - Febrero - 2026
        EXENTO $ 500.000
        TOTAL $ 500.000
        """
        pdf = SimpleUploadedFile(
            "factura.pdf",
            b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF",
            content_type="application/pdf",
        )
        self.client.force_login(self.user_admin)

        response = self.client.post(
            reverse("finanzas:documento_tributario_importar"),
            {"accion": "parsear", "archivo": pdf},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Revision del documento tributario")
        self.assertContains(response, 'name="folio"')
        self.assertContains(response, 'value="2"', html=False)
        self.assertContains(response, 'value="2026-03-10"', html=False)
        self.assertContains(response, 'value="ESPACIO CULTURAL Y DEPORTIVO ELEMENTOS SPA"', html=False)
        self.assertContains(response, 'value="77.813.508-6"', html=False)
        self.assertContains(response, 'value="PEREIRA E.I.R.L."', html=False)
        self.assertContains(response, 'value="77.752.651-0"', html=False)
        self.assertContains(response, 'value="500000"', html=False)
        self.assertEqual(
            response.context["documento_form"].initial["observaciones"],
            "Obra Circo Contemporaneo Función La Tarea más difícil - Febrero - 2026",
        )
        self.assertEqual(DocumentoTributario.objects.count(), 0)

        token = next(iter(self.client.session[SESSION_KEY].keys()))
        visor_url = reverse(
            "finanzas:documento_tributario_importacion_archivo",
            kwargs={"token": token, "tipo_archivo": "pdf"},
        )
        self.assertContains(response, visor_url)
        self.assertContains(response, "<iframe", html=False)

        visor_response = self.client.get(visor_url)
        self.assertEqual(visor_response.status_code, 200)
        self.assertEqual(visor_response["X-Frame-Options"], "SAMEORIGIN")
        self.assertIn("inline;", visor_response["Content-Disposition"])

    def test_documento_tributario_importar_muestra_xml_subido_en_revision(self):
        xml = SimpleUploadedFile(
            "boleta.xml",
            b"""
            <EnvioDTE>
              <SetDTE>
                <DTE>
                  <Documento>
                    <Encabezado>
                      <IdDoc>
                        <TipoDTE>39</TipoDTE>
                        <Folio>101</Folio>
                        <FchEmis>2026-02-27</FchEmis>
                      </IdDoc>
                    </Encabezado>
                  </Documento>
                </DTE>
              </SetDTE>
            </EnvioDTE>
            """,
            content_type="application/xml",
        )
        self.client.force_login(self.user_admin)

        response = self.client.post(
            reverse("finanzas:documento_tributario_importar"),
            {"accion": "parsear", "archivo": xml},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Visor del archivo subido")
        self.assertContains(response, "&lt;EnvioDTE&gt;", html=False)

        token = next(iter(self.client.session[SESSION_KEY].keys()))
        visor_url = reverse(
            "finanzas:documento_tributario_importacion_archivo",
            kwargs={"token": token, "tipo_archivo": "xml"},
        )
        self.assertContains(response, visor_url)

    def test_documento_tributario_importar_confirma_con_metadata_json_serializada(self):
        xml = SimpleUploadedFile(
            "boleta.xml",
            b"""
            <EnvioDTE>
              <SetDTE>
                <DTE>
                  <Documento>
                    <Encabezado>
                      <IdDoc>
                        <TipoDTE>39</TipoDTE>
                        <Folio>101</Folio>
                        <FchEmis>2026-02-27</FchEmis>
                      </IdDoc>
                      <Emisor>
                        <RUTEmisor>11.111.111-1</RUTEmisor>
                        <RznSoc>Org Finanzas</RznSoc>
                      </Emisor>
                      <Receptor>
                        <RUTRecep>22.222.222-2</RUTRecep>
                        <RznSocRecep>Ana Diaz</RznSocRecep>
                      </Receptor>
                      <Totales>
                        <MntNeto>10000</MntNeto>
                        <IVA>1900</IVA>
                        <MntTotal>11900</MntTotal>
                        <TasaIVA>19</TasaIVA>
                      </Totales>
                    </Encabezado>
                  </Documento>
                </DTE>
              </SetDTE>
            </EnvioDTE>
            """,
            content_type="application/xml",
        )
        self.client.force_login(self.user_admin)

        parse_response = self.client.post(
            f"{reverse('finanzas:documento_tributario_importar')}?periodo_mes=2&periodo_anio=2026&organizacion={self.org.pk}",
            {"accion": "parsear", "archivo": xml},
        )
        self.assertEqual(parse_response.status_code, 200)

        token = next(iter(self.client.session[SESSION_KEY].keys()))
        documento_initial = dict(parse_response.context["documento_form"].initial)
        post_data = {
            "accion": "confirmar",
            "token_importacion": token,
            **documento_initial,
        }

        confirm_response = self.client.post(
            f"{reverse('finanzas:documento_tributario_importar')}?periodo_mes=2&periodo_anio=2026&organizacion={self.org.pk}",
            post_data,
        )

        self.assertEqual(confirm_response.status_code, 302)
        documento = DocumentoTributario.objects.get(folio="101")
        self.assertIn("importacion_normalizada", documento.metadata_extra)
        self.assertIn("warnings_importacion", documento.metadata_extra)

    def test_documento_tributario_importar_permite_mismo_folio_si_cambia_emisor(self):
        DocumentoTributario.objects.create(
            organizacion=self.org,
            tipo_documento=DocumentoTributario.TipoDocumento.BOLETA_HONORARIOS,
            folio="45",
            fecha_emision="2026-03-12",
            rut_emisor="12.345.678-9",
            nombre_emisor="OTRO EMISOR",
            rut_receptor="77.813.508-6",
            nombre_receptor="ESPACIO CULTURAL Y DEPORTIVO ELEMENTOS SPA",
            monto_total=100000,
        )
        pdf_path = Path(__file__).resolve().parent.parent / "public" / "202603_LaTarea+Dificil.12Febrero2026_BarbaraAllendes.pdf"
        pdf = SimpleUploadedFile(
            pdf_path.name,
            pdf_path.read_bytes(),
            content_type="application/pdf",
        )
        self.client.force_login(self.user_admin)

        parse_response = self.client.post(
            f"{reverse('finanzas:documento_tributario_importar')}?periodo_mes=3&periodo_anio=2026&organizacion={self.org.pk}",
            {"accion": "parsear", "archivo": pdf},
        )

        self.assertEqual(parse_response.status_code, 200)
        self.assertEqual(parse_response.context["review_payload"]["duplicates"], [])

        token = next(iter(self.client.session[SESSION_KEY].keys()))
        post_data = {
            "accion": "confirmar",
            "token_importacion": token,
            **dict(parse_response.context["documento_form"].initial),
        }
        confirm_response = self.client.post(
            f"{reverse('finanzas:documento_tributario_importar')}?periodo_mes=3&periodo_anio=2026&organizacion={self.org.pk}",
            post_data,
        )

        self.assertEqual(confirm_response.status_code, 302)
        self.assertEqual(
            DocumentoTributario.objects.filter(
                organizacion=self.org,
                tipo_documento=DocumentoTributario.TipoDocumento.BOLETA_HONORARIOS,
                folio="45",
            ).count(),
            2,
        )
        self.assertTrue(
            DocumentoTributario.objects.filter(
                organizacion=self.org,
                tipo_documento=DocumentoTributario.TipoDocumento.BOLETA_HONORARIOS,
                folio="45",
                rut_emisor="18.445.523-4",
            ).exists()
        )

    def test_documento_tributario_importar_advierte_duplicado_por_folio_tipo_y_emisor(self):
        DocumentoTributario.objects.create(
            organizacion=self.org,
            tipo_documento=DocumentoTributario.TipoDocumento.BOLETA_HONORARIOS,
            folio="45",
            fecha_emision="2026-03-12",
            rut_emisor="18.445.523-4",
            nombre_emisor="BARBARA BEATRIZ ALLENDES HUERTA",
            rut_receptor="77.813.508-6",
            nombre_receptor="ESPACIO CULTURAL Y DEPORTIVO ELEMENTOS SPA",
            monto_total=100000,
        )
        pdf_path = Path(__file__).resolve().parent.parent / "public" / "202603_LaTarea+Dificil.12Febrero2026_BarbaraAllendes.pdf"
        pdf = SimpleUploadedFile(
            pdf_path.name,
            pdf_path.read_bytes(),
            content_type="application/pdf",
        )
        self.client.force_login(self.user_admin)

        response = self.client.post(
            f"{reverse('finanzas:documento_tributario_importar')}?periodo_mes=3&periodo_anio=2026&organizacion={self.org.pk}",
            {"accion": "parsear", "archivo": pdf},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["review_payload"]["duplicates"]), 1)
        self.assertContains(response, "Documento #")


class FinanzasIntegrationTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.org = Organizacion.objects.create(
            nombre="Org Integracion",
            razon_social="Org Integracion SPA",
            rut="33.333.333-3",
        )
        self.rol_admin = Rol.objects.create(nombre="Administrador", codigo="ADMINISTRADOR")
        self.rol_estudiante = Rol.objects.create(nombre="Estudiante", codigo="ESTUDIANTE")

        self.user_admin = User.objects.create_user("admin_int", password="secret123")
        self.persona_admin = Persona.objects.create(
            nombres="Admin",
            apellidos="Integracion",
            email="adminint@example.com",
            user=self.user_admin,
        )
        PersonaRol.objects.create(
            persona=self.persona_admin,
            rol=self.rol_admin,
            organizacion=self.org,
            activo=True,
        )

        self.estudiante = Persona.objects.create(
            nombres="Ana",
            apellidos="Diaz",
            email="ana.int@example.com",
        )
        PersonaRol.objects.create(
            persona=self.estudiante,
            rol=self.rol_estudiante,
            organizacion=self.org,
            activo=True,
        )
        self.disciplina = Disciplina.objects.create(
            organizacion=self.org,
            nombre="Yoga",
        )
        self.sesion_1 = SesionClase.objects.create(
            disciplina=self.disciplina,
            fecha="2026-02-26",
            estado=SesionClase.Estado.PROGRAMADA,
        )
        self.sesion_2 = SesionClase.objects.create(
            disciplina=self.disciplina,
            fecha="2026-02-27",
            estado=SesionClase.Estado.PROGRAMADA,
        )

    def test_asistencia_sin_pago_queda_como_deuda(self):
        asistencia = Asistencia.objects.create(sesion=self.sesion_1, persona=self.estudiante)
        consumo = AttendanceConsumption.objects.get(asistencia=asistencia)
        self.assertEqual(consumo.estado, AttendanceConsumption.Estado.DEUDA)
        self.assertIsNone(consumo.pago)

    def test_asistencia_con_pago_disponible_queda_consumida(self):
        Payment.objects.create(
            persona=self.estudiante,
            organizacion=self.org,
            fecha_pago="2026-02-25",
            metodo_pago=Payment.Metodo.TRANSFERENCIA,
            aplica_iva=False,
            monto_referencia=10000,
            clases_asignadas=1,
        )
        asistencia = Asistencia.objects.create(sesion=self.sesion_2, persona=self.estudiante)
        consumo = AttendanceConsumption.objects.get(asistencia=asistencia)
        self.assertEqual(consumo.estado, AttendanceConsumption.Estado.CONSUMIDO)
        self.assertIsNotNone(consumo.pago)

    def test_asistencia_no_consume_pago_de_otro_mes(self):
        Payment.objects.create(
            persona=self.estudiante,
            organizacion=self.org,
            fecha_pago="2026-01-25",
            metodo_pago=Payment.Metodo.TRANSFERENCIA,
            numero_comprobante="ENE-1",
            aplica_iva=False,
            monto_referencia=10000,
            clases_asignadas=1,
        )

        asistencia = Asistencia.objects.create(sesion=self.sesion_2, persona=self.estudiante)
        consumo = AttendanceConsumption.objects.get(asistencia=asistencia)

        self.assertEqual(consumo.estado, AttendanceConsumption.Estado.DEUDA)
        self.assertIsNone(consumo.pago)

    def test_pago_nuevo_imputa_deudas_previas(self):
        asistencia = Asistencia.objects.create(sesion=self.sesion_1, persona=self.estudiante)
        consumo = AttendanceConsumption.objects.get(asistencia=asistencia)
        self.assertEqual(consumo.estado, AttendanceConsumption.Estado.DEUDA)
        self.assertIsNone(consumo.pago)

        pago = Payment.objects.create(
            persona=self.estudiante,
            organizacion=self.org,
            fecha_pago="2026-02-28",
            metodo_pago=Payment.Metodo.TRANSFERENCIA,
            aplica_iva=False,
            monto_referencia=10000,
            clases_asignadas=1,
        )

        consumo.refresh_from_db()
        self.assertEqual(consumo.estado, AttendanceConsumption.Estado.CONSUMIDO)
        self.assertEqual(consumo.pago, pago)

    def test_pago_no_imputa_deuda_de_otro_mes(self):
        asistencia = Asistencia.objects.create(sesion=self.sesion_1, persona=self.estudiante)
        consumo = AttendanceConsumption.objects.get(asistencia=asistencia)
        self.assertEqual(consumo.estado, AttendanceConsumption.Estado.DEUDA)

        Payment.objects.create(
            persona=self.estudiante,
            organizacion=self.org,
            fecha_pago="2026-03-05",
            metodo_pago=Payment.Metodo.TRANSFERENCIA,
            numero_comprobante="MAR-1",
            aplica_iva=False,
            monto_referencia=10000,
            clases_asignadas=1,
        )

        consumo.refresh_from_db()
        self.assertEqual(consumo.estado, AttendanceConsumption.Estado.DEUDA)
        self.assertIsNone(consumo.pago)

    def test_asociar_asistencia_a_pago_rechaza_pago_de_otro_mes(self):
        pago_otro_mes = Payment.objects.create(
            persona=self.estudiante,
            organizacion=self.org,
            fecha_pago="2026-03-05",
            metodo_pago=Payment.Metodo.EFECTIVO,
            aplica_iva=False,
            monto_referencia=10000,
            clases_asignadas=1,
        )
        asistencia = Asistencia.objects.create(sesion=self.sesion_1, persona=self.estudiante)

        with self.assertRaisesMessage(
            ValueError,
            "Solo se pueden asociar pagos del mismo mes y anio de la asistencia.",
        ):
            asociar_asistencia_a_pago(asistencia, pago_otro_mes)

    def test_pago_con_plan_respeta_monto_referencia_editable(self):
        plan = PaymentPlan.objects.create(
            organizacion=self.org,
            nombre="Plan Base",
            num_clases=4,
            precio=20000,
            activo=True,
        )
        pago = Payment.objects.create(
            persona=self.estudiante,
            organizacion=self.org,
            plan=plan,
            fecha_pago="2026-02-28",
            metodo_pago=Payment.Metodo.TRANSFERENCIA,
            aplica_iva=False,
            monto_referencia=15000,
        )
        self.assertEqual(pago.monto_total, 15000)

    def test_form_transferencia_exige_numero_comprobante(self):
        data_base = {
            "organizacion": self.org.pk,
            "persona": self.estudiante.pk,
            "fecha_pago": "2026-02-28",
            "metodo_pago": "transferencia",
            "monto_referencia": "10000",
            "clases_asignadas": "1",
        }
        form = PaymentForm(data=data_base)
        self.assertFalse(form.is_valid())
        self.assertIn("numero_comprobante", form.errors)

        data_efectivo = {
            **data_base,
            "metodo_pago": "efectivo",
            "numero_comprobante": "",
        }
        form_efectivo = PaymentForm(data=data_efectivo)
        self.assertTrue(form_efectivo.is_valid(), form_efectivo.errors)

    def test_form_rechaza_plan_de_otra_organizacion(self):
        otra_org = Organizacion.objects.create(
            nombre="Org Externa",
            razon_social="Org Externa SPA",
            rut="44.444.444-4",
        )
        plan_otro = PaymentPlan.objects.create(
            organizacion=otra_org,
            nombre="Plan Otro",
            num_clases=4,
            precio=22000,
            activo=True,
        )
        form = PaymentForm(
            data={
                "organizacion": self.org.pk,
                "persona": self.estudiante.pk,
                "plan": plan_otro.pk,
                "fecha_pago": "2026-02-28",
                "metodo_pago": "efectivo",
                "monto_referencia": "10000",
                "clases_asignadas": "1",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("plan", form.errors)

    def test_form_rechaza_documento_tributario_de_otra_organizacion(self):
        otra_org = Organizacion.objects.create(
            nombre="Org Docs",
            razon_social="Org Docs SPA",
            rut="55.555.555-5",
        )
        documento_otro = DocumentoTributario.objects.create(
            organizacion=otra_org,
            tipo_documento=DocumentoTributario.TipoDocumento.FACTURA_AFECTA,
            folio="F-1",
            fecha_emision="2026-02-28",
            monto_total=10000,
        )
        form = PaymentForm(
            data={
                "organizacion": self.org.pk,
                "persona": self.estudiante.pk,
                "documento_tributario": documento_otro.pk,
                "fecha_pago": "2026-02-28",
                "metodo_pago": "efectivo",
                "monto_referencia": "10000",
                "clases_asignadas": "1",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("documento_tributario", form.errors)

    def test_parse_tax_document_dte_xml_normaliza_boleta_venta(self):
        xml = b"""
        <EnvioDTE>
          <SetDTE>
            <DTE>
              <Documento>
                <Encabezado>
                  <IdDoc>
                    <TipoDTE>39</TipoDTE>
                    <Folio>555</Folio>
                    <FchEmis>2026-02-28</FchEmis>
                  </IdDoc>
                  <Emisor>
                    <RUTEmisor>11.111.111-1</RUTEmisor>
                    <RznSoc>Org Integracion</RznSoc>
                  </Emisor>
                  <Receptor>
                    <RUTRecep>22.222.222-2</RUTRecep>
                    <RznSocRecep>Cliente Uno</RznSocRecep>
                  </Receptor>
                  <Totales>
                    <MntNeto>20000</MntNeto>
                    <IVA>3800</IVA>
                    <MntTotal>23800</MntTotal>
                    <TasaIVA>19</TasaIVA>
                  </Totales>
                </Encabezado>
                <Detalle>
                  <NroLinDet>1</NroLinDet>
                  <NmbItem>Taller</NmbItem>
                  <QtyItem>2</QtyItem>
                  <PrcItem>10000</PrcItem>
                  <MontoItem>20000</MontoItem>
                </Detalle>
              </Documento>
            </DTE>
          </SetDTE>
        </EnvioDTE>
        """
        normalized = parse_tax_document(xml_bytes=xml, xml_name="dte.xml", organizacion_id=self.org.pk)

        self.assertEqual(normalized.get_value("encabezado", "categoria_documental"), "sales_receipt")
        self.assertEqual(normalized.get_value("encabezado", "tipo_documento_sugerido"), "boleta_venta_afecta")
        self.assertEqual(normalized.get_value("encabezado", "folio"), "555")
        self.assertEqual(normalized.get_value("montos", "total_bruto"), Decimal("23800"))
        self.assertEqual(len(normalized.lineas), 1)

    def test_parse_tax_document_bhe_xml_normaliza_retencion(self):
        xml = b"""
        <datos>
          <tipodoc>bhe</tipodoc>
          <numeroBoleta>9001</numeroBoleta>
          <fechaBoleta>2026-02-20</fechaBoleta>
          <rutEmisor>12345678</rutEmisor>
          <dvEmisor>9</dvEmisor>
          <rutReceptor>11111111</rutReceptor>
          <dvReceptor>1</dvReceptor>
          <nombreReceptor>Org Integracion</nombreReceptor>
          <domicilioEmisor>Calle Uno</domicilioEmisor>
          <domicilioReceptor>Calle Dos</domicilioReceptor>
          <actividadEconomica>Artista</actividadEconomica>
          <totalHonorarios>100000</totalHonorarios>
          <impuestoHonorarios>15250</impuestoHonorarios>
          <liquidoHonorarios>84750</liquidoHonorarios>
          <porcentajeImpuesto>15.25</porcentajeImpuesto>
          <prestacionServicios>
            <item>Presentacion artistica</item>
          </prestacionServicios>
        </datos>
        """
        normalized = parse_tax_document(xml_bytes=xml, xml_name="bhe.xml", organizacion_id=self.org.pk)

        self.assertEqual(normalized.get_value("encabezado", "categoria_documental"), "fee_receipt")
        self.assertEqual(normalized.get_value("encabezado", "tipo_documento_sugerido"), "boleta_honorarios")
        self.assertEqual(normalized.get_value("montos", "retencion_honorarios"), Decimal("15250"))
        self.assertEqual(normalized.get_value("montos", "porcentaje_retencion"), Decimal("15.25"))
        self.assertEqual(normalized.lineas[0].fields["descripcion"].value, "Presentacion artistica")

    @patch("finanzas.documentos.parsers.PdfFallbackParser._extract_text_with_pdftotext")
    @patch("finanzas.documentos.parsers.PdfFallbackParser._extract_text_with_pypdf", return_value="")
    def test_parse_tax_document_bhe_pdf_extrae_folio_fecha_y_montos(
        self,
        _extract_text_with_pypdf,
        extract_text_with_pdftotext,
    ):
        extract_text_with_pdftotext.return_value = """
                                                                                                            BOLETA DE HONORARIOS
                   ALVARO FRANCISCO VARGAS QUEZADA                                                              ELECTRONICA

                                                                                                                     N ° 125
                            RUT: 17.085.005−K
        GIRO(S): OTRAS ACTIVIDADES PROFESIONALES, CIENTIFICAS Y
                             TECNICAS N.C.P.,
                  SERVICIOS ARTISTICOS Y/O DEPORTIVOS
                             NUEVA 3 ST 51 EL NARANJAL , RENGO
                                   TELEFONO: 956490299

                                                                                                            Fecha: 12 de Marzo de 2026

Señor(es): ESPACIO CULTURAL Y DEPORTIVO ELEMENTOS SPA                                                   Rut: 77.813.508− 6
Domicilio: NUEVA TRES N 1020, EL NARANJAL NORTE, RENGO

Por atención profesional:
FUNCION LA TAREA MAS DIFICIL − FEBRERO − 2026                                                                                  100.000
                                                                                     Total Honorarios: $:                      100.000
                                                                                15.25 % Impto. Retenido:                        15.250
                                                                                                   Total:                       84.750
        """
        normalized = parse_tax_document(
            pdf_bytes=b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF",
            pdf_name="honorarios.pdf",
            organizacion_id=self.org.pk,
        )

        self.assertEqual(normalized.get_value("encabezado", "tipo_documento_sugerido"), "boleta_honorarios")
        self.assertEqual(normalized.get_value("encabezado", "folio"), "125")
        self.assertEqual(normalized.get_value("encabezado", "fecha_emision"), "2026-03-12")
        self.assertEqual(normalized.get_value("emisor", "razon_social"), "ALVARO FRANCISCO VARGAS QUEZADA")
        self.assertEqual(normalized.get_value("emisor", "rut"), "17.085.005-K")
        self.assertEqual(normalized.get_value("receptor", "razon_social"), "ESPACIO CULTURAL Y DEPORTIVO ELEMENTOS SPA")
        self.assertEqual(normalized.get_value("receptor", "rut"), "77.813.508-6")
        self.assertEqual(normalized.get_value("montos", "neto"), Decimal("100000"))
        self.assertEqual(normalized.get_value("montos", "retencion_honorarios"), Decimal("15250"))
        self.assertEqual(normalized.get_value("montos", "porcentaje_retencion"), Decimal("15.25"))
        self.assertEqual(normalized.get_value("montos", "total_liquido"), Decimal("84750"))
        self.assertEqual(normalized.get_value("montos", "total_bruto"), Decimal("100000"))
        self.assertEqual(normalized.lineas[0].fields["descripcion"].value, "FUNCION LA TAREA MAS DIFICIL - FEBRERO - 2026")

    def test_form_edicion_pago_renderiza_fecha_iso_para_input_date(self):
        pago = Payment.objects.create(
            persona=self.estudiante,
            organizacion=self.org,
            fecha_pago="2026-02-28",
            metodo_pago=Payment.Metodo.EFECTIVO,
            aplica_iva=False,
            monto_referencia=10000,
            clases_asignadas=1,
        )
        form = PaymentForm(instance=pago)
        html = form["fecha_pago"].as_widget()
        self.assertIn('value="2026-02-28"', html)

    def test_form_edicion_documento_tributario_renderiza_fecha_iso_para_input_date(self):
        documento = DocumentoTributario.objects.create(
            organizacion=self.org,
            tipo_documento=DocumentoTributario.TipoDocumento.FACTURA_EXENTA,
            fuente=DocumentoTributario.Fuente.MANUAL,
            folio="502",
            fecha_emision="2026-03-10",
            nombre_emisor="Emisor",
            rut_emisor="11.111.111-1",
            nombre_receptor="Receptor",
            rut_receptor="22.222.222-2",
            monto_neto=0,
            monto_exento=500000,
            monto_iva=0,
            monto_total=500000,
        )
        form = DocumentoTributarioForm(instance=documento)
        html = form["fecha_emision"].as_widget()
        self.assertIn('value="2026-03-10"', html)

    def test_documento_tributario_form_acepta_montos_con_punto_como_miles(self):
        form = DocumentoTributarioForm(
            data={
                "organizacion": self.org.pk,
                "tipo_documento": DocumentoTributario.TipoDocumento.FACTURA_EXENTA,
                "fuente": DocumentoTributario.Fuente.MANUAL,
                "folio": "501",
                "fecha_emision": "2026-03-10",
                "nombre_emisor": "Emisor",
                "rut_emisor": "11.111.111-1",
                "nombre_receptor": "Receptor",
                "rut_receptor": "22.222.222-2",
                "monto_neto": "0",
                "monto_exento": "500.000",
                "iva_tasa": "0",
                "monto_iva": "0",
                "retencion_tasa": "0",
                "retencion_monto": "0",
                "monto_total": "500.000",
                "metadata_extra": "{}",
                "observaciones": "",
            }
        )

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["monto_exento"], Decimal("500000"))
        self.assertEqual(form.cleaned_data["monto_total"], Decimal("500000"))

    def test_pagos_list_muestra_resumen_compilado_del_listado(self):
        self.client.force_login(self.user_admin)

        pago_1 = Payment.objects.create(
            persona=self.estudiante,
            organizacion=self.org,
            fecha_pago="2026-02-25",
            metodo_pago=Payment.Metodo.EFECTIVO,
            aplica_iva=False,
            monto_referencia=10000,
            clases_asignadas=2,
        )
        Payment.objects.create(
            persona=self.estudiante,
            organizacion=self.org,
            fecha_pago="2026-02-28",
            metodo_pago=Payment.Metodo.TRANSFERENCIA,
            numero_comprobante="ABC123",
            aplica_iva=False,
            monto_referencia=15000,
            clases_asignadas=3,
        )
        Payment.objects.create(
            persona=self.estudiante,
            organizacion=self.org,
            fecha_pago="2026-03-02",
            metodo_pago=Payment.Metodo.EFECTIVO,
            aplica_iva=False,
            monto_referencia=5000,
            clases_asignadas=1,
        )

        asistencia = Asistencia.objects.create(sesion=self.sesion_1, persona=self.estudiante)
        consumo = AttendanceConsumption.objects.get(asistencia=asistencia)
        self.assertEqual(consumo.pago, pago_1)

        response = self.client.get(
            reverse("finanzas:pagos_list"),
            {"periodo_mes": 2, "periodo_anio": 2026, "organizacion": self.org.pk},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["total_pagos_monto"], 25000)
        self.assertEqual(response.context["total_clases_pagadas"], 5)
        self.assertEqual(response.context["total_saldo_clases"], 4)

    def test_pagos_list_muestra_estado_fiscal_y_texto_copiable(self):
        self.client.force_login(self.user_admin)
        plan = PaymentPlan.objects.create(
            organizacion=self.org,
            nombre="Plan Mensual",
            num_clases=4,
            precio=10000,
            activo=True,
        )
        Payment.objects.create(
            persona=self.estudiante,
            organizacion=self.org,
            plan=plan,
            fecha_pago="2026-02-25",
            metodo_pago=Payment.Metodo.EFECTIVO,
            aplica_iva=True,
            monto_incluye_iva=False,
            monto_referencia=10000,
            clases_asignadas=4,
        )
        Payment.objects.create(
            persona=self.estudiante,
            organizacion=self.org,
            fecha_pago="2026-02-26",
            metodo_pago=Payment.Metodo.EFECTIVO,
            aplica_iva=False,
            monto_referencia=8000,
            clases_asignadas=1,
        )
        disciplina_secundaria = Disciplina.objects.create(
            organizacion=self.org,
            nombre="Pilates",
        )
        sesion_pilates = SesionClase.objects.create(
            disciplina=disciplina_secundaria,
            fecha="2026-02-24",
            estado=SesionClase.Estado.PROGRAMADA,
        )
        Asistencia.objects.create(sesion=self.sesion_1, persona=self.estudiante)
        Asistencia.objects.create(sesion=self.sesion_2, persona=self.estudiante)
        Asistencia.objects.create(sesion=sesion_pilates, persona=self.estudiante)
        Asistencia.objects.filter(sesion=sesion_pilates, persona=self.estudiante).update(
            estado=Asistencia.Estado.AUSENTE
        )

        response = self.client.get(
            reverse("finanzas:pagos_list"),
            {"periodo_mes": 2, "periodo_anio": 2026, "organizacion": self.org.pk},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Haz clic sobre los montos de neto, IVA o bruto para copiar el valor sin puntos.")
        self.assertContains(response, "<th>IVA</th>", html=False)
        self.assertNotContains(response, "<th>Organizacion</th>", html=False)
        self.assertContains(response, "Afecta")
        self.assertContains(response, "Exenta")
        self.assertContains(response, "11.900")
        self.assertContains(response, "10.000")
        self.assertContains(response, "1.900")
        self.assertContains(response, "8.000")
        self.assertContains(response, "bi-chat-text", html=False)
        self.assertContains(response, 'data-copy-value="10000"', html=False)
        self.assertContains(response, 'data-copy-value="1900"', html=False)
        self.assertContains(response, 'data-copy-value="11900"', html=False)
        self.assertContains(response, 'title="$ 11.900 · clic para copiar 11900"', html=False)
        self.assertContains(
            response,
            'data-copy-text="Taller de Yoga - Plan Mensual (Ana Diaz)"',
            html=False,
        )
        self.assertContains(
            response,
            'title="Taller de Yoga - Plan Mensual (Ana Diaz) · clic para copiar"',
            html=False,
        )

        pago = next(item for item in response.context["pagos"] if item.plan_id)
        self.assertEqual(pago.disciplina_principal_nombre, "Yoga")
        self.assertEqual(pago.texto_copia, "Taller de Yoga - Plan Mensual (Ana Diaz)")

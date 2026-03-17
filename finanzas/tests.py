from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from decimal import Decimal

from finanzas.documentos.services import parse_tax_document
from finanzas.forms import PaymentForm

from database.models import (
    Asistencia,
    AttendanceConsumption,
    Category,
    DocumentoTributario,
    Disciplina,
    Organizacion,
    Payment,
    PaymentPlan,
    Persona,
    PersonaRol,
    Rol,
    SesionClase,
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

        response = self.client.post(
            reverse("finanzas:documento_tributario_importar"),
            {"accion": "parsear", "archivo_xml": xml},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Revision del documento tributario")
        self.assertContains(response, "101")
        self.assertEqual(DocumentoTributario.objects.count(), 0)


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

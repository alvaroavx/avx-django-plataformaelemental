import hashlib
import io
import re
import xml.etree.ElementTree as ET
from decimal import Decimal, InvalidOperation

from .dtos import NormalizedTaxDocument, NormalizedTaxLine

try:
    from pypdf import PdfReader
except Exception:  # pragma: no cover - dependencia opcional
    PdfReader = None


def _text(element):
    return (element.text or "").strip() if element is not None and element.text is not None else ""


def _local_name(tag):
    return tag.split("}", 1)[-1]


def _find_child(element, child_name):
    if element is None:
        return None
    for child in element:
        if _local_name(child.tag) == child_name:
            return child
    return None


def _find_descendant(element, *names):
    current = element
    for name in names:
        current = _find_child(current, name)
        if current is None:
            return None
    return current


def _find_all_descendants(element, name):
    return [child for child in element.iter() if _local_name(child.tag) == name]


def _decimal(value):
    if value in (None, ""):
        return None
    raw = str(value).strip()
    raw = raw.replace("$", "").replace(" ", "")
    if "," in raw and "." in raw:
        raw = raw.replace(".", "").replace(",", ".")
    elif "," in raw:
        raw = raw.replace(".", "").replace(",", ".")
    try:
        return Decimal(raw)
    except (InvalidOperation, ValueError):
        return None


def _filename_hash(content):
    return hashlib.sha256(content).hexdigest()


def _document_category_from_dte(tipo_dte):
    mapping = {
        "33": ("invoice", "factura electrónica", "factura_afecta"),
        "34": ("invoice", "factura exenta", "factura_exenta"),
        "39": ("sales_receipt", "boleta de venta electrónica", "boleta_venta_afecta"),
        "41": ("sales_receipt", "boleta de venta exenta", "boleta_venta_exenta"),
        "61": ("credit_note", "nota de credito", "nota_credito"),
        "56": ("other", "nota de debito", "nota_debito"),
    }
    return mapping.get(str(tipo_dte), ("other", "documento tributario", "otro"))


class BaseTaxDocumentParser:
    parser_name = "base"

    def parse(self, *, xml_bytes=None, pdf_bytes=None, xml_name=None, pdf_name=None):
        raise NotImplementedError


class DteXmlParser(BaseTaxDocumentParser):
    parser_name = "xml_dte"

    def parse(self, *, xml_bytes=None, pdf_bytes=None, xml_name=None, pdf_name=None):
        root = ET.fromstring(xml_bytes)
        documento_node = next(
            (
                node
                for node in root.iter()
                if _local_name(node.tag) == "Documento" and _find_child(node, "Encabezado") is not None
            ),
            None,
        )
        if documento_node is None:
            raise ValueError("No se encontro un nodo Documento valido en el XML DTE.")

        encabezado = _find_child(documento_node, "Encabezado")
        id_doc = _find_child(encabezado, "IdDoc")
        emisor = _find_child(encabezado, "Emisor")
        receptor = _find_child(encabezado, "Receptor")
        totales = _find_child(encabezado, "Totales")

        tipo_dte = _text(_find_child(id_doc, "TipoDTE"))
        categoria, nombre_legible, tipo_documento = _document_category_from_dte(tipo_dte)

        normalized = NormalizedTaxDocument()
        normalized.set_field("encabezado", "tipo_tributario", tipo_dte, "xml", "high")
        normalized.set_field("encabezado", "categoria_documental", categoria, "xml", "high")
        normalized.set_field("encabezado", "nombre_legible", nombre_legible, "xml", "high")
        normalized.set_field("encabezado", "tipo_documento_sugerido", tipo_documento, "xml", "high")
        normalized.set_field("encabezado", "folio", _text(_find_child(id_doc, "Folio")), "xml", "high")
        normalized.set_field("encabezado", "fecha_emision", _text(_find_child(id_doc, "FchEmis")), "xml", "high")
        normalized.set_field(
            "encabezado",
            "fecha_generacion",
            _text(next((n for n in root.iter() if _local_name(n.tag) == "TmstFirmaEnv"), None)),
            "xml",
            "medium",
        )
        normalized.set_field("encabezado", "moneda", "CLP", "inferred", "medium")
        normalized.set_field(
            "encabezado",
            "indicador_exento",
            bool(_text(_find_child(totales, "MntExe")) and _text(_find_child(totales, "MntExe")) != "0"),
            "xml",
            "high",
        )

        normalized.set_field("emisor", "rut", _text(_find_child(emisor, "RUTEmisor")), "xml", "high")
        normalized.set_field("emisor", "razon_social", _text(_find_child(emisor, "RznSoc")), "xml", "high")
        normalized.set_field("emisor", "giro", _text(_find_child(emisor, "GiroEmis")), "xml", "medium")
        normalized.set_field("emisor", "direccion", _text(_find_child(emisor, "DirOrigen")), "xml", "medium")
        normalized.set_field("emisor", "comuna", _text(_find_child(emisor, "CmnaOrigen")), "xml", "medium")
        normalized.set_field("emisor", "ciudad", _text(_find_child(emisor, "CiudadOrigen")), "xml", "medium")
        normalized.set_field("emisor", "email", _text(_find_child(emisor, "CorreoEmisor")), "xml", "low")

        normalized.set_field("receptor", "rut", _text(_find_child(receptor, "RUTRecep")), "xml", "high")
        normalized.set_field("receptor", "razon_social", _text(_find_child(receptor, "RznSocRecep")), "xml", "high")
        normalized.set_field("receptor", "giro", _text(_find_child(receptor, "GiroRecep")), "xml", "medium")
        normalized.set_field("receptor", "direccion", _text(_find_child(receptor, "DirRecep")), "xml", "medium")
        normalized.set_field("receptor", "comuna", _text(_find_child(receptor, "CmnaRecep")), "xml", "medium")
        normalized.set_field("receptor", "ciudad", _text(_find_child(receptor, "CiudadRecep")), "xml", "medium")
        normalized.set_field("receptor", "email", _text(_find_child(receptor, "CorreoRecep")), "xml", "low")

        normalized.set_field("montos", "neto", _decimal(_text(_find_child(totales, "MntNeto"))), "xml", "high")
        normalized.set_field("montos", "exento", _decimal(_text(_find_child(totales, "MntExe"))), "xml", "high")
        normalized.set_field("montos", "iva", _decimal(_text(_find_child(totales, "IVA"))), "xml", "high")
        normalized.set_field("montos", "tasa_iva", _decimal(_text(_find_child(totales, "TasaIVA"))), "xml", "high")
        normalized.set_field("montos", "retencion_honorarios", None, "inferred", "low")
        normalized.set_field("montos", "porcentaje_retencion", None, "inferred", "low")
        normalized.set_field("montos", "total_liquido", None, "inferred", "low")
        normalized.set_field("montos", "total_bruto", _decimal(_text(_find_child(totales, "MntTotal"))), "xml", "high")

        for detalle in _find_all_descendants(documento_node, "Detalle"):
            linea = NormalizedTaxLine()
            nro_linea = _text(_find_child(detalle, "NroLinDet"))
            nombre_item = _text(_find_child(detalle, "NmbItem"))
            descripcion = _text(_find_child(detalle, "DscItem")) or nombre_item
            codigo_node = _find_child(detalle, "CdgItem")
            codigo = _text(_find_child(codigo_node, "VlrCodigo")) or _text(_find_child(codigo_node, "TpoCodigo"))
            linea.set_field("numero_linea", nro_linea or len(normalized.lineas) + 1, "xml", "high")
            linea.set_field("codigo", codigo, "xml", "medium")
            linea.set_field("descripcion", descripcion, "xml", "high")
            linea.set_field("cantidad", _decimal(_text(_find_child(detalle, "QtyItem"))), "xml", "medium")
            linea.set_field("precio_unitario", _decimal(_text(_find_child(detalle, "PrcItem"))), "xml", "medium")
            linea.set_field("descuento", _decimal(_text(_find_child(detalle, "DescuentoMonto"))), "xml", "medium")
            linea.set_field("recargo", _decimal(_text(_find_child(detalle, "RecargoMonto"))), "xml", "medium")
            linea.set_field("subtotal_linea", _decimal(_text(_find_child(detalle, "MontoItem"))), "xml", "high")
            normalized.lineas.append(linea)

        normalized.set_field("metadata_archivo", "nombre_archivo", xml_name, "xml", "high")
        normalized.set_field("metadata_archivo", "tipo_mime", "application/xml", "inferred", "high")
        normalized.set_field("metadata_archivo", "extension", "xml", "inferred", "high")
        normalized.set_field("metadata_archivo", "hash", _filename_hash(xml_bytes), "xml", "high")
        normalized.set_field("metadata_archivo", "formato_origen", "xml_dte", "xml", "high")
        normalized.set_field("metadata_archivo", "parser_usado", self.parser_name, "xml", "high")
        normalized.set_field("metadata_archivo", "fuente_principal", "xml", "xml", "high")
        return normalized


class BheXmlParser(BaseTaxDocumentParser):
    parser_name = "xml_bhe"

    def parse(self, *, xml_bytes=None, pdf_bytes=None, xml_name=None, pdf_name=None):
        root = ET.fromstring(xml_bytes)
        normalized = NormalizedTaxDocument()

        tipo_doc = _text(_find_child(root, "tipodoc")) or "bhe"
        normalized.set_field("encabezado", "tipo_tributario", tipo_doc, "xml", "high")
        normalized.set_field("encabezado", "categoria_documental", "fee_receipt", "xml", "high")
        normalized.set_field("encabezado", "nombre_legible", "boleta de honorarios electrónica", "xml", "high")
        normalized.set_field("encabezado", "tipo_documento_sugerido", "boleta_honorarios", "xml", "high")
        normalized.set_field("encabezado", "folio", _text(_find_child(root, "numeroBoleta")), "xml", "high")
        normalized.set_field("encabezado", "fecha_emision", _text(_find_child(root, "fechaBoleta")), "xml", "high")
        normalized.set_field("encabezado", "fecha_generacion", None, "inferred", "low")
        normalized.set_field("encabezado", "moneda", "CLP", "inferred", "medium")
        normalized.set_field("encabezado", "indicador_exento", False, "inferred", "medium")

        rut_emisor = _text(_find_child(root, "rutEmisor"))
        dv_emisor = _text(_find_child(root, "dvEmisor"))
        rut_receptor = _text(_find_child(root, "rutReceptor"))
        dv_receptor = _text(_find_child(root, "dvReceptor"))
        normalized.set_field("emisor", "rut", f"{rut_emisor}-{dv_emisor}" if rut_emisor and dv_emisor else rut_emisor, "xml", "high")
        normalized.set_field("emisor", "razon_social", _text(_find_child(root, "nombreEmisor")), "xml", "medium")
        normalized.set_field("emisor", "giro", _text(_find_child(root, "actividadEconomica")), "xml", "medium")
        normalized.set_field("emisor", "direccion", _text(_find_child(root, "domicilioEmisor")), "xml", "medium")
        normalized.set_field("receptor", "rut", f"{rut_receptor}-{dv_receptor}" if rut_receptor and dv_receptor else rut_receptor, "xml", "high")
        normalized.set_field("receptor", "razon_social", _text(_find_child(root, "nombreReceptor")), "xml", "high")
        normalized.set_field("receptor", "direccion", _text(_find_child(root, "domicilioReceptor")), "xml", "medium")

        total_honorarios = _decimal(_text(_find_child(root, "totalHonorarios")))
        impuesto = _decimal(_text(_find_child(root, "impuestoHonorarios")))
        liquido = _decimal(_text(_find_child(root, "liquidoHonorarios")))
        porcentaje = _decimal(_text(_find_child(root, "porcentajeImpuesto")))
        normalized.set_field("montos", "neto", total_honorarios, "xml", "high")
        normalized.set_field("montos", "exento", None, "inferred", "low")
        normalized.set_field("montos", "iva", Decimal("0"), "inferred", "high")
        normalized.set_field("montos", "tasa_iva", Decimal("0"), "inferred", "high")
        normalized.set_field("montos", "retencion_honorarios", impuesto, "xml", "high")
        normalized.set_field("montos", "porcentaje_retencion", porcentaje, "xml", "high")
        normalized.set_field("montos", "total_liquido", liquido, "xml", "high")
        normalized.set_field("montos", "total_bruto", total_honorarios, "xml", "high")

        items = _find_all_descendants(root, "item")
        for index, item in enumerate(items, start=1):
            descripcion = _text(item)
            if not descripcion:
                continue
            linea = NormalizedTaxLine()
            linea.set_field("numero_linea", index, "xml", "high")
            linea.set_field("descripcion", descripcion, "xml", "high")
            if index == 1 and total_honorarios is not None:
                linea.set_field("subtotal_linea", total_honorarios, "xml", "medium")
            normalized.lineas.append(linea)

        if not normalized.lineas and total_honorarios is not None:
            linea = NormalizedTaxLine()
            linea.set_field("numero_linea", 1, "inferred", "medium")
            linea.set_field("descripcion", "Prestacion de servicios", "inferred", "medium")
            linea.set_field("subtotal_linea", total_honorarios, "xml", "high")
            normalized.lineas.append(linea)

        normalized.set_field("metadata_archivo", "nombre_archivo", xml_name, "xml", "high")
        normalized.set_field("metadata_archivo", "tipo_mime", "application/xml", "inferred", "high")
        normalized.set_field("metadata_archivo", "extension", "xml", "inferred", "high")
        normalized.set_field("metadata_archivo", "hash", _filename_hash(xml_bytes), "xml", "high")
        normalized.set_field("metadata_archivo", "formato_origen", "xml_bhe", "xml", "high")
        normalized.set_field("metadata_archivo", "parser_usado", self.parser_name, "xml", "high")
        normalized.set_field("metadata_archivo", "fuente_principal", "xml", "xml", "high")
        return normalized


class PdfFallbackParser(BaseTaxDocumentParser):
    parser_name = "pdf_fallback"

    def parse(self, *, xml_bytes=None, pdf_bytes=None, pdf_name=None, xml_name=None):
        normalized = NormalizedTaxDocument()
        normalized.set_field("metadata_archivo", "nombre_archivo", pdf_name, "pdf", "high")
        normalized.set_field("metadata_archivo", "tipo_mime", "application/pdf", "inferred", "high")
        normalized.set_field("metadata_archivo", "extension", "pdf", "inferred", "high")
        normalized.set_field("metadata_archivo", "hash", _filename_hash(pdf_bytes), "pdf", "high")
        normalized.set_field("metadata_archivo", "formato_origen", "pdf", "pdf", "high")
        normalized.set_field("metadata_archivo", "parser_usado", self.parser_name, "pdf", "high")
        normalized.set_field("metadata_archivo", "fuente_principal", "pdf", "pdf", "high")
        normalized.set_field("encabezado", "categoria_documental", "other", "inferred", "low")
        normalized.set_field("encabezado", "nombre_legible", "documento desde PDF", "inferred", "low")
        normalized.set_field("encabezado", "tipo_documento_sugerido", "otro", "inferred", "low")
        normalized.set_field("encabezado", "moneda", "CLP", "inferred", "medium")
        if PdfReader is None:
            normalized.warnings.append("No hay parser PDF instalado; se requiere revision manual completa.")
            return normalized

        try:
            reader = PdfReader(io.BytesIO(pdf_bytes))
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
        except Exception:
            normalized.errors.append("No se pudo leer el PDF. Si es escaneado, la revision debe ser manual.")
            return normalized

        if not text.strip():
            normalized.errors.append("El PDF no contiene texto seleccionable util para parsear.")
            return normalized

        upper = text.upper()
        if "HONORARIOS" in upper:
            categoria = "fee_receipt"
            nombre_legible = "boleta de honorarios"
            tipo_documento = "boleta_honorarios"
        elif "FACTURA" in upper:
            categoria = "invoice"
            nombre_legible = "factura"
            tipo_documento = "factura_afecta"
        elif "BOLETA" in upper:
            categoria = "sales_receipt"
            nombre_legible = "boleta de venta"
            tipo_documento = "boleta_venta_afecta"
        else:
            categoria = "other"
            nombre_legible = "documento tributario"
            tipo_documento = "otro"
        normalized.set_field("encabezado", "categoria_documental", categoria, "pdf", "medium")
        normalized.set_field("encabezado", "nombre_legible", nombre_legible, "pdf", "medium")
        normalized.set_field("encabezado", "tipo_documento_sugerido", tipo_documento, "pdf", "medium")

        folio_match = re.search(r"(FOLIO|N[ÚU]MERO|NUMERO)\s*[:#]?\s*([A-Z0-9\-]+)", upper)
        total_match = re.search(r"TOTAL\s*[:$]?\s*([\d\.\,]+)", upper)
        rut_matches = re.findall(r"\b\d{1,3}(?:\.\d{3}){2}-[\dkK]\b|\b\d{7,8}-[\dkK]\b", text)
        if folio_match:
            normalized.set_field("encabezado", "folio", folio_match.group(2), "pdf", "medium")
        if total_match:
            normalized.set_field("montos", "total_bruto", _decimal(total_match.group(1)), "pdf", "medium")
        if rut_matches:
            normalized.set_field("emisor", "rut", rut_matches[0], "pdf", "low")
            if len(rut_matches) > 1:
                normalized.set_field("receptor", "rut", rut_matches[1], "pdf", "low")
        normalized.warnings.append("Parser PDF basico aplicado; revisa todos los campos antes de confirmar.")
        return normalized


def detectar_familia_xml(xml_bytes):
    root = ET.fromstring(xml_bytes)
    root_name = _local_name(root.tag).lower()
    all_tags = {_local_name(node.tag) for node in root.iter()}
    if "Documento" in all_tags and "Encabezado" in all_tags:
        return "dte"
    if root_name == "datos" or "numeroBoleta" in all_tags:
        return "bhe"
    return "desconocido"

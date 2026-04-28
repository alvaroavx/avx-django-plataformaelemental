import hashlib
import io
import re
import subprocess
import tempfile
import unicodedata
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


def _money_decimal(value):
    if value in (None, ""):
        return None
    raw = str(value).strip()
    raw = raw.replace("$", "").replace(" ", "")
    if "," in raw:
        raw = raw.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"\d{1,3}(?:\.\d{3})+", raw):
        raw = raw.replace(".", "")
    try:
        return Decimal(raw)
    except (InvalidOperation, ValueError):
        return None


def _parse_spanish_date(value):
    if not value:
        return None
    raw = re.sub(r"\s+", " ", str(value).strip().lower())
    meses = {
        "enero": 1,
        "febrero": 2,
        "marzo": 3,
        "abril": 4,
        "mayo": 5,
        "junio": 6,
        "julio": 7,
        "agosto": 8,
        "septiembre": 9,
        "setiembre": 9,
        "octubre": 10,
        "noviembre": 11,
        "diciembre": 12,
    }
    match = re.search(r"(\d{1,2})\s+de\s+([a-záéíóúñ]+)\s+del?\s+(\d{4})", raw, flags=re.IGNORECASE)
    if not match:
        return None
    dia = int(match.group(1))
    mes = meses.get(match.group(2))
    anio = int(match.group(3))
    if not mes:
        return None
    return f"{anio:04d}-{mes:02d}-{dia:02d}"


def _fold_text(value):
    normalized = unicodedata.normalize("NFKD", value or "")
    return "".join(char for char in normalized if not unicodedata.combining(char)).upper()


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

    @staticmethod
    def _normalize_pdf_text(text):
        return (
            (text or "")
            .replace("\xa0", " ")
            .replace("−", "-")
            .replace("–", "-")
            .replace("—", "-")
        )

    @staticmethod
    def _extract_text_with_pypdf(pdf_bytes):
        if PdfReader is None:
            return ""
        try:
            reader = PdfReader(io.BytesIO(pdf_bytes))
            return "\n".join(page.extract_text() or "" for page in reader.pages)
        except Exception:
            return ""

    @staticmethod
    def _extract_text_with_pdftotext(pdf_bytes):
        try:
            with tempfile.NamedTemporaryFile(suffix=".pdf") as tmp_pdf:
                tmp_pdf.write(pdf_bytes)
                tmp_pdf.flush()
                result = subprocess.run(
                    ["pdftotext", "-layout", tmp_pdf.name, "-"],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if result.returncode == 0:
                    return result.stdout or ""
        except Exception:
            return ""
        return ""

    @staticmethod
    def _join_wrapped_lines(parts):
        resultado = []
        for parte in parts:
            texto = re.sub(r"\s+", " ", (parte or "")).strip()
            if not texto:
                continue
            if resultado and resultado[-1] and resultado[-1][-1].isalpha() and texto[0].islower():
                resultado[-1] = f"{resultado[-1]}{texto}"
            else:
                resultado.append(texto)
        return " ".join(resultado).strip()

    @staticmethod
    def _parse_fee_receipt_pdf(text, normalized):
        raw_lines = [line.rstrip() for line in text.splitlines() if line.strip()]
        lines = [re.sub(r"\s+", " ", line).strip() for line in raw_lines]

        first_title_line = next(
            (
                line
                for line in raw_lines
                if "ELECTRONICA" in _fold_text(line) and re.split(r"\s{3,}", line.strip())[0].strip()
            ),
            "",
        )
        if not first_title_line:
            first_title_line = next(
            (
                line
                for line in raw_lines
                if "BOLETA DE HONORARIOS" in _fold_text(line) or "ELECTRONICA" in _fold_text(line)
            ),
            "",
        )
        if first_title_line:
            partes = re.split(r"\s{3,}", first_title_line.strip())
            if partes and partes[0].strip() and "ELECTRONICA" not in _fold_text(partes[0]) and "BOLETA DE HONORARIOS" not in _fold_text(partes[0]):
                normalized.set_field("emisor", "razon_social", partes[0].strip(), "pdf", "medium")

        if not normalized.get_value("emisor", "razon_social"):
            rut_index = next((idx for idx, line in enumerate(lines) if line.upper().startswith("RUT:")), None)
            if rut_index:
                nombre_idx = rut_index - 1
                if nombre_idx >= 0 and not re.search(r"\bN\s*[°ºoO]?\s*\d+\b", lines[nombre_idx], flags=re.IGNORECASE):
                    normalized.set_field("emisor", "razon_social", lines[nombre_idx], "pdf", "medium")

        folio_line = next((line for line in lines if re.search(r"\bN\s*[°ºoO]?\s*[0-9]+\b", line, flags=re.IGNORECASE)), "")
        if folio_line:
            folio_match = re.search(r"\bN\s*[°ºoO]?\s*([0-9]+)\b", folio_line, flags=re.IGNORECASE)
            if folio_match:
                normalized.set_field("encabezado", "folio", folio_match.group(1), "pdf", "high")

        fecha_match = re.search(
            r"Fecha:\s*([0-9]{1,2}\s+de\s+[A-Za-zÁÉÍÓÚáéíóúñÑ]+\s+de\s+[0-9]{4})",
            text,
            flags=re.IGNORECASE,
        )
        if fecha_match:
            fecha_raw = fecha_match.group(1).strip()
            fecha_iso = _parse_spanish_date(fecha_raw) or fecha_raw
            normalized.set_field("encabezado", "fecha_emision", fecha_iso, "pdf", "high")

        emisor_rut_match = re.search(r"RUT:\s*([0-9\.\-Kk ]+)", text, flags=re.IGNORECASE)
        if emisor_rut_match:
            normalized.set_field(
                "emisor",
                "rut",
                re.sub(r"\s+", "", emisor_rut_match.group(1).strip()).upper(),
                "pdf",
                "high",
            )

        giro_index = next((idx for idx, line in enumerate(lines) if line.upper().startswith("GIRO")), None)
        if giro_index is not None:
            giro_lines = []
            for idx in range(giro_index, len(lines)):
                line = lines[idx]
                upper_line = line.upper()
                if idx == giro_index:
                    giro_lines.append(line.split(":", 1)[1].strip() if ":" in line else line)
                    continue
                if upper_line.startswith("TELEFONO") or upper_line.startswith("FECHA:") or upper_line.startswith("SEÑOR(ES)"):
                    break
                if upper_line.startswith("RUT:"):
                    continue
                giro_lines.append(line)
            if giro_lines:
                giro_texto = []
                direccion = ""
                for line in giro_lines:
                    if any(char.isdigit() for char in line):
                        direccion = line
                    else:
                        giro_texto.append(line)
                if giro_texto:
                    normalized.set_field("emisor", "giro", ", ".join(giro_texto).strip(", "), "pdf", "medium")
                if direccion:
                    normalized.set_field("emisor", "direccion", direccion, "pdf", "low")

        receptor_match = re.search(
            r"Señor\(es\):\s*(.+?)\s+Rut:\s*([0-9\.\-Kk ]+)",
            text,
            flags=re.IGNORECASE,
        )
        if receptor_match:
            normalized.set_field("receptor", "razon_social", receptor_match.group(1).strip(), "pdf", "high")
            normalized.set_field(
                "receptor",
                "rut",
                re.sub(r"\s+", "", receptor_match.group(2).strip()).upper(),
                "pdf",
                "high",
            )
        domicilio_match = re.search(r"Domicilio:\s*(.+)", text, flags=re.IGNORECASE)
        if domicilio_match:
            normalized.set_field("receptor", "direccion", domicilio_match.group(1).strip(), "pdf", "medium")

        honorarios_match = re.search(
            r"Total\s+Honorarios:\s*\$?:?\s*([\d\.\,]+)",
            text,
            flags=re.IGNORECASE,
        )
        retencion_match = re.search(
            r"([0-9]+(?:\.[0-9]+)?)\s*%\s*Impto\.?\s*Retenido:\s*([\d\.\,]+)",
            text,
            flags=re.IGNORECASE,
        )
        total_liquido_match = re.search(r"\bTotal:\s*([\d\.\,]+)", text, flags=re.IGNORECASE)
        if honorarios_match:
            total_honorarios = _money_decimal(honorarios_match.group(1))
            normalized.set_field("montos", "neto", total_honorarios, "pdf", "high")
            normalized.set_field("montos", "iva", Decimal("0"), "inferred", "high")
            normalized.set_field("montos", "tasa_iva", Decimal("0"), "inferred", "high")
            normalized.set_field("montos", "total_bruto", total_honorarios, "pdf", "high")
        if retencion_match:
            normalized.set_field("montos", "porcentaje_retencion", _decimal(retencion_match.group(1)), "pdf", "high")
            normalized.set_field("montos", "retencion_honorarios", _money_decimal(retencion_match.group(2)), "pdf", "high")
        if total_liquido_match:
            normalized.set_field("montos", "total_liquido", _money_decimal(total_liquido_match.group(1)), "pdf", "high")

        detalle_inicio = next(
            (idx for idx, line in enumerate(lines) if _fold_text(line).startswith("POR ATENCION PROFESIONAL")),
            None,
        )
        if detalle_inicio is not None:
            detalle_lineas = []
            for idx in range(detalle_inicio + 1, len(lines)):
                line = lines[idx]
                upper_line = _fold_text(line)
                if upper_line.startswith("TOTAL HONORARIOS") or upper_line.startswith("FECHA / HORA"):
                    break
                if upper_line.startswith("EL CONTRIBUYENTE") or upper_line.startswith("RES. EX."):
                    break
                if line:
                    detalle_lineas.append(line)
            if detalle_lineas:
                descripcion = " ".join(re.sub(r"\s+[\d\.\,]+$", "", line).strip() for line in detalle_lineas).strip()
                descripcion = re.sub(r"\s+", " ", descripcion).strip()
                monto_linea = normalized.get_value("montos", "total_bruto")
                linea = NormalizedTaxLine()
                linea.set_field("numero_linea", 1, "pdf", "medium")
                linea.set_field("descripcion", descripcion, "pdf", "high")
                linea.set_field("cantidad", Decimal("1"), "inferred", "medium")
                linea.set_field("precio_unitario", monto_linea, "pdf", "medium")
                linea.set_field("subtotal_linea", monto_linea, "pdf", "medium")
                normalized.lineas.append(linea)

    @staticmethod
    def _parse_sales_receipt_pdf(text, normalized):
        raw_lines = [line.rstrip() for line in text.splitlines() if line.strip()]
        lines = [re.sub(r"\s+", " ", line).strip() for line in raw_lines]
        es_exenta = normalized.get_value("encabezado", "tipo_documento_sugerido") == "boleta_venta_exenta"
        normalized.set_field("encabezado", "tipo_tributario", "41" if es_exenta else "39", "pdf", "high")

        folio_match = re.search(
            r"BOLETA(?:\s+EXENTA)?\s+ELECTR[ÓO]NICA\s+NUMERO:\s*([\d\.\,]+)",
            text,
            flags=re.IGNORECASE,
        )
        if not folio_match:
            folio_match = re.search(
                r"BOLETA(?:\s+EXENTA)?\s+ELECTR[ÓO]NICA\s+NUMERO:\s*\n+\s*([\d\.\,]+)",
                text,
                flags=re.IGNORECASE,
            )
        if folio_match:
            folio = re.sub(r"\D", "", folio_match.group(1))
            if folio:
                normalized.set_field("encabezado", "folio", folio, "pdf", "high")

        fecha_match = re.search(r"Fecha:\s*([0-9]{4}-[0-9]{2}-[0-9]{2})", text, flags=re.IGNORECASE)
        if fecha_match:
            normalized.set_field("encabezado", "fecha_emision", fecha_match.group(1), "pdf", "high")

        rut_index = next(
            (
                idx
                for idx, line in enumerate(lines)
                if re.fullmatch(r"\d{1,3}(?:\.\d{3}){2}-\s*[\dkK]|\d{7,8}-\s*[\dkK]", line)
            ),
            None,
        )
        if rut_index is not None:
            emisor_rut = re.sub(r"\s+", "", lines[rut_index]).upper()
            normalized.set_field("emisor", "rut", emisor_rut, "pdf", "high")
            nombre_emisor = " ".join(item for item in lines[:rut_index] if item).strip()
            if nombre_emisor:
                normalized.set_field("emisor", "razon_social", nombre_emisor, "pdf", "high")

        giro_index = next((idx for idx, line in enumerate(lines) if line.upper().startswith("GIRO:")), None)
        if giro_index is not None:
            giro_lines = []
            for idx in range(giro_index, len(lines)):
                line = lines[idx]
                upper_line = line.upper()
                if upper_line.startswith("BOLETA ELECTR"):
                    break
                if idx == giro_index:
                    giro_lines.append(line.split(":", 1)[1].strip() if ":" in line else line)
                    continue
                giro_lines.append(line)
            if giro_lines:
                normalized.set_field("emisor", "giro", " ".join(giro_lines).strip(), "pdf", "medium")

        direccion_index = next((idx for idx, line in enumerate(lines) if line.upper().startswith("DIRECCIÓN:") or line.upper().startswith("DIRECCION:")), None)
        if direccion_index is not None:
            direccion = lines[direccion_index].split(":", 1)[1].strip() if ":" in lines[direccion_index] else lines[direccion_index]
            if direccion:
                normalized.set_field("receptor", "direccion", direccion, "pdf", "medium")

        medio_index = next((idx for idx, line in enumerate(lines) if line.upper().startswith("MEDIO DE PAGO:")), None)
        if medio_index is not None:
            medio_partes = []
            glosa_partes = []
            total_bruto = None
            monto_iva = Decimal("0") if es_exenta else None
            monto_neto = None

            medio_inicial = lines[medio_index].split(":", 1)[1].strip() if ":" in lines[medio_index] else ""
            if medio_inicial:
                medio_partes.append(medio_inicial)

            idx = medio_index + 1
            while idx < len(lines):
                line = lines[idx]
                if re.search(r"\$\s*[\d\.\,]+", line):
                    total_match = re.search(r"\$\s*([\d\.\,]+)", line)
                    if total_match:
                        total_bruto = _money_decimal(total_match.group(1))
                    idx += 1
                    break
                if not glosa_partes and len(line.split()) <= 2 and "-" not in line and "(" not in line and ")" not in line and not any(char.isdigit() for char in line):
                    medio_partes.append(line)
                else:
                    glosa_partes.append(line)
                idx += 1

            while idx < len(lines):
                line = lines[idx]
                if "TIMBRE ELECTR" in _fold_text(line):
                    break
                iva_match = re.search(r"de:\s*\$\s*([\d\.\,]+)", line, flags=re.IGNORECASE)
                if iva_match:
                    monto_iva = _money_decimal(iva_match.group(1))
                    break
                idx += 1

            medio_pago = PdfFallbackParser._join_wrapped_lines(medio_partes)
            glosa = PdfFallbackParser._join_wrapped_lines(glosa_partes)

            if total_bruto is not None and monto_iva is not None and not es_exenta:
                monto_neto = total_bruto - monto_iva

            if medio_pago:
                normalized.set_field("encabezado", "medio_pago", medio_pago, "pdf", "high")
            if total_bruto is not None:
                normalized.set_field("montos", "total_bruto", total_bruto, "pdf", "high")
            if monto_iva is not None:
                normalized.set_field("montos", "iva", monto_iva, "pdf", "high")
                normalized.set_field("montos", "tasa_iva", Decimal("0" if es_exenta else "19"), "inferred", "high")
            if es_exenta:
                normalized.set_field("montos", "neto", Decimal("0"), "inferred", "high")
                normalized.set_field("montos", "exento", total_bruto or Decimal("0"), "pdf", "high")
            else:
                if monto_neto is not None:
                    normalized.set_field("montos", "neto", monto_neto, "inferred", "high")
                normalized.set_field("montos", "exento", Decimal("0"), "inferred", "high")

            if glosa:
                linea = NormalizedTaxLine()
                linea.set_field("numero_linea", 1, "pdf", "medium")
                linea.set_field("descripcion", glosa, "pdf", "high")
                linea.set_field("cantidad", Decimal("1"), "inferred", "medium")
                linea.set_field("precio_unitario", total_bruto or monto_neto, "pdf", "medium")
                linea.set_field("subtotal_linea", total_bruto or monto_neto, "pdf", "medium")
                normalized.lineas.append(linea)

    @staticmethod
    def _parse_pdf_field_patterns(text, normalized):
        text = PdfFallbackParser._normalize_pdf_text(text)
        upper = text.upper()
        categoria = "other"
        nombre_legible = "documento tributario"
        tipo_documento = "otro"
        if "HONORARIOS" in upper:
            categoria = "fee_receipt"
            nombre_legible = "boleta de honorarios"
            tipo_documento = "boleta_honorarios"
        elif "FACTURA" in upper and ("EXENTA" in upper or "NO AFECTA" in upper):
            categoria = "invoice"
            nombre_legible = "factura exenta"
            tipo_documento = "factura_exenta"
        elif "FACTURA" in upper:
            categoria = "invoice"
            nombre_legible = "factura"
            tipo_documento = "factura_afecta"
        elif "BOLETA" in upper and "EXENTA" in upper:
            categoria = "sales_receipt"
            nombre_legible = "boleta de venta exenta"
            tipo_documento = "boleta_venta_exenta"
        elif "BOLETA" in upper:
            categoria = "sales_receipt"
            nombre_legible = "boleta de venta"
            tipo_documento = "boleta_venta_afecta"

        normalized.set_field("encabezado", "categoria_documental", categoria, "pdf", "medium")
        normalized.set_field("encabezado", "nombre_legible", nombre_legible, "pdf", "medium")
        normalized.set_field("encabezado", "tipo_documento_sugerido", tipo_documento, "pdf", "medium")
        normalized.set_field("encabezado", "moneda", "CLP", "inferred", "medium")

        if tipo_documento == "boleta_honorarios":
            PdfFallbackParser._parse_fee_receipt_pdf(text, normalized)
            return
        if tipo_documento in {"boleta_venta_afecta", "boleta_venta_exenta"} and (
            "EL IVA INCLUIDO EN ESTA BOLETA ES" in upper or "BOLETA EXENTA ELECTR" in upper
        ):
            PdfFallbackParser._parse_sales_receipt_pdf(text, normalized)
            return

        folio_match = re.search(r"(?:N[º°oO]?|NRO\.?|NUMERO)\s*([0-9]+)", text, flags=re.IGNORECASE)
        fecha_match = re.search(
            r"Fecha\s+Emision\s*:\s*([0-9]{1,2}\s+de\s+[A-Za-zÁÉÍÓÚáéíóúñÑ]+\s+del?\s+[0-9]{4})",
            text,
            flags=re.IGNORECASE,
        )
        rut_matches = re.findall(r"\d{1,3}(?:\.\d{3}){2}-\s*[\dkK]|\d{7,8}-\s*[\dkK]", text)
        total_match = re.search(r"TOTAL\s+\$\s*([\d\.\,]+)", text, flags=re.IGNORECASE)
        exento_match = re.search(r"EXENTO\s+\$\s*([\d\.\,]+)", text, flags=re.IGNORECASE)
        neto_match = re.search(r"NETO\s+\$\s*([\d\.\,]+)", text, flags=re.IGNORECASE)
        iva_match = re.search(r"\bIVA\b\s+\$\s*([\d\.\,]+)", text, flags=re.IGNORECASE)

        if folio_match:
            normalized.set_field("encabezado", "folio", folio_match.group(1), "pdf", "medium")
        if fecha_match:
            fecha_iso = _parse_spanish_date(fecha_match.group(1).strip()) or fecha_match.group(1).strip()
            normalized.set_field("encabezado", "fecha_emision", fecha_iso, "pdf", "medium")
        if rut_matches:
            normalized.set_field("emisor", "rut", re.sub(r"\s+", "", rut_matches[0]), "pdf", "medium")
            if len(rut_matches) > 1:
                normalized.set_field("receptor", "rut", re.sub(r"\s+", "", rut_matches[1]), "pdf", "medium")
        if total_match:
            normalized.set_field("montos", "total_bruto", _money_decimal(total_match.group(1)), "pdf", "medium")
        if exento_match:
            normalized.set_field("montos", "exento", _money_decimal(exento_match.group(1)), "pdf", "medium")
        if neto_match:
            normalized.set_field("montos", "neto", _money_decimal(neto_match.group(1)), "pdf", "medium")
        if iva_match:
            normalized.set_field("montos", "iva", _money_decimal(iva_match.group(1)), "pdf", "medium")

        lines = [line.rstrip() for line in text.splitlines()]
        giro_index = next((idx for idx, line in enumerate(lines) if "GIRO:" in line.upper()), None)
        if giro_index is not None:
            emisor_lines = []
            idx = giro_index - 1
            while idx >= 0:
                line = lines[idx].strip()
                if not line:
                    idx -= 1
                    continue
                if "R.U.T." in line.upper():
                    break
                emisor_lines.insert(0, re.split(r"\s{3,}", line, maxsplit=1)[0].strip())
                idx -= 1
            emisor_lines = [line for line in emisor_lines if line]
            if emisor_lines:
                normalized.set_field("emisor", "razon_social", " ".join(emisor_lines).strip(), "pdf", "medium")
            giro_line = lines[giro_index]
            giro_value = giro_line.split(":", 1)[1].strip() if ":" in giro_line else giro_line.strip()
            giro_value = re.split(r"\s{3,}", giro_value, maxsplit=1)[0].strip()
            normalized.set_field("emisor", "giro", giro_value, "pdf", "medium")

        senores_index = next((idx for idx, line in enumerate(lines) if "SEÑOR(ES)" in line.upper() or "SEÑOR(ES):" in line.upper()), None)
        if senores_index is not None:
            for idx in range(senores_index + 1, min(senores_index + 8, len(lines))):
                line = lines[idx].strip()
                if not line:
                    continue
                upper_line = line.upper()
                if upper_line.startswith("R.U.T.") or upper_line.startswith("GIRO:") or upper_line.startswith("DIRECCION:"):
                    continue
                normalized.set_field("receptor", "razon_social", line, "pdf", "medium")
                break
            for idx in range(senores_index + 1, min(senores_index + 10, len(lines))):
                line = lines[idx].strip()
                upper_line = line.upper()
                if upper_line.startswith("GIRO:"):
                    normalized.set_field("receptor", "giro", line.split(":", 1)[1].strip(), "pdf", "low")
                if upper_line.startswith("DIRECCION:"):
                    normalized.set_field("receptor", "direccion", line.split(":", 1)[1].strip(), "pdf", "low")

        table_start = next(
            (
                idx
                for idx, line in enumerate(lines)
                if "DESCRIPCION" in line.upper() and "CANTIDAD" in line.upper() and "PRECIO" in line.upper()
            ),
            None,
        )
        if table_start is not None:
            for idx in range(table_start + 1, len(lines)):
                line = lines[idx].rstrip()
                stripped_line = line.strip()
                if not stripped_line:
                    continue
                if stripped_line.startswith("-"):
                    row_match = re.search(r"^\-\s+(.+?)\s+([0-9]+)\s+([\d\.\,]+)\s+([\d\.\,]+)\s*$", stripped_line)
                    descripcion_extra = ""
                    if idx + 1 < len(lines):
                        next_line = lines[idx + 1].strip()
                        if next_line and not next_line.upper().startswith("FORMA DE PAGO"):
                            descripcion_extra = next_line
                    if row_match:
                        linea = NormalizedTaxLine()
                        descripcion_base = row_match.group(1).strip()
                        descripcion = f"{descripcion_base} {descripcion_extra}".strip()
                        linea.set_field("numero_linea", 1, "pdf", "medium")
                        linea.set_field("descripcion", descripcion, "pdf", "medium")
                        linea.set_field("cantidad", _decimal(row_match.group(2)), "pdf", "medium")
                        linea.set_field("precio_unitario", _money_decimal(row_match.group(3)), "pdf", "medium")
                        linea.set_field("subtotal_linea", _money_decimal(row_match.group(4)), "pdf", "medium")
                        normalized.lineas.append(linea)
                    break

    def parse(self, *, xml_bytes=None, pdf_bytes=None, pdf_name=None, xml_name=None):
        normalized = NormalizedTaxDocument()
        normalized.set_field("metadata_archivo", "nombre_archivo", pdf_name, "pdf", "high")
        normalized.set_field("metadata_archivo", "tipo_mime", "application/pdf", "inferred", "high")
        normalized.set_field("metadata_archivo", "extension", "pdf", "inferred", "high")
        normalized.set_field("metadata_archivo", "hash", _filename_hash(pdf_bytes), "pdf", "high")
        normalized.set_field("metadata_archivo", "formato_origen", "pdf", "pdf", "high")
        normalized.set_field("metadata_archivo", "parser_usado", self.parser_name, "pdf", "high")
        normalized.set_field("metadata_archivo", "fuente_principal", "pdf", "pdf", "high")
        text = self._extract_text_with_pypdf(pdf_bytes)
        if not text.strip():
            text = self._extract_text_with_pdftotext(pdf_bytes)

        if not text.strip():
            normalized.errors.append("El PDF no contiene texto seleccionable util para parsear.")
            return normalized

        self._parse_pdf_field_patterns(text, normalized)
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

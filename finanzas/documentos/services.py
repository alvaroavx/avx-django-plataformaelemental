from .dtos import NormalizedTaxDocument
from .mapping import detectar_duplicados_documento, documento_initial_from_normalized, pago_initial_from_normalized, sugerencias_mapeo
from .parsers import BheXmlParser, DteXmlParser, PdfFallbackParser, detectar_familia_xml


def parse_tax_document(*, xml_bytes=None, xml_name=None, pdf_bytes=None, pdf_name=None, organizacion_id=None):
    if xml_bytes:
        familia = detectar_familia_xml(xml_bytes)
        if familia == "dte":
            normalized = DteXmlParser().parse(xml_bytes=xml_bytes, xml_name=xml_name, pdf_bytes=pdf_bytes, pdf_name=pdf_name)
        elif familia == "bhe":
            normalized = BheXmlParser().parse(xml_bytes=xml_bytes, xml_name=xml_name, pdf_bytes=pdf_bytes, pdf_name=pdf_name)
        else:
            normalized = NormalizedTaxDocument()
            normalized.errors.append("No se pudo reconocer la familia del XML.")
    elif pdf_bytes:
        normalized = PdfFallbackParser().parse(pdf_bytes=pdf_bytes, pdf_name=pdf_name)
    else:
        normalized = NormalizedTaxDocument()
        normalized.errors.append("No se recibio ningun archivo para parsear.")

    normalized.posibles_duplicados = detectar_duplicados_documento(normalized, organizacion_id=organizacion_id)
    normalized.sugerencias_mapeo = sugerencias_mapeo(normalized, organizacion_id=organizacion_id)
    return normalized


def build_review_payload(normalized, organizacion_id=None):
    return {
        "normalized": normalized.to_dict(),
        "documento_initial": documento_initial_from_normalized(normalized, organizacion_id=organizacion_id),
        "pago_initial": pago_initial_from_normalized(normalized, organizacion_id=organizacion_id),
        "warnings": list(normalized.warnings),
        "errors": list(normalized.errors),
        "duplicates": list(normalized.posibles_duplicados),
        "suggestions": dict(normalized.sugerencias_mapeo),
    }

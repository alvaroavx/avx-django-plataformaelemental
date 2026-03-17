import json
from decimal import Decimal

from database.models import DocumentoTributario, Organizacion, Payment, Persona


def map_tipo_documento(normalized):
    return normalized.get_value("encabezado", "tipo_documento_sugerido", "otro") or "otro"


def _rut_normalizado(value):
    return (value or "").replace(".", "").upper().strip()


def _buscar_persona_sugerida(organizacion_id, rut, nombre):
    queryset = Persona.objects.all()
    if rut:
        persona = queryset.filter(identificador__iexact=_rut_normalizado(rut)).first()
        if persona:
            return persona
    if nombre:
        partes = [item for item in str(nombre).split() if item]
        if partes:
            persona = queryset.filter(nombres__icontains=partes[0]).first()
            if persona:
                return persona
    return None


def detectar_duplicados_documento(normalized, organizacion_id=None):
    queryset = DocumentoTributario.objects.all()
    if organizacion_id:
        queryset = queryset.filter(organizacion_id=organizacion_id)
    folio = normalized.get_value("encabezado", "folio")
    fecha = normalized.get_value("encabezado", "fecha_emision")
    total = normalized.get_value("montos", "total_bruto")
    rut_emisor = normalized.get_value("emisor", "rut")
    rut_receptor = normalized.get_value("receptor", "rut")
    tipo_documento = map_tipo_documento(normalized)
    if folio:
        queryset = queryset.filter(folio=folio)
    if fecha:
        queryset = queryset.filter(fecha_emision=fecha)
    if total is not None:
        queryset = queryset.filter(monto_total=total)
    if tipo_documento:
        queryset = queryset.filter(tipo_documento=tipo_documento)
    if rut_emisor:
        queryset = queryset.filter(rut_emisor__iexact=rut_emisor)
    if rut_receptor:
        queryset = queryset.filter(rut_receptor__iexact=rut_receptor)
    return [
        {
            "id": item.pk,
            "folio": item.folio,
            "fecha_emision": item.fecha_emision.isoformat(),
            "monto_total": str(item.monto_total),
        }
        for item in queryset[:10]
    ]


def documento_initial_from_normalized(normalized, organizacion_id=None):
    metadata = normalized.to_dict()
    return {
        "organizacion": organizacion_id or "",
        "tipo_documento": map_tipo_documento(normalized),
        "fuente": DocumentoTributario.Fuente.SII if normalized.get_value("metadata_archivo", "fuente_principal") == "xml" else DocumentoTributario.Fuente.MANUAL,
        "folio": normalized.get_value("encabezado", "folio", ""),
        "fecha_emision": normalized.get_value("encabezado", "fecha_emision", ""),
        "nombre_emisor": normalized.get_value("emisor", "razon_social", ""),
        "rut_emisor": normalized.get_value("emisor", "rut", ""),
        "nombre_receptor": normalized.get_value("receptor", "razon_social", ""),
        "rut_receptor": normalized.get_value("receptor", "rut", ""),
        "monto_neto": normalized.get_value("montos", "neto") or Decimal("0"),
        "monto_exento": normalized.get_value("montos", "exento") or Decimal("0"),
        "iva_tasa": normalized.get_value("montos", "tasa_iva") or Decimal("0"),
        "monto_iva": normalized.get_value("montos", "iva") or Decimal("0"),
        "retencion_tasa": normalized.get_value("montos", "porcentaje_retencion") or Decimal("0"),
        "retencion_monto": normalized.get_value("montos", "retencion_honorarios") or Decimal("0"),
        "monto_total": normalized.get_value("montos", "total_bruto") or Decimal("0"),
        "metadata_extra": json.dumps(metadata, ensure_ascii=True),
        "observaciones": "\n".join(normalized.warnings),
    }


def pago_initial_from_normalized(normalized, organizacion_id=None):
    categoria = normalized.get_value("encabezado", "categoria_documental")
    if categoria != "sales_receipt":
        return None
    nombre = normalized.get_value("receptor", "razon_social") or ""
    rut = normalized.get_value("receptor", "rut") or ""
    persona = _buscar_persona_sugerida(organizacion_id, rut, nombre)
    return {
        "organizacion": organizacion_id or "",
        "persona": persona.pk if persona else "",
        "fecha_pago": normalized.get_value("encabezado", "fecha_emision", ""),
        "metodo_pago": Payment.Metodo.EFECTIVO,
        "numero_comprobante": "",
        "aplica_iva": False,
        "monto_incluye_iva": True,
        "monto_referencia": normalized.get_value("montos", "total_bruto") or Decimal("0"),
        "clases_asignadas": 0,
        "observaciones": "Pago sugerido desde documento tributario importado.",
    }


def sugerencias_mapeo(normalized, organizacion_id=None):
    nombre = normalized.get_value("receptor", "razon_social") or normalized.get_value("emisor", "razon_social") or ""
    rut = normalized.get_value("receptor", "rut") or normalized.get_value("emisor", "rut") or ""
    persona = _buscar_persona_sugerida(organizacion_id, rut, nombre)
    organizacion = Organizacion.objects.filter(pk=organizacion_id).first() if organizacion_id else None
    return {
        "persona_sugerida_id": persona.pk if persona else None,
        "persona_sugerida_nombre": str(persona) if persona else "",
        "organizacion_sugerida_id": organizacion.pk if organizacion else None,
    }

import json
from decimal import Decimal

from django.utils.dateparse import parse_date

from personas.models import Organizacion, Persona
from personas.validators import formatear_rut_chileno

from finanzas.models import DocumentoTributario, Payment


def map_tipo_documento(normalized):
    return normalized.get_value("encabezado", "tipo_documento_sugerido", "otro") or "otro"


def _glosa_documento(normalized):
    glosas = []
    for linea in normalized.lineas:
        descripcion = linea.fields.get("descripcion")
        if not descripcion or not descripcion.value:
            continue
        texto = str(descripcion.value).strip()
        if texto and texto not in glosas:
            glosas.append(texto)
    return "\n".join(glosas)


def _rut_normalizado(value):
    return formatear_rut_chileno(value)


def _buscar_persona_sugerida(organizacion_id, rut, nombre):
    queryset = Persona.objects.all()
    if rut:
        rut_formateado = _rut_normalizado(rut)
        persona = queryset.filter(rut__iexact=rut_formateado).first()
        if persona:
            return persona
    if nombre:
        partes = [item for item in str(nombre).split() if item]
        if partes:
            persona = queryset.filter(nombres__icontains=partes[0]).first()
            if persona:
                return persona
    return None


def _buscar_organizacion_sugerida(organizacion_id, rut, nombre):
    queryset = Organizacion.objects.all()
    if organizacion_id:
        queryset = queryset.exclude(pk=organizacion_id)
    if rut:
        rut_formateado = _rut_normalizado(rut)
        organizacion = queryset.filter(rut__iexact=rut_formateado).first()
        if organizacion:
            return organizacion
    if nombre:
        organizacion = queryset.filter(nombre__iexact=str(nombre).strip()).first()
        if organizacion:
            return organizacion
        organizacion = queryset.filter(razon_social__iexact=str(nombre).strip()).first()
        if organizacion:
            return organizacion
    return None


def _nombre_organizacion(value):
    return " ".join((value or "").upper().split())


def _lado_contraparte(normalized, organizacion_id=None):
    organizacion = Organizacion.objects.filter(pk=organizacion_id).first() if organizacion_id else None
    rut_emisor = _rut_normalizado(normalized.get_value("emisor", "rut") or "")
    rut_receptor = _rut_normalizado(normalized.get_value("receptor", "rut") or "")
    nombre_emisor = _nombre_organizacion(normalized.get_value("emisor", "razon_social") or "")
    nombre_receptor = _nombre_organizacion(normalized.get_value("receptor", "razon_social") or "")
    if organizacion:
        rut_org = _rut_normalizado(organizacion.rut)
        nombres_org = {
            _nombre_organizacion(organizacion.nombre),
            _nombre_organizacion(organizacion.razon_social),
        }
        nombres_org.discard("")
        if rut_org and rut_org == rut_emisor:
            return "receptor"
        if rut_org and rut_org == rut_receptor:
            return "emisor"
        if nombre_emisor and nombre_emisor in nombres_org:
            return "receptor"
        if nombre_receptor and nombre_receptor in nombres_org:
            return "emisor"
    if rut_receptor or nombre_receptor:
        return "receptor"
    if rut_emisor or nombre_emisor:
        return "emisor"
    return None


def _datos_contraparte(normalized, organizacion_id=None):
    lado = _lado_contraparte(normalized, organizacion_id=organizacion_id)
    if not lado:
        return "", "", None
    nombre = normalized.get_value(lado, "razon_social") or ""
    rut = normalized.get_value(lado, "rut") or ""
    return nombre, rut, lado


def _datos_lado(normalized, lado):
    return (
        normalized.get_value(lado, "razon_social") or "",
        normalized.get_value(lado, "rut") or "",
        lado,
    )


def _sugerir_contraparte(normalized, organizacion_id=None):
    nombre, rut, lado = _datos_contraparte(normalized, organizacion_id=organizacion_id)
    candidatos = []
    if lado:
        candidatos.append((nombre, rut, lado))
        otro_lado = "emisor" if lado == "receptor" else "receptor"
        candidatos.append(_datos_lado(normalized, otro_lado))
    else:
        candidatos.extend([
            _datos_lado(normalized, "receptor"),
            _datos_lado(normalized, "emisor"),
        ])

    persona_sugerida = None
    organizacion_sugerida = None
    lado_encontrado = lado
    for nombre_candidato, rut_candidato, lado_candidato in candidatos:
        if not persona_sugerida:
            persona_sugerida = _buscar_persona_sugerida(organizacion_id, rut_candidato, nombre_candidato)
        if not organizacion_sugerida and not persona_sugerida:
            organizacion_sugerida = _buscar_organizacion_sugerida(organizacion_id, rut_candidato, nombre_candidato)
        if persona_sugerida or organizacion_sugerida:
            lado_encontrado = lado_candidato
            break
    return persona_sugerida, organizacion_sugerida, lado_encontrado


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
    if folio and tipo_documento and rut_emisor:
        queryset = queryset.filter(
            folio=folio,
            tipo_documento=tipo_documento,
            rut_emisor__iexact=rut_emisor,
        )
    else:
        if folio:
            queryset = queryset.filter(folio=folio)
        if tipo_documento:
            queryset = queryset.filter(tipo_documento=tipo_documento)
        fecha_parseada = parse_date(fecha) if isinstance(fecha, str) else fecha
        if fecha_parseada:
            queryset = queryset.filter(fecha_emision=fecha_parseada)
        if total is not None:
            queryset = queryset.filter(monto_total=total)
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
    observaciones = _glosa_documento(normalized) or "\n".join(normalized.warnings)
    persona_sugerida, organizacion_sugerida, _lado = _sugerir_contraparte(normalized, organizacion_id=organizacion_id)
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
        "persona_relacionada": persona_sugerida.pk if persona_sugerida else "",
        "organizacion_relacionada": organizacion_sugerida.pk if organizacion_sugerida else "",
        "metadata_extra": json.dumps(metadata, ensure_ascii=True),
        "observaciones": observaciones,
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
    persona, organizacion, lado = _sugerir_contraparte(normalized, organizacion_id=organizacion_id)
    return {
        "lado_contraparte": lado,
        "persona_sugerida_id": persona.pk if persona else None,
        "persona_sugerida_nombre": str(persona) if persona else "",
        "organizacion_sugerida_id": organizacion.pk if organizacion else None,
        "organizacion_sugerida_nombre": organizacion.nombre if organizacion else "",
    }

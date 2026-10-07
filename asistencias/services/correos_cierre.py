import calendar
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from django.utils.formats import date_format

from asistencias.models import SesionClase


def _clp(monto):
    entero = Decimal(monto).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return f"$ {int(entero):,}".replace(",", ".")


def _nombre_periodo(mes, anio):
    return date_format(date(anio, mes, 1), "F Y")


def construir_borrador_correo_profesor(*, profesor, organizacion, rol_profesor, mes, anio):
    """Construye un borrador copiable; no envía correo ni registra un pago."""
    sesiones = list(
        SesionClase.objects.filter(
            profesores=profesor,
            disciplina__organizacion=organizacion,
            fecha__year=anio,
            fecha__month=mes,
        )
        .select_related("disciplina")
        .prefetch_related("asistencias__persona")
        .distinct()
        .order_by("disciplina__nombre", "fecha", "pk")
    )

    grupos_por_id = {}
    total_asistencias = 0
    for sesion in sesiones:
        grupo = grupos_por_id.setdefault(
            sesion.disciplina_id,
            {
                "disciplina": sesion.disciplina,
                "sesiones": [],
                "sesiones_realizadas": 0,
                "total_asistencias": 0,
            },
        )
        asistentes = sorted(
            (asistencia.persona for asistencia in sesion.asistencias.all()),
            key=lambda persona: ((persona.apellidos or "").casefold(), (persona.nombres or "").casefold()),
        )
        cantidad = len(asistentes)
        grupo["sesiones"].append(
            {
                "fecha": sesion.fecha,
                "estado": sesion.get_estado_display(),
                "cancelada": sesion.estado == SesionClase.Estado.CANCELADA,
                "asistentes": asistentes,
                "cantidad_asistentes": cantidad,
            }
        )
        if sesion.estado == SesionClase.Estado.COMPLETADA:
            grupo["sesiones_realizadas"] += 1
        grupo["total_asistencias"] += cantidad
        total_asistencias += cantidad

    grupos = sorted(grupos_por_id.values(), key=lambda grupo: grupo["disciplina"].nombre.casefold())
    grupos_con_realizadas = [grupo for grupo in grupos if grupo["sesiones_realizadas"]]
    candidatos_asunto = grupos_con_realizadas or grupos
    disciplina_asunto = None
    if candidatos_asunto:
        disciplina_asunto = sorted(
            candidatos_asunto,
            key=lambda grupo: (
                -grupo["sesiones_realizadas"],
                -grupo["total_asistencias"],
                grupo["disciplina"].nombre.casefold(),
            ),
        )[0]["disciplina"]

    valor_clase = rol_profesor.valor_clase
    retencion_porcentaje = rol_profesor.retencion_sii
    pago_bruto = valor_clase * total_asistencias if valor_clase is not None else None
    retencion_monto = None
    pago_neto = None
    if pago_bruto is not None and retencion_porcentaje is not None:
        retencion_monto = pago_bruto * retencion_porcentaje / Decimal("100")
        pago_neto = pago_bruto - retencion_monto

    ultimo_dia = calendar.monthrange(anio, mes)[1]
    fecha_boleta = date(anio, mes, ultimo_dia)
    periodo = _nombre_periodo(mes, anio)
    asunto = f"{disciplina_asunto.nombre} {periodo}" if disciplina_asunto else f"Clases {periodo}"

    faltantes = []
    for valor, etiqueta in (
        (organizacion.razon_social, "razón social de la organización"),
        (organizacion.rut, "RUT de la organización"),
        (organizacion.direccion, "dirección tributaria"),
        (organizacion.comuna, "comuna"),
        (organizacion.region, "región"),
        (valor_clase, "valor por asistencia del profesor"),
        (retencion_porcentaje, "porcentaje de retención del profesor"),
    ):
        if valor in (None, ""):
            faltantes.append(etiqueta)

    lineas = [
        f"Hola {profesor.nombres},",
        "",
        "Muchas gracias por las clases realizadas durante el mes. Adjunto el comprobante de transferencia y, para transparencia, te comparto el detalle de asistencia considerado para el pago.",
        "",
    ]
    for grupo in grupos:
        lineas.append(grupo["disciplina"].nombre)
        for sesion in grupo["sesiones"]:
            asistentes = ", ".join(persona.nombre_completo for persona in sesion["asistentes"]) or "Sin asistentes"
            lineas.append(f"- {sesion['fecha'].strftime('%d/%m/%Y')} · {sesion['estado']}: {asistentes}")
        lineas.append("")

    lineas.extend(
        [
            "Detalle del pago",
            f"- Asistencias: {total_asistencias}",
            f"- Valor por asistencia: {_clp(valor_clase) if valor_clase is not None else 'Sin informar'}",
            f"- Monto bruto de la boleta: {_clp(pago_bruto) if pago_bruto is not None else 'Sin calcular'}",
            f"- Retención SII: {retencion_porcentaje}% ({_clp(retencion_monto)})" if retencion_monto is not None else "- Retención SII: Sin calcular",
            f"- Monto líquido transferido: {_clp(pago_neto) if pago_neto is not None else 'Sin calcular'}",
            "",
            "Datos para emitir la boleta de honorarios",
            f"- Fecha: {fecha_boleta.strftime('%d/%m/%Y')}",
            f"- Razón social: {organizacion.razon_social or 'Sin informar'}",
            f"- RUT: {organizacion.rut or 'Sin informar'}",
            f"- Dirección: {organizacion.direccion or 'Sin informar'}, {organizacion.comuna or 'Sin informar'}, {organizacion.region or 'Sin informar'}",
            f"- Prestación: Clases de {', '.join(grupo['disciplina'].nombre for grupo in grupos) or 'Sin disciplinas'} durante {periodo}",
            "- La organización receptora retiene el porcentaje indicado.",
            "",
            "Muchas gracias por tu trabajo.",
            "",
            organizacion.nombre,
        ]
    )

    return {
        "asunto": asunto,
        "periodo": periodo,
        "fecha_boleta": fecha_boleta,
        "grupos": grupos,
        "total_asistencias": total_asistencias,
        "valor_clase": valor_clase,
        "pago_bruto": pago_bruto,
        "retencion_porcentaje": retencion_porcentaje,
        "retencion_monto": retencion_monto,
        "pago_neto": pago_neto,
        "faltantes": faltantes,
        "puede_copiar": not faltantes,
        "cuerpo_plano": "\n".join(lineas),
    }

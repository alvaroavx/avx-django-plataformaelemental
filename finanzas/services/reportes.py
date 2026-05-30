from ..models import Transaction
from ..selectors import resumen_dashboard


PAGOS_CSV_HEADERS = ["Fecha", "Organizacion", "Persona", "Metodo", "Neto", "IVA", "Total", "Clases"]
TRANSACCIONES_CSV_HEADERS = ["Fecha", "Organizacion", "Tipo", "Categoria", "Monto", "Descripcion"]
PAGOS_ALUMNOS_XLSX_HEADERS = [
    "Fecha pago",
    "Periodo imputado",
    "Organizacion",
    "Estudiante",
    "Plan",
    "Metodo de pago",
    "Monto neto",
    "IVA",
    "Monto total",
    "Clases pagadas",
    "Clases consumidas",
    "Saldo clases",
    "Estado",
    "Documento tributario",
    "Numero comprobante",
    "Observacion",
]
TRANSACCIONES_XLSX_HEADERS = [
    "Fecha",
    "Periodo",
    "Organizacion",
    "Tipo",
    "Categoria",
    "Descripcion/glosa",
    "Monto",
    "Documento tributario asociado",
    "Msg",
]
LIBRO_CAJA_CSV_HEADERS = [
    "numero correlativo",
    "fecha",
    "tipo",
    "categoria",
    "descripcion/glosa",
    "monto",
    "ingreso/egreso",
    "documento tributario asociado",
    "Msg",
]


def armar_dashboard_financiero(
    *,
    pagos_qs,
    transacciones_qs,
    documentos_qs,
    consumos_qs,
    periodo_descripcion,
    organizacion,
    mes=None,
    anio=None,
):
    return {
        **resumen_dashboard(
            pagos_qs,
            transacciones_qs,
            documentos_qs,
            consumos_qs,
            mes=mes,
            anio=anio,
        ),
        "pagos_recientes": pagos_qs.select_related("persona", "organizacion")[:10],
        "transacciones_recientes": transacciones_qs.select_related("categoria", "organizacion")[:10],
        "periodo_descripcion_vista": periodo_descripcion,
        "organizacion_filtro": organizacion,
    }


def armar_reporte_categorias(*, consolidado_qs, periodo_descripcion):
    return {
        "consolidado": list(consolidado_qs),
        "periodo_descripcion_vista": periodo_descripcion,
    }


def filas_export_pagos(pagos):
    for pago in pagos:
        yield [
            pago.fecha_pago,
            pago.organizacion.nombre,
            pago.persona.nombre_completo,
            pago.get_metodo_pago_display(),
            pago.monto_neto,
            pago.monto_iva,
            pago.monto_total,
            pago.clases_asignadas,
        ]


def filas_export_transacciones(transacciones):
    for item in transacciones:
        yield [
            item.fecha,
            item.organizacion.nombre,
            item.get_tipo_display(),
            item.categoria.nombre,
            item.monto,
            item.descripcion,
        ]


def _periodo_fecha(fecha):
    return fecha.strftime("%Y-%m") if fecha else ""


def _estado_operacional_pago(pago):
    saldo = pago.saldo_clases_calculado if hasattr(pago, "saldo_clases_calculado") else pago.saldo_clases
    if saldo > 0:
        return "Con saldo"
    if saldo == 0:
        return "Sin saldo"
    return "Sobreconsumido"


def _documento_resumen_pago(pago):
    documento = pago.documento_tributario
    if not documento:
        return ""
    return f"{documento.get_tipo_documento_display()} #{documento.folio}"


def filas_export_pagos_alumnos_xlsx(pagos):
    for pago in pagos:
        clases_consumidas = (
            pago.clases_consumidas_calculadas if hasattr(pago, "clases_consumidas_calculadas") else pago.clases_consumidas
        )
        saldo_clases = pago.saldo_clases_calculado if hasattr(pago, "saldo_clases_calculado") else pago.saldo_clases
        yield [
            pago.fecha_pago,
            _periodo_fecha(pago.fecha_pago),
            pago.organizacion.nombre,
            pago.persona.nombre_completo,
            pago.plan.nombre if pago.plan else "",
            pago.get_metodo_pago_display(),
            pago.monto_neto,
            pago.monto_iva,
            pago.monto_total,
            pago.clases_asignadas,
            clases_consumidas,
            saldo_clases,
            _estado_operacional_pago(pago),
            _documento_resumen_pago(pago),
            pago.numero_comprobante,
            pago.observaciones,
        ]


def filas_export_transacciones_xlsx(transacciones):
    for item in transacciones:
        yield [
            item.fecha,
            _periodo_fecha(item.fecha),
            item.organizacion.nombre,
            item.get_tipo_display(),
            item.categoria.nombre,
            item.descripcion,
            item.monto,
            documento_resumen_transaccion(item),
            msg_contable_transaccion(item),
        ]


def documento_resumen_transaccion(transaccion):
    documentos = list(transaccion.documentos_tributarios.all())
    if not documentos:
        return ""
    return " | ".join(
        f"{documento.get_tipo_documento_display()} #{documento.folio}" for documento in documentos
    )


def msg_contable_transaccion(transaccion):
    partes = [transaccion.fecha.isoformat(), transaccion.get_tipo_display(), transaccion.categoria.nombre]
    descripcion = (transaccion.descripcion or "").strip()
    if descripcion:
        partes.append(descripcion)
    documento = documento_resumen_transaccion(transaccion)
    if documento:
        partes.append(documento)
    return " - ".join(partes)


def filas_export_libro_caja(transacciones):
    for correlativo, item in enumerate(transacciones, start=1):
        yield [
            correlativo,
            item.fecha.isoformat(),
            item.get_tipo_display(),
            item.categoria.nombre,
            item.descripcion,
            item.monto,
            "ingreso" if item.tipo == Transaction.Tipo.INGRESO else "egreso",
            documento_resumen_transaccion(item),
            msg_contable_transaccion(item),
        ]


__all__ = [
    "LIBRO_CAJA_CSV_HEADERS",
    "PAGOS_ALUMNOS_XLSX_HEADERS",
    "PAGOS_CSV_HEADERS",
    "TRANSACCIONES_CSV_HEADERS",
    "TRANSACCIONES_XLSX_HEADERS",
    "armar_dashboard_financiero",
    "armar_reporte_categorias",
    "filas_export_libro_caja",
    "filas_export_pagos_alumnos_xlsx",
    "filas_export_pagos",
    "filas_export_transacciones",
    "filas_export_transacciones_xlsx",
    "msg_contable_transaccion",
]

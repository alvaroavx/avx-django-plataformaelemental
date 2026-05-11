from ..selectors import resumen_dashboard


PAGOS_CSV_HEADERS = ["Fecha", "Organizacion", "Persona", "Metodo", "Neto", "IVA", "Total", "Clases"]
TRANSACCIONES_CSV_HEADERS = ["Fecha", "Organizacion", "Tipo", "Categoria", "Monto", "Descripcion"]


def armar_dashboard_financiero(*, pagos_qs, transacciones_qs, periodo_descripcion, organizacion):
    return {
        **resumen_dashboard(pagos_qs, transacciones_qs),
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


__all__ = [
    "PAGOS_CSV_HEADERS",
    "TRANSACCIONES_CSV_HEADERS",
    "armar_dashboard_financiero",
    "armar_reporte_categorias",
    "filas_export_pagos",
    "filas_export_transacciones",
]

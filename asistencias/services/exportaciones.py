from decimal import Decimal


ASISTENCIAS_XLSX_HEADERS = [
    "Fecha sesion",
    "Disciplina",
    "Estudiante",
    "Estado asistencia",
    "Profesores",
    "Organizacion",
    "Observacion",
    "Periodo",
]

PAGOS_PROFESORES_XLSX_HEADERS = [
    "Periodo",
    "Organizacion",
    "Profesor",
    "Disciplinas",
    "Sesiones completadas",
    "Asistencias",
    "Alumnos unicos",
    "Valor clase",
    "Pago bruto",
    "Retencion SII %",
    "Retencion SII",
    "Pago neto",
    "Estado",
    "Observacion",
]


def filas_export_asistencias(asistencias, *, periodo_descripcion):
    for asistencia in asistencias:
        sesion = asistencia.sesion
        yield [
            sesion.fecha,
            sesion.disciplina.nombre,
            asistencia.persona.nombre_completo,
            asistencia.get_estado_display(),
            sesion.profesores_resumen,
            sesion.disciplina.organizacion.nombre,
            asistencia.comentario,
            periodo_descripcion,
        ]


def filas_export_pagos_profesores(
    roles,
    *,
    asistencias_por_profesor,
    sesiones_por_profesor,
    disciplinas_por_profesor,
    periodo_descripcion,
):
    for rol_profesor in roles:
        key = (rol_profesor.persona_id, rol_profesor.organizacion_id)
        asistencias_data = asistencias_por_profesor.get(key, {})
        asistencias_mes = asistencias_data.get("asistencias_mes", 0)
        sesiones_mes = sesiones_por_profesor.get(key, 0)
        if not asistencias_mes and not sesiones_mes:
            continue

        valor_clase = rol_profesor.valor_clase or Decimal("0")
        retencion_pct = rol_profesor.retencion_sii or Decimal("0")
        pago_bruto = valor_clase * Decimal(asistencias_mes)
        retencion_monto = pago_bruto * retencion_pct / Decimal("100")
        pago_neto = pago_bruto - retencion_monto
        yield [
            periodo_descripcion,
            rol_profesor.organizacion.nombre,
            rol_profesor.persona.nombre_completo,
            ", ".join(disciplinas_por_profesor.get(key, [])),
            sesiones_mes,
            asistencias_mes,
            asistencias_data.get("alumnos_unicos", 0),
            valor_clase,
            pago_bruto,
            retencion_pct,
            retencion_monto,
            pago_neto,
            "Estimado operacional",
            "Calculado desde asistencias; no es Transaction ni libro de caja.",
        ]

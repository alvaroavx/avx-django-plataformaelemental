from personas.models import Persona, PersonaRol, Rol

from ..models import AttendanceConsumption, Payment


def crear_persona_estudiante_desde_modal(*, form, organizacion):
    rol_estudiante = Rol.objects.filter(codigo="ESTUDIANTE").first()
    if not organizacion:
        form.add_error(
            None,
            "Debes seleccionar una organizacion en el filtro superior antes de crear a la persona.",
        )
        return None
    if not rol_estudiante:
        form.add_error(
            None,
            "No existe el rol ESTUDIANTE configurado para asignar a la nueva persona.",
        )
        return None

    persona = Persona.objects.create(
        nombres=form.cleaned_data["nombres"].strip(),
        apellidos=form.cleaned_data.get("apellidos", "").strip(),
        telefono=form.cleaned_data.get("telefono", "").strip(),
    )
    PersonaRol.objects.get_or_create(
        persona=persona,
        rol=rol_estudiante,
        organizacion=organizacion,
        defaults={"activo": True},
    )
    return persona


def texto_copiable_operativo_pago(pago):
    disciplina = getattr(pago, "disciplina_principal_nombre", "") or "Sin disciplina"
    nombre_plan = pago.plan.nombre if pago.plan_id else "Sin plan"
    return f"Taller de {disciplina} - {nombre_plan} ({pago.persona.nombre_completo})"


def enriquecer_pagos_para_listado(pagos):
    for pago in pagos:
        pago.estado_fiscal_label = "Afecta" if pago.monto_iva else "Exenta"
        pago.estado_fiscal_badge_class = "text-bg-primary" if pago.monto_iva else "text-bg-secondary"
        pago.texto_copia = texto_copiable_operativo_pago(pago)
        pago.monto_neto_copia = str(int(pago.monto_neto or 0))
        pago.monto_iva_copia = str(int(pago.monto_iva or 0))
        pago.monto_total_copia = str(int(pago.monto_total or 0))
    return pagos


def calcular_saldo_clases_pago(pago, *, consumos_consumidos=None):
    if consumos_consumidos is None:
        consumos_consumidos = pago.consumos.filter(estado=AttendanceConsumption.Estado.CONSUMIDO).count()
    return pago.clases_asignadas - consumos_consumidos


def resumen_consumos_pago(pago):
    consumos = list(pago.consumos.all())
    consumos_consumidos = sum(1 for item in consumos if item.estado == AttendanceConsumption.Estado.CONSUMIDO)
    consumos_pendientes = sum(1 for item in consumos if item.estado == AttendanceConsumption.Estado.PENDIENTE)
    consumos_deuda = sum(1 for item in consumos if item.estado == AttendanceConsumption.Estado.DEUDA)
    return {
        "consumos": consumos,
        "consumos_consumidos": consumos_consumidos,
        "consumos_pendientes": consumos_pendientes,
        "consumos_deuda": consumos_deuda,
        "saldo_clases": calcular_saldo_clases_pago(pago, consumos_consumidos=consumos_consumidos),
    }


__all__ = [
    "calcular_saldo_clases_pago",
    "crear_persona_estudiante_desde_modal",
    "enriquecer_pagos_para_listado",
    "resumen_consumos_pago",
    "texto_copiable_operativo_pago",
]

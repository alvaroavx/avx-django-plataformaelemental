from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from auditoria.models import AuditLog
from auditoria.services import registrar_auditoria
from personas.models import Persona, PersonaRol, Rol

from ..models import (
    AttendanceConsumption,
    Category,
    DocumentoTributario,
    LotePago,
    Payment,
    PaymentPlan,
    Transaction,
)


@transaction.atomic
def crear_pago_operacional(
    *,
    pago,
    usuario=None,
    lote=None,
    origen="pago_individual",
    clave_idempotencia=None,
):
    """Crea un pago y exactamente una transacción contable en la misma unidad atómica."""
    clave_idempotencia = (clave_idempotencia or pago.clave_idempotencia or "").strip() or None
    if clave_idempotencia:
        existente = (
            Payment.objects.select_for_update()
            .filter(clave_idempotencia=clave_idempotencia)
            .first()
        )
        if existente:
            if existente.organizacion_id != pago.organizacion_id:
                raise ValidationError("La clave de idempotencia pertenece a otra organización.")
            return existente

    pago.lote = lote
    pago.registrado_por = usuario if getattr(usuario, "is_authenticated", False) else None
    pago.clave_idempotencia = clave_idempotencia
    pago.save()

    categoria, _ = Category.objects.get_or_create(
        nombre="Cobranza de clases",
        defaults={"tipo": Category.Tipo.INGRESO, "activa": True},
    )
    if categoria.tipo != Category.Tipo.INGRESO:
        raise ValidationError("La categoría contable de cobranza no está configurada como ingreso.")
    transaccion = Transaction.objects.create(
        organizacion=pago.organizacion,
        categoria=categoria,
        fecha=pago.fecha_pago,
        tipo=Transaction.Tipo.INGRESO,
        monto=pago.monto_total,
        descripcion=pago.observaciones.strip()
        or f"Pago de clases de {pago.persona.nombre_completo}",
        creado_por=pago.registrado_por,
    )
    pago.transaccion = transaccion
    pago.save(update_fields=["transaccion", "actualizado_en"])

    registrar_auditoria(
        usuario=usuario,
        accion=AuditLog.ACCION_CREAR,
        dominio="finanzas",
        objeto=transaccion,
        organizacion=pago.organizacion,
        resumen="Transacción creada desde pago operacional",
        metadata={
            "pago_id": pago.pk,
            "transaccion_id": transaccion.pk,
            "origen": origen,
        },
    )
    registrar_auditoria(
        usuario=usuario,
        accion=AuditLog.ACCION_CREAR,
        dominio="finanzas",
        objeto=pago,
        organizacion=pago.organizacion,
        resumen="Pago creado",
        metadata={
            "pago_id": pago.pk,
            "lote_id": str(lote.pk) if lote else None,
            "transaccion_id": transaccion.pk,
            "disciplina_id": pago.disciplina_id,
            "clave_idempotencia": clave_idempotencia,
            "origen": origen,
        },
    )
    return pago


@transaction.atomic
def sincronizar_transaccion_pago(*, pago, usuario=None):
    """Mantiene el movimiento enlazado consistente después de una edición autorizada."""
    pago = Payment.objects.select_for_update().select_related("persona").get(pk=pago.pk)
    if not pago.transaccion_id:
        return pago
    transaccion = Transaction.objects.select_for_update().get(pk=pago.transaccion_id)
    transaccion.fecha = pago.fecha_pago
    transaccion.monto = pago.monto_total
    transaccion.descripcion = pago.observaciones.strip() or f"Pago de clases de {pago.persona.nombre_completo}"
    transaccion.save(update_fields=["fecha", "monto", "descripcion", "actualizado_en"])
    registrar_auditoria(
        usuario=usuario,
        accion=AuditLog.ACCION_EDITAR,
        dominio="finanzas",
        objeto=transaccion,
        organizacion=pago.organizacion,
        resumen="Transacción sincronizada desde pago",
        metadata={"pago_id": pago.pk, "transaccion_id": transaccion.pk},
    )
    return pago


def _resolver_fila_pago(*, fila, organizacion_id):
    persona = Persona.objects.filter(
        pk=fila["persona_id"],
        roles__organizacion_id=organizacion_id,
        roles__rol__codigo__iexact="ESTUDIANTE",
        roles__activo=True,
    ).first()
    if not persona:
        raise ValidationError("La persona seleccionada no es elegible para la organización.")
    plan = None
    if fila.get("plan_id"):
        plan = PaymentPlan.objects.filter(pk=fila["plan_id"], organizacion_id=organizacion_id, activo=True).first()
        if not plan:
            raise ValidationError("El plan seleccionado no pertenece a la organización o no está activo.")
    documento = None
    if fila.get("documento_tributario_id"):
        documento = DocumentoTributario.objects.filter(
            pk=fila["documento_tributario_id"], organizacion_id=organizacion_id
        ).first()
        if not documento:
            raise ValidationError("El documento seleccionado no pertenece a la organización.")
    return persona, plan, documento


@transaction.atomic
def confirmar_lote_pagos(
    *, usuario, organizacion_id, clave_idempotencia, filas, metadatos=None, respaldo=None
):
    """Confirma todas las filas o ninguna; una clave solo puede producir un lote."""
    try:
        with transaction.atomic():
            lote = LotePago.objects.create(
                organizacion_id=organizacion_id,
                clave_idempotencia=clave_idempotencia,
                creado_por=usuario,
                respaldo=respaldo,
                metadatos=metadatos or {},
            )
    except IntegrityError:
        lote = LotePago.objects.select_for_update().filter(clave_idempotencia=clave_idempotencia).first()
        if lote:
            if lote.organizacion_id != organizacion_id:
                raise ValidationError("La clave de idempotencia ya pertenece a otra organización.")
            return lote, False
        raise

    pagos = []
    try:
        personas_vistas = set()
        for indice, fila in enumerate(filas):
            if fila["persona_id"] in personas_vistas:
                raise ValidationError("Una persona no puede repetirse dentro del lote.")
            personas_vistas.add(fila["persona_id"])
            persona, plan, documento = _resolver_fila_pago(fila=fila, organizacion_id=organizacion_id)
            disciplina = None
            if fila.get("disciplina_id"):
                from asistencias.models import Disciplina

                disciplina = Disciplina.objects.filter(
                    pk=fila["disciplina_id"],
                    organizacion_id=organizacion_id,
                    activa=True,
                ).first()
                if not disciplina:
                    raise ValidationError("La disciplina no pertenece a la organización o no está activa.")
            pago = Payment(
                persona=persona,
                organizacion_id=organizacion_id,
                plan=plan,
                disciplina=disciplina,
                documento_tributario=documento,
                fecha_pago=fila["fecha_pago"],
                metodo_pago=fila["metodo_pago"],
                numero_comprobante=fila.get("numero_comprobante", ""),
                aplica_iva=fila.get("aplica_iva", True),
                monto_incluye_iva=fila.get("monto_incluye_iva", False),
                monto_referencia=fila["monto_referencia"],
                clases_asignadas=fila.get("clases_asignadas", 0),
                observaciones=fila.get("observaciones", ""),
            )
            clave_item = fila.get("clave_idempotencia") or (
                f"{clave_idempotencia}:{indice}:{persona.pk}"
            )
            pagos.append(
                crear_pago_operacional(
                    pago=pago,
                    usuario=usuario,
                    lote=lote,
                    origen="pago_masivo",
                    clave_idempotencia=clave_item,
                )
            )
        lote.cantidad_pagos = len(pagos)
        lote.monto_total = sum((pago.monto_total for pago in pagos), 0)
        lote.confirmado_en = timezone.now()
        lote.save(update_fields=["cantidad_pagos", "monto_total", "confirmado_en", "actualizado_en"])
        registrar_auditoria(
            usuario=usuario,
            accion=AuditLog.ACCION_CREAR,
            dominio="finanzas",
            objeto=lote,
            organizacion=lote.organizacion,
            resumen="Lote de pagos confirmado",
            metadata={
                "lote_id": str(lote.pk),
                "pago_ids": [pago.pk for pago in pagos],
                "cantidad_pagos": lote.cantidad_pagos,
                "monto_total": lote.monto_total,
                "transaccion_ids": [pago.transaccion_id for pago in pagos],
                "origen": "pago_masivo",
            },
        )
    except Exception:
        raise
    return lote, True


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
        telefono=form.cleaned_data.get("telefono", ""),
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
        if pago.revertido_en and hasattr(pago, "saldo_clases_calculado"):
            pago.saldo_clases_calculado = 0
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
    "confirmar_lote_pagos",
    "crear_pago_operacional",
    "crear_persona_estudiante_desde_modal",
    "enriquecer_pagos_para_listado",
    "resumen_consumos_pago",
    "sincronizar_transaccion_pago",
    "texto_copiable_operativo_pago",
]

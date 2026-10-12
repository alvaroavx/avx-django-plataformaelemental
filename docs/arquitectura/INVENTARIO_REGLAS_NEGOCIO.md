# Inventario de reglas de negocio

Fecha de actualización: 2026-10-12

Este inventario referencia la implementación vigente. No reemplaza los tests ni
los documentos dueños de cada app.

## Identidad y organizaciones

| Regla | Implementación principal |
| --- | --- |
| Persona requiere RUT, email o teléfono y normaliza RUT/teléfono. | `personas/models.py`, `personas/validators.py`, `personas/utils.py` |
| El rol pertenece a persona + organización y esa combinación es única. | `personas/models.py:PersonaRol` |
| Google autentica identidad, pero no asigna roles u organizaciones. | `personas/auth_google.py`, `personas/identidades_google.py` |
| Una solicitud pendiente es única por identidad Google y por email normalizado. | `personas/models.py:SolicitudAcceso` |
| Aprobar/rechazar/reabrir requiere permiso Django global explícito. | `personas/resolucion_solicitudes.py`, `personas/views.py` |

## Autorización

| Regla | Implementación principal |
| --- | --- |
| Acciones se mapean a roles normalizados. | `personas/permissions.py` |
| Asistencias limita objetos a organizaciones/roles vigentes y no da bypass a staff ordinario. | `asistencias/selectors.py`, `asistencias/decorators.py`, `asistencias/views.py` |
| Sin portal dedicado (ADR 0016). En el árbol de trabajo (sin commitear, ADR 0018/0019) Profesor puede ver solo sesiones donde figura como profesor (`ver_calendario`) y agregar alumnos vinculados a la disciplina en esas sesiones (`agregar_asistentes_propios`); ambas capacidades se pueden deshabilitar por organización. | `personas/permissions.py`, `asistencias/selectors.py`, `asistencias/views.py` |
| Personas y Finanzas todavía conservan bypass histórico de `is_staff`. | `personas/permissions.py`, decoradores consumidores |

## Operación académica

| Regla | Implementación principal |
| --- | --- |
| Disciplina es única por organización + nombre + nivel. | `asistencias/models.py:Disciplina` |
| Asistencia es única por sesión + persona. | `asistencias/models.py:Asistencia` |
| Estudiante agregado puede reactivar Persona y rol de la organización real. | `asistencias/services/dominio.py`, `asistencias/views.py` |
| Clase liberada conserva asistencia, motivo, actor y reversa. | `asistencias/models.py:ClaseLiberada`, `asistencias/services/dominio.py` |
| Filtros globales son periodo y organización; no conceden permiso. | `plataformaelemental/context.py` |

## Cobranza operacional

| Regla | Implementación principal |
| --- | --- |
| Cada asistencia tiene como máximo un consumo financiero. | `finanzas/models.py:AttendanceConsumption` |
| Presente, ausente y justificada consumen derecho mensual o generan deuda. | `finanzas/services/imputacion.py`, `finanzas/signals.py` |
| Pago y clase deben coincidir en persona, organización, mes/año y vigencia del plan. | `finanzas/services/imputacion.py` |
| Pago revertido no otorga derecho y fuerza recálculo de consumos. | `finanzas/services/reversas.py` |
| Clase liberada activa queda pendiente, sin pago ni deuda. | `finanzas/services/imputacion.py` |
| Pago masivo revalida todas las filas, es atómico e idempotente. | `finanzas/services/pagos.py`, `finanzas/views.py` |
| Todo pago nuevo confirmado por el servicio crea una transacción contable uno-a-uno; pagos históricos pueden carecer de vínculo. | `finanzas/models.py`, `finanzas/services/pagos.py` |

## Movimientos de caja

| Regla | Implementación principal |
| --- | --- |
| Transaction toma ingreso/egreso desde la categoría y alimenta libro de caja. | `finanzas/forms.py`, `finanzas/selectors.py`, `finanzas/services/reportes.py` |
| Payment y Transaction no son intercambiables y pueden enlazarse uno a uno. | `finanzas/models.py`, `docs/apps/FINANZAS.md` |

## Integración con Cuadratura

| Regla | Implementación principal |
| --- | --- |
| Solo pagos con `fecha_pago` en el mes, no revertidos, con transacción de ingreso de la misma organización, monto total igual y montos CLP enteros se exportan como operación; el resto va a `pending_records` con motivos. | `finanzas/services/cuadratura_v1.py:prepare_month` |
| `batch_id` es SHA-256 de organización, período e IDs de operaciones incluidas; la generación no muta registros. | `finanzas/services/cuadratura_v1.py`, `finanzas/tests.py` |
| La exportación exige organización, mes y año concretos y la acción `exportar_datos` (roles Admin/Finanzas; `is_staff` conserva bypass). | `finanzas/views.py:preparar_mes`, `finanzas/views.py:descargar_cuadratura` |
| Un mes se envía a la API de Cuadratura solo si terminó, está configurado (https salvo DEBUG), tiene operaciones y no tiene pendientes salvo pagos revertidos; el último intento `en_curso`, `enviado` o `incierto` bloquea crear, editar, revertir o eliminar pagos del mes y sus transacciones enlazadas; cada request va firmado con Ed25519. | `finanzas/services/cuadratura_api.py`, `finanzas/models.py:validar_meses_no_enviados`, `finanzas/test_envio_cuadratura.py` |

## Auditoría y API

| Regla | Implementación principal |
| --- | --- |
| Auditoría se crea después del commit y no revierte el negocio si falla. | `auditoria/services.py` |
| API pública solo ofrece health/status/version; `me` requiere usuario. | `api/urls.py`, `api/views.py` |
| API key solo puede autorizar métodos seguros, aunque hoy no hay endpoints de datos. | `api/authentication.py`, `api/permissions.py` |

## Reglas pendientes de endurecimiento

- Eliminar el bypass global de `is_staff` requiere una decisión y migración de permisos.
- Varias invariantes son de aplicación y no constraints PostgreSQL.
- No existe conciliación formal entre pagos y transacciones dentro de Elemental; la conciliación fiscal pertenece a Cuadratura (ADR 0015).
- No existe política productiva única de bajas/cascadas.
- `Category` sigue siendo catálogo global entre organizaciones.

Riesgos priorizados: [docs/ESTADO_ACTUAL.md](../ESTADO_ACTUAL.md).

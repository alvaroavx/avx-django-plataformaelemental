# Finanzas

Fecha de actualización: 2026-10-12

## Propósito

La app `finanzas` administra la cobranza operacional de clases y los movimientos
de caja de Plataforma Elemental. La documentación fiscal, conciliación y cierres
contables pertenecen a Cuadratura.

## Alcance vigente

- Planes de pago por organización.
- Pagos individuales y lotes de pago idempotentes (pago masivo).
- Consumo de clases, saldos, deudas y reversas auditables.
- Transacciones de ingreso o egreso y sus categorías.
- Panel financiero, reporte por categorías y exportaciones operacionales.
- Exportación JSON versionada Elemental → Cuadratura (`elemental-cuadratura-v1`).
- Envío del mes a la API v1 de Cuadratura (`cuadratura-operations-v1`) con bloqueo del mes enviado (ADR 0023).

Quedan fuera de esta app los comprobantes fiscales, sus archivos XML/PDF, su
importación, almacenamiento, asociación y edición (ADR 0015, migración
`finanzas.0013_remove_transaction_documentos_tributarios_and_more`).

## Modelo

- `PaymentPlan`: oferta de clases y precio por organización.
- `Payment`: pago operacional de una persona; puede enlazarse uno a uno con una
  `Transaction` y conserva sus propios montos (`monto_neto`, `monto_iva`,
  `monto_total`), clases asignadas, clave de idempotencia y datos de reversa.
- `LotePago`: confirmación masiva con clave de idempotencia (PK UUID).
- `AttendanceConsumption`: imputación de una asistencia a un pago o deuda.
- `Category`: clasificación de movimientos de caja.
- `Transaction`: ingreso o egreso de una organización, con archivo de respaldo opcional.

`Payment` y `Transaction` no son intercambiables: el primero responde por la
cobranza de clases y el segundo por el movimiento de dinero.

Todos los montos de dinero (`PaymentPlan.precio`, montos de `Payment`,
`Transaction.monto`, `LotePago.monto_total`) son pesos chilenos enteros
(`BigIntegerField`, ADR 0022). `desglosar_montos()` aplica la regla de
Cuadratura con IVA 19 % y `ROUND_HALF_UP`: con IVA incluido, `neto =
round(total / 1,19)` e `iva = total - neto`; con IVA agregado, `iva =
round(neto × 0,19)`. Siempre se cumple `neto + iva = total`. Si la organización
es `es_exenta_iva`, el pago se guarda con `aplica_iva = False`.

## Reglas principales

- Todo queryset financiero se limita a las organizaciones autorizadas para el usuario.
- Los filtros globales de organización y período se preservan entre vistas.
- `services/pagos.py::crear_pago_operacional` crea el `Payment` y exactamente una
  `Transaction` de ingreso (categoría `Cobranza de clases`, creada si no existe)
  en la misma unidad atómica. Editar un pago sincroniza fecha, monto y
  descripción de su transacción enlazada. Los pagos históricos pueden conservar
  `transaccion = NULL`.
- Una reversa no elimina el pago: conserva motivo, autor y fecha, y recalcula
  los consumos afectados. **No** modifica ni anula la `Transaction` enlazada.
- La imputación se ejecuta por señales (`finanzas/signals.py`): cada `Asistencia`
  guardada asigna su consumo y cada `Payment` nuevo se imputa a deudas del mismo
  mes y año según `services/imputacion.py`.
- Los montos exportados a Cuadratura son CLP enteros y conservan identificadores estables.
- Un registro enviado a Cuadratura no acredita por sí mismo la emisión de un comprobante fiscal.

## Capas

- `models.py`: persistencia e integridad.
- `forms.py` y `forms_helpers.py`: validación de entrada para pagos, planes, categorías y transacciones.
- `selectors.py`: consultas y agregaciones sin efectos secundarios.
- `decorators.py`: decoradores de permiso sobre `personas.permissions`.
- `signals.py`: imputación automática asistencia ↔ pago.
- `services/pagos.py`: alta de pagos, lotes, sincronización con la transacción y saldos.
- `services/imputacion.py`: derecho de clase, consumo, deuda y resumen por estudiante.
- `services/reversas.py`: reversa auditada de pagos.
- `services/reconciliacion.py`: diagnóstico de integridad asistencias/consumos/pagos.
- `services/reportes.py`: composición del panel y filas de exportación.
- `services/cuadratura_v1.py`: contrato de salida hacia Cuadratura.
- `services/cuadratura_api.py`: traducción al contrato genérico de Cuadratura, envío por API y estado del envío.
- `views.py`: autorización y coordinación HTTP.

Comando de diagnóstico (solo lectura; termina con error si hay inconsistencias):

```bash
python manage.py reconciliar_integridad_dominio
```

## Rutas y exportaciones

Bajo `/finanzas/`: panel, planes, pagos (individual, masivo, detalle, edición,
reversa), categorías, transacciones (detalle, archivo protegido, edición,
eliminación), `reportes/categorias/` y `preparar-mes/`.

Exportaciones (permiso `exportar_datos`):

- `export/pagos.csv`, `export/pagos-alumnos.xlsx`.
- `export/transacciones.csv`, `export/transacciones.xlsx`, `export/libro-caja.csv`.
- `export/pagos-profesores.xlsx`: estimación de pago a profesores calculada con
  `asistencias/services/exportaciones.py`; no es un pago registrado.
- `preparar-mes/descargar/`: archivo JSON para Cuadratura (ver sección siguiente).
- `preparar-mes/enviar/` (POST): envía el mes a la API de Cuadratura (ver «Envío por API»).

## Contrato Elemental → Cuadratura v1

### Lo que existe

Implementación: `finanzas/services/cuadratura_v1.py` (`prepare_month`,
`serialize_contract`) y las vistas `preparar_mes` y `descargar_cuadratura` de
`finanzas/views.py`.

- **Acceso:** `/finanzas/preparar-mes/` muestra el resumen y los registros
  pendientes; `/finanzas/preparar-mes/descargar/` entrega el archivo. Ambas exigen
  `exportar_datos` (Administrador, Finanzas, `is_staff` o superusuario) y una
  organización, mes y año específicos. Sin ellos la descarga responde `400` en
  texto plano.
- **Archivo:** JSON UTF-8, indentado, claves ordenadas, nombre
  `elemental_cuadratura_AAAA-MM.json`. Es transporte manual; el envío directo
  usa otro contrato (ver «Envío por API»).
- **Selección:** `Payment` de la organización con `fecha_pago` dentro del mes
  (`selection.criterion = confirmed_payment_date_in_period`), ordenados por id.
  No muta datos.
- **Raíz del documento:** `contract_version` (`elemental-cuadratura-v1`),
  `origin_system` (`ELEMENTAL`), `batch_id`, `generated_at`,
  `source_organization` (`organization:<pk>`, nombre), `expected_taxpayer`
  (`tax_id` = `Organizacion.rut`, `legal_name` = razón social o nombre),
  `selection` (`period`, `timezone` = `America/Santiago`, `criterion`),
  `operations`, `pending_records` y `summary` (`operations`, `payments`,
  `pending`, `total_payments`).
- **Operación:** una por pago elegible, con `external_id` =
  `transaction:<pk>`, `operation_date` = fecha de la transacción enlazada,
  `service_period` = período seleccionado, `concept` = `workshop_classes`,
  `detail` (descripción de la transacción o `Pago de clases`), `plan`,
  `discipline`, `beneficiary` (`person:<pk>` y nombre), `buyer` siempre `null`,
  `tax` y una lista `payments` con un único elemento (`payment:<pk>`,
  `payment_date`, `amount`, `status` siempre `CONFIRMED`, `method` según
  `Payment.Metodo`, `reference` = número de comprobante). Los textos se truncan
  (500/200/160 caracteres).
- **Clasificación tributaria:** `EXEMPT` si la organización es exenta de IVA o
  el pago no aplica IVA; en otro caso `TAXABLE`. `net`, `vat` y `total` vienen de
  `monto_neto`, `monto_iva` y `monto_total` del pago.
- **Registros pendientes:** un pago no se exporta como operación y se declara en
  `pending_records` (`payment:<pk>` y motivos ordenados) si tiene alguno de:
  `payment_reversed`, `missing_linked_transaction`, `invalid_linked_transaction`
  (otra organización o tipo distinto de ingreso), `transaction_amount_mismatch`
  o `non_integer_clp_amount` (guarda defensiva; desde ADR 0022 los montos son
  enteros y este motivo no debería aparecer).
- **`batch_id`:** SHA-256 de `organización|período|external_id` de las
  operaciones incluidas. Es estable mientras no cambie el conjunto de
  operaciones; `generated_at` cambia en cada descarga.
- **Pruebas:** `finanzas/tests.py` cubre una operación válida (sin mutar el
  pago) y un pago sin transacción enlazada.

### Envío por API (ADR 0023)

- **Dónde:** botón «Enviar a Cuadratura» en `/finanzas/preparar-mes/`, con permiso
  `exportar_datos` y una casilla obligatoria que confirma el bloqueo.
- **Contrato:** `construir_documento` traduce `prepare_month` a
  `cuadratura-operations-v1`, el contrato genérico que define Cuadratura.
  - Sin `origin_system`: lo fija el token.
  - `customer_name` viene del nombre del beneficiario.
  - `pending_records` pasa a `excluded_records`.
  - `batch_id` es el SHA-256 del documento sin `generated_at`.
- **Llamadas:** `GET {CUADRATURA_API_URL}/api/v1/` para elegir la organización por
  RUT, y luego `POST .../organizations/{id}/periods/AAAA-MM/batches/`. Usa
  `Authorization: Bearer {CUADRATURA_API_TOKEN}` y el timeout
  `CUADRATURA_API_TIMEOUT`.
- **Condiciones (`estado_envio`):**
  - el mes terminó;
  - la integración está configurada, con `https://` salvo en `DEBUG`;
  - hay operaciones;
  - no hay pendientes salvo `payment_reversed`.
- **Registro:** cada intento crea `EnvioCuadratura` y un `AuditLog`. Los estados son
  `en_curso`, `enviado`, `incierto`, `rechazado` y `fallido`.
  - Bloquean el mes `en_curso`, `enviado` e `incierto`. El intento `en_curso` se
    registra antes de leer los datos, para que nadie edite durante el envío.
  - `incierto` se reintenta con el mismo contenido.
  - `rechazado` y `fallido` liberan el mes.
  - Tabla completa en el ADR 0023.
- **Firma:** cada request va firmado con Ed25519 usando la llave de
  `CUADRATURA_API_PRIVATE_KEY_FILE` (comando `generar_llave_cuadratura`). No se
  siguen redirecciones.
- **Bloqueo:** `validar_meses_no_enviados` (según el último intento del mes) impide crear, editar, revertir o eliminar
  pagos con `fecha_pago` en un mes enviado, o moverlos desde o hacia él.
  - También impide editar o eliminar las transacciones enlazadas a esos pagos.
  - Se aplica en `Payment.save/delete`, en `Transaction.save/delete` y en los
    formularios de pago, pago masivo y transacción.
  - Para desbloquear, un superusuario elimina el envío desde la base. No hay
    pantalla para eso.
- **Pruebas:** `finanzas/test_envio_cuadratura.py`.

### Planificado / no implementado

- Reenvío, corrección o anulación de un mes ya enviado (hoy el mes queda bloqueado).
- Consultar desde Elemental si Cuadratura ya confirmó el lote (la API lo permite con
  `GET .../batches/{id}/`, pero Elemental no lo consulta).
- Auditoría de la descarga manual: hoy no se registra en `AuditLog` (el envío sí).

## Seguridad y auditoría

- Los roles Administrador y Finanzas operan la app según la matriz de permisos;
  Solo lectura puede ver finanzas, sin operar ni exportar.
- Profesor no tiene permisos financieros (`personas/permissions.py::ACCION_ROLES`):
  no registra pagos, no exporta y no accede a las vistas protegidas por
  `ver_finanzas`. El pago masivo y su resultado exigen `operar_pagos` en
  la organización real del lote, sin excepción por `is_staff`.
- Las acciones sensibles registran ids, montos y fechas; no adjuntos ni datos personales completos.
- La API pública de Elemental no expone pagos ni transacciones. El token de Cuadratura vive solo en la variable de entorno `CUADRATURA_API_TOKEN` y la llave privada en el archivo de `CUADRATURA_API_PRIVATE_KEY_FILE`, fuera del repo y con permisos 600. Ninguno se guarda en base de datos, auditoría ni mensajes de error.

## Validación esperada

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test finanzas
```

El detalle de la frontera con Cuadratura está en el ADR 0015 y en la
documentación transversal del workspace.

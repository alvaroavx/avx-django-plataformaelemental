# Finanzas

Fecha de actualización: 2026-10-08

## Propósito

La app `finanzas` administra la cobranza operacional de clases y los movimientos
de caja de Plataforma Elemental. La documentación fiscal, conciliación y cierres
contables pertenecen a Cuadratura.

## Alcance vigente

- Planes de pago por organización.
- Pagos individuales y lotes de pago idempotentes.
- Consumo de clases, saldos, deudas y reversas auditables.
- Transacciones de ingreso o egreso y sus categorías.
- Panel financiero y exportaciones operacionales.
- Exportación JSON versionada Elemental → Cuadratura.

Quedan fuera de esta app los comprobantes fiscales, sus archivos XML/PDF, su
importación, almacenamiento, asociación y edición.

## Modelo

- `PaymentPlan`: oferta de clases y precio por organización.
- `Payment`: pago operacional de una persona; puede enlazarse uno a uno con una
  `Transaction` y conserva sus propios montos, clases y estado.
- `LotePago`: confirmación masiva con clave de idempotencia.
- `AttendanceConsumption`: imputación de una asistencia a un pago o deuda.
- `Category`: clasificación de movimientos de caja.
- `Transaction`: ingreso o egreso de una organización.

`Payment` y `Transaction` no son intercambiables: el primero responde por la
cobranza de clases y el segundo por el movimiento de dinero.

## Reglas principales

- Todo queryset financiero se limita a las organizaciones autorizadas para el usuario.
- Los filtros globales de organización y período se preservan entre vistas.
- Una confirmación de pago crea su movimiento enlazado cuando corresponde; los
  pagos históricos pueden conservar `transaccion = NULL`.
- Una reversa no elimina el pago: conserva motivo, autor y fecha.
- La imputación consume asistencias del mismo mes y año conforme a las reglas del servicio.
- Los montos exportados a Cuadratura son CLP enteros y conservan identificadores estables.
- Un registro enviado a Cuadratura no acredita por sí mismo la emisión de un comprobante fiscal.

## Capas

- `models.py`: persistencia e integridad.
- `forms.py`: validación de entrada para pagos, planes, categorías y transacciones.
- `selectors.py`: consultas y agregaciones sin efectos secundarios.
- `services/pagos.py`: alta y reversa de pagos, saldos e imputación.
- `services/reportes.py`: composición del panel y exportaciones.
- `services/cuadratura_v1.py`: contrato de salida hacia Cuadratura.
- `views.py`: autorización y coordinación HTTP.

## Seguridad y auditoría

- Los roles Administrador y Finanzas operan la app según la matriz de permisos.
- Profesor puede registrar pagos solo dentro de su espacio y alcance autorizado.
- Las acciones sensibles registran ids, montos y fechas; no adjuntos ni datos personales completos.
- La API pública no expone pagos ni transacciones.

## Validación esperada

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test finanzas
```

El detalle de la frontera con Cuadratura está en el ADR 0015 y en la
documentación transversal del workspace.

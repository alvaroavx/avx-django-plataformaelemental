# ADR 0022: montos en pesos chilenos enteros con la regla de IVA de Cuadratura

- Estado: aceptada
- Fecha: 2026-10-12
- Decisor: Álvaro

## Contexto

Elemental guardaba precios, pagos, transacciones y tarifas como `Decimal` con dos
decimales y calculaba el IVA redondeando a centavos. El peso chileno no usa
decimales y Cuadratura, que es dueña de la documentación fiscal, trabaja solo con
enteros (`sales/services.py`: `neto = round(total / 1,19)`, `iva = total - neto`).
Por eso el exportador del contrato v1 dejaba en `pending_records` como
`non_integer_clp_amount` todo pago afecto cuyo IVA no fuera entero, y esos pagos
nunca llegaban a Cuadratura.

## Alternativas descartadas

- Redondear solo al exportar: deja dos verdades de monto entre Elemental y Cuadratura.
- Mantener `DecimalField` y guardar siempre `.00`: no impide que vuelvan a entrar decimales.

## Decisión

- `PaymentPlan.precio`, `Payment.monto_referencia/neto/iva/total`,
  `Transaction.monto`, `LotePago.monto_total` y `PersonaRol.valor_clase` pasan a
  `BigIntegerField`. `retencion_sii` sigue siendo porcentaje decimal.
- `finanzas.models.desglosar_montos()` es la única regla de cálculo. Con IVA incluido
  el total manda (`neto = round(total / 1,19)`). Con IVA agregado,
  `iva = round(neto × 0,19)`; esto da el mismo resultado que aplicar la regla de
  Cuadratura sobre el total. Redondeo `ROUND_HALF_UP`.
- La migración `finanzas.0014` redondea los datos existentes tomando como ancla el
  total cobrado: total redondeado al peso, neto e IVA recalculados con la regla
  anterior y el total de cada lote recalculado como suma de sus pagos.
  `finanzas.0015` y `personas.0012` cambian el tipo de columna.
- No se agregan restricciones nuevas de signo; se conserva el comportamiento previo.

## Consecuencias asumidas

- El redondeo de datos existentes es irreversible: la migración inversa restaura el
  tipo `Decimal`, pero no los centavos originales. `scripts/deploy.sh` respalda la
  base con `pg_dump` antes de migrar.
- Un pago con IVA agregado sobre un neto no divisible puede cambiar su total en
  menos de un peso.
- Los formularios rechazan montos con decimales.
- El motivo `non_integer_clp_amount` del exportador queda como guarda defensiva.

## Condiciones de revisión

Revisar si Cuadratura o la contraparte contable cambian la regla de redondeo del IVA.

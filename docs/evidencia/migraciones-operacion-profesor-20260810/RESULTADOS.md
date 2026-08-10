# Evidencia de migraciones Operación Profesor

Fecha: 2026-08-10

## Alcance real

Se usó un clúster PostgreSQL 18.4 aislado y datos completamente sintéticos. No se
conectó ni modificó producción y no hubo una copia productiva disponible en este
checkout. Por ello la evidencia valida código, herramientas y mecánica, pero no
autoriza el despliegue.

## Resultado

- `asistencias.0004` migró desde cero con backfill histórico inactivo.
- El reporte sanitizado ejecutó con `--fallar-si-inseguro` y cero relaciones en
  este dataset financiero sintético; el test de backfill separado comprobó una
  asignación y una matrícula históricas, ambas inactivas.
- `finanzas.0012` migró 300.000 pagos y 100.000 transacciones en 2,335 s.
- Mayor latencia observada en la escritura con rollback: 967,264 ms; cero errores.
- Cero pagos/transacciones/imputaciones históricas inventadas.
- Backup custom y restauración real pasaron con conteos, sumas y migraciones
  coincidentes.
- `manage.py check`: 0 issues; `makemigrations --check --dry-run`: sin cambios.
- Regresión histórica final: 8 tests OK en 1,538 s; Operación Profesor +
  relaciones: 16 tests OK en 7,792 s antes del ajuste mecánico de lotes.
- Transición, activación masiva y reversa: 12 tests OK en 0,812 s contra PostgreSQL 18
  temporal; incluye rollback total si el lote cruza una organización no
  autorizada y confirma que el reporte no autoactiva relaciones.
- Regresión integrada final: 87 tests OK en 247,997 s contra PostgreSQL 18
  UTF-8 (`relaciones_historicas`, Operación Profesor y acceso financiero). Un
  intento `SQL_ASCII` fue descartado por no poder almacenar JSON Unicode.
- Suite completa PostgreSQL: 418 tests OK, 12 omitidos, en 541,362 s.
- `ruff check .`, `git diff --check`, 84 enlaces Markdown y 13 diagramas
  Mermaid: OK.
- El primer intento de monitor se invalidó porque su propia conexión estaba
  `idle in transaction`; se terminaron exclusivamente esas conexiones en la
  base temporal, se corrigió a autocommit y se reemplazó la medición. No se usa
  el intento inválido como resultado.

## Archivos

- `ensayo-sintetico-finanzas-0012.json`: preflight, muestras, locks, escritura y
  postflight sanitizados.
- `reporte-relaciones-historicas-sintetico.json`: salida de solo conteos.
- `sql-asistencias-0004.sql` y `sql-finanzas-0012.sql`: SQL generado y formateado.
- El runbook y el gate están en
  `docs/operacion/MIGRACIONES_OPERACION_PROFESOR.md`.

## Gate posterior

El gate QA original quedó reemplazado por una ventana productiva manual aceptada
para el piloto. Este workspace no dispone de QA/staging y no usó producción. El
runbook exige que infraestructura ejecute preflight, backup, mediciones,
transición y smoke antes de abrir tráfico. El antecedente y los 12 tests omitidos
se detallan en [ENSAYO_QA_Y_TRANSICION.md](ENSAYO_QA_Y_TRANSICION.md).

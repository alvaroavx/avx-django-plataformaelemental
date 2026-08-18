# ADR 0002: Release defensivo de `asistencias.0005`

Fecha: 2026-08-18

Estado: aceptado para preparación local; despliegue en NO-GO hasta publicar un
SHA y tag autorizados.

## Contexto

`asistencias.0005_reparar_schema_0004_aplicada_precommit` corrige bases que
hubieran aplicado una versión precommit de `0004`. La migración es
`atomic=False`, puede ejecutar DDL y actualizaciones, y no tiene reversa. Al mismo
tiempo, una instalación limpia puede tener `0004` y `finanzas.0012` pendientes,
mientras producción puede tener ambas aplicadas y solo `0005` pendiente.

El script histórico `release_operacion_profesor.sh` está ligado a un tag anterior
y no conoce `0005`. El deploy genérico termina en `migrate` global y tampoco
expresa esta reparación como una etapa independiente.

## Decisión

- Mantener inmutables el tag y script históricos.
- Crear `scripts/release_asistencias_0005.sh` con identidad por tag anotado, SHA
  exacto entregado y padre esperado.
- Verificar el artefacto directamente desde el objeto Git, sin checkout; entrar
  después a mantenimiento y completar snapshot, dump y restauración antes de
  cambiar el checkout o instalar dependencias en el virtualenv.
- Admitir únicamente dos estados iniciales: Ruta A (`0004` y `0012` aplicadas) y
  Ruta B (las tres migraciones pendientes).
- Inspeccionar esquema y conteos agregados con PostgreSQL read-only antes de
  decidir la ruta.
- Exigir dump restaurado, snapshot previo, mantenimiento y `lock_timeout=5s`.
- Ejecutar solo migraciones con app y destino explícitos; nunca `migrate` global.
- Mantener reporte y activación administrativa como gates humanos visibles. Si
  el reporte tiene cero pendientes, registrar explícitamente que no se requieren
  activaciones; si tiene uno o más, exigir un `User.id` activo con permisos
  administrativos reales en todo el alcance y confirmación literal.
- Tratar un fallo parcial de `0005` como incidente forward-only: se conserva
  mantenimiento, se diagnostica sin escribir y solo se reintenta la misma
  migración cuando permanece pendiente y el esquema es compatible.

## Consecuencias

- Un estado de base no reconocido detiene la ventana en lugar de inferir una
  ruta.
- El SHA final se entrega fuera del contenido autorreferente del commit; en
  ejecución debe coincidir con `HEAD` y con el tag.
- No existe downgrade automático, restauración automática ni rollback de
  aplicación asumido después de `0005`.
- La evidencia versionable se limita a Markdown y JSON agregado sanitizado. Los
  logs nominales, dumps, snapshots y actas operativas permanecen fuera de Git.

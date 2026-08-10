# Deuda técnica activa

Fecha de actualización: 2026-08-09

Este documento lista deuda verificable del código actual. La fotografía completa,
incluidos riesgos operativos y de datos, está en [ESTADO_ACTUAL](../ESTADO_ACTUAL.md).

## Alta

### Permisos no uniformes entre apps

Estado: activa.

Asistencias no concede bypass operativo a `is_staff`, pero los helpers compartidos
y consumidores de Personas/Finanzas todavía lo permiten por defecto. El alcance
por organización tampoco está centralizado para toda superficie futura.

Acción segura: inventariar actores y superficies, escribir la matriz definitiva,
crear una cuenta administrativa de reemplazo y probarla antes de retirar privilegios.
Incluir Django Admin: varias acciones masivas estándar siguen disponibles y la
lectura de `AuditLog` no está aislada por organización.

### Operaciones destructivas y cascadas productivas

Estado: activa.

`Persona.user` usa `CASCADE`; organizaciones, personas y sesiones también tienen
cascadas amplias, combinadas con algunas protecciones financieras. La UI evita
varios borrados, pero shell, Admin, migraciones o código futuro pueden activar el
grafo real.

Acción segura: documentar bajas soportadas, preferir desactivación/reversa, añadir
preview y probar sobre copia antes de cambiar `on_delete` o datos.

### Runtime productivo no reproducido desde el repo

Estado: no confirmado.

El usuario informa que el sitio está en producción y el repositorio contiene
deploy automatizado, pero este levantamiento no verificó el servidor, commit,
Python/PostgreSQL, flags, Nginx, media ni restauración de backups.

Acción segura: auditoría read-only del servidor y simulacro de `pg_restore`.

### Posibles datos reales versionados

Estado: activa.

`data/` contiene cargas de alumnos y `public/` PDFs tributarios no referenciados
por runtime/tests. Sus nombres parecen reales; no deben asumirse fixtures.

Acción segura: confirmar dueño/retención, retirar del HEAD si corresponde y decidir
si la exposición justifica limpiar historial. No copiar contenido a documentación.

## Media

### Dos subdominios dentro de Finanzas

Estado: activa controlada.

Cobranza y contabilidad comparten app. Hay services/selectors y paquete de
documentos, pero las views aún coordinan casos de uso grandes.

Acción: extraer incrementalmente sin crear otra app hasta que existan ciclo de
vida, modelos y permisos realmente independientes.

### Reglas solo en aplicación

Estado: activa.

Compatibilidad de organización, contraparte exclusiva y plan por defecto dependen
en parte de forms/services. Escrituras futuras podrían omitirlos.

Acción: estabilizar reglas y datos antes de añadir constraints compatibles.

### Desalineación de Python y selección de entorno

Estado: activa.

PR usa Python 3.12, deploy prueba 3.13 y runtime no está fijado. Un valor desconocido
de `DJANGO_ENV` cae a `dev`; el secret key base tiene fallback inseguro.

Acción: alinear versión, fallar cerrado en entorno desconocido y exigir secretos
productivos antes de construir la aplicación.

### CI y deploy acoplados

Estado: parcialmente resuelta.

El patch de transición deja los pushes a `main` solo con pruebas y exige
`workflow_dispatch`, confirmación literal y environment `production` para
desplegar un tag/hash explícito. El clon remoto rechaza cambios locales y usa el
SHA probado en modo detached. Sigue pendiente configurar revisores obligatorios
en GitHub y reemplazar el healthcheck HTTP superficial por uno más profundo.

Acción: verificar la política real del environment y diseñar healthcheck profundo.

### Observabilidad y auditoría incompletas

Estado: activa.

No hay logs estructurados, alertas ni healthcheck de DB. `AuditLog` es parcial y
best-effort. `monitor` está instalado, archivado y con tests HTML omitidos.

Acción: definir mínimo de producción; auditar tablas de monitor antes de retirarlo.

## Baja

- Views extensas y separación desigual por capas.
- Sin coverage formal ni convención única de factories.
- Auditoría histórica SQLite muy larga; se conserva como evidencia, no como guía.
- API conserva ApiAccessKey/Token DRF sin consumidor de datos.
- Dependencias visuales CDN no están vendorizadas ni monitorizadas.

## Resuelta

- App legacy `database` retirada del runtime y grafo vigente.
- SQLite retirado de settings y del checkout local en este corte.
- Inventario de reglas regenerado desde el código actual.
- Transiciones ordinarias de asistencia recalculan idempotentemente su consumo.
- Pago ya no se elimina desde UI: existe reversa histórica controlada.
- Accesos directos financieros por objeto se acotan mediante querysets de organización.

## Regla de cierre

Una deuda solo se marca resuelta cuando código, tests y documento dueño coinciden.
Una mitigación de UI no equivale a una garantía de base de datos o producción.

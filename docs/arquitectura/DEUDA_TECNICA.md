# Deuda técnica activa

Fecha de actualización: 2026-10-12

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

`data/` contiene cargas de alumnos que no deben asumirse fixtures sintéticas.

Acción segura: confirmar dueño/retención, retirar del HEAD si corresponde y decidir
si la exposición justifica limpiar historial. No copiar contenido a documentación.

## Media

### Dos subdominios dentro de Finanzas

Estado: activa controlada.

Cobranza y caja comparten app. Hay services/selectors (el paquete de documentos
fiscales se retiró por ADR 0015), pero las views aún coordinan casos de uso grandes.

Acción: extraer incrementalmente sin crear otra app hasta que existan ciclo de
vida, modelos y permisos realmente independientes.

### Reglas solo en aplicación

Estado: activa.

Compatibilidad de organización, contraparte exclusiva y plan por defecto dependen
en parte de forms/services. Escrituras futuras podrían omitirlos.

Acción: estabilizar reglas y datos antes de añadir constraints compatibles.

### Desalineación de Python y selección de entorno

Estado: activa, parcialmente resuelta.

PR y deploy prueban con Python 3.12, pero el runtime productivo no está fijado y
`pyproject.toml` declara `target-version = "py313"` para ruff. Un valor desconocido
de `DJANGO_ENV` cae a `dev`; el secret key base tiene fallback inseguro.

Acción: alinear versión, fallar cerrado en entorno desconocido y exigir secretos
productivos antes de construir la aplicación.

### CI y deploy acoplados

Estado: parcialmente resuelta.

Los pushes a `main` despliegan automáticamente cuando CI pasa. Desde `16cb3af`
el deploy aplica migraciones pendientes tras detener el servicio y respaldar con
`pg_dump`; solo las reparaciones históricas de asistencias quedan reservadas al
release escalonado. El clon remoto rechaza cambios locales y usa el SHA probado
en modo detached. `deploy.yml` no declara `environment:` y por tanto no exige
revisores. Sigue pendiente reemplazar el healthcheck HTTP superficial por uno más
profundo.

Acción: decidir si el deploy con migraciones requiere aprobación (environment
protegido) y diseñar healthcheck profundo.

### CI incompleto y desactualizado

Estado: activa.

Los workflows ejecutan `python manage.py test asistencias finanzas personas`,
no la suite completa: `api`, `auditoria` y `plataformaelemental` no corren en CI.
Además, `test.yml` invoca `asistencias.test_profesor_ux` y
`asistencias.test_operacion_profesor`, eliminados en `d792f75`, por lo que ese
paso falla.

Acción: retirar los módulos inexistentes y usar `python manage.py test` en ambos
workflows (ajustando `scripts/validar_gate_ci.py` si lo exige).

### Observabilidad y auditoría incompletas

Estado: activa.

No hay logs estructurados, alertas ni healthcheck de DB. `AuditLog` es parcial y
best-effort.

Acción: definir mínimo de producción.

## Baja

- Views extensas y separación desigual por capas.
- Sin coverage formal ni convención única de factories.
- Auditoría histórica SQLite muy larga; se conserva como evidencia, no como guía.
- API conserva ApiAccessKey/Token DRF sin consumidor de datos.
- Residuos del portal retirado: `asistencias/services/profesor.py` conserva
  siete servicios sin consumidores en código ni tests (`crear_sesion_profesor`,
  `liberar_sesion_profesor`, `cambiar_estado_sesion_profesor`,
  `crear_alumno_profesor`, `quitar_asistente_profesor`, `liberar_clase_profesor`,
  `revertir_clase_liberada_profesor`), junto a las activaciones administrativas
  que sí se usan; `scripts/e2e/profesor_*.js` quedan como archivo histórico.
- Constantes de acción sin consumidor en el árbol de trabajo:
  `ver_sesion` y `editar_asistencias` (`personas/permissions.py`).
- Tablas `monitor_*` pendientes de retiro en ambientes distintos de desarrollo;
  `migrate monitor zero` ya no es ejecutable desde `HEAD`.
- Dependencias visuales CDN no están vendorizadas ni monitorizadas.

## Resuelta

- App legacy `database` retirada del runtime y grafo vigente.
- App `monitor` (archivada, sin rutas activas) retirada del runtime, del codigo y de `INSTALLED_APPS`.
- SQLite retirado de settings y del checkout local en este corte.
- Inventario de reglas regenerado desde el código actual.
- Transiciones ordinarias de asistencia recalculan idempotentemente su consumo.
- Pago ya no se elimina desde UI: existe reversa histórica controlada.
- Accesos directos financieros por objeto se acotan mediante querysets de organización.

## Regla de cierre

Una deuda solo se marca resuelta cuando código, tests y documento dueño coinciden.
Una mitigación de UI no equivale a una garantía de base de datos o producción.

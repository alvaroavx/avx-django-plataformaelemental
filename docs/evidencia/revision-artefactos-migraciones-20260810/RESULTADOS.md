# Evidencia — artefactos y migraciones

Fecha: 2026-08-10

## Convención de artefactos

- `node --check scripts/e2e/profesor_operacion.js`: aprobado.
- `ruff check scripts/validate_markdown_links.py`: aprobado.
- `npm run test:docs-links`: 68 enlaces locales válidos.
- `git diff --check`: aprobado.

Los recorridos Puppeteer ad hoc de Operación Profesor fueron generalizados en
`scripts/e2e/profesor_operacion.js`. Las credenciales locales que existían en las
copias temporales no se incorporaron al repositorio; el runner exige variables
de entorno y es de solo lectura salvo habilitación explícita de mutaciones.

## Migraciones de Operación Profesor

Se inspeccionaron las operaciones y el SQL generado por Django con:

```bash
python manage.py sqlmigrate asistencias 0004
python manage.py sqlmigrate finanzas 0012
```

SQL conservado:

- [asistencias 0004](asistencias-0004.sql)
- [finanzas 0012](finanzas-0012.sql)

Conclusiones verificadas:

- No existen borrados, remoción de campos ni actualización destructiva de filas.
- El cambio de opciones de `SesionClase.estado` es un `no-op` SQL.
- `asistencias.0004` crea tres tablas y ejecuta un backfill Python desde sesiones
  y asistencias históricas. Crea como activas todas las relaciones derivadas.
- `finanzas.0012` agrega columnas anulables; los valores históricos quedan en
  `NULL` y no se crean transacciones retroactivas.
- Los índices únicos, claves foráneas e índices normales se crean con operaciones
  no concurrentes. Su bloqueo debe medirse según el volumen productivo.
- El SQL no representa el contenido de `RunPython`; para ese comportamiento la
  fuente de verdad es la migración `asistencias.0004`.

Esta inspección usó PostgreSQL local de desarrollo únicamente para construir el
plan SQL. No consultó ni modificó producción.

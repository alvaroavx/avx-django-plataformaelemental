# Testing

Fecha de actualizacion: 2026-05-11

## Proposito
Este documento define la estrategia de pruebas vigente.

La meta no es tener tests por cantidad. La meta es proteger reglas criticas del negocio y evitar regresiones en flujos operativos.

## Comando Principal
El set principal esperado es:

```bash
python manage.py test asistencias.tests personas.tests finanzas.tests api.tests
```

Este comando es el que usa CI.

## Checks Base
Para cambios generales:

```bash
python manage.py check
```

Para cambios de migraciones:

```bash
python manage.py makemigrations --check --dry-run
```

Para produccion:

```bash
python manage.py check --deploy
```

## Estrategia Por Tipo De Cambio

### Modelos y migraciones
Debe cubrir:
- tabla creada o modificada,
- unicidades,
- relaciones `ForeignKey`, `OneToOneField` y `ManyToManyField`,
- comportamiento `CASCADE`, `PROTECT` o `SET_NULL`,
- migracion limpia en PostgreSQL.

Tests recomendados:
- modelo guarda datos validos,
- constraint relevante falla cuando corresponde,
- relacion critica consulta correctamente.

### Cobranza operacional
Debe cubrir:
- asistencia presente sin pago disponible,
- asistencia presente con pago disponible,
- pago posterior imputando deuda del mismo periodo,
- pago de otro mes no consumiendo asistencia fuera de periodo,
- resumen financiero de estudiante.

Regla:
- Si cambia deuda, saldo, pagos, consumos o imputacion, debe existir test de regla.

### Finanzas / contabilidad
Debe cubrir:
- montos neto, IVA, exento, retencion y total,
- asociacion opcional con documentos tributarios,
- exportaciones CSV con headers estables,
- reportes sobre el mismo universo filtrado que la vista.

Regla:
- No basta con testear que renderiza la vista; se debe testear la regla o selector/service que calcula.

### Documentos tributarios
Debe cubrir:
- deteccion de duplicados operativos,
- parseo de XML/PDF soportado,
- normalizacion de montos CLP,
- sugerencia de contraparte por RUT,
- error legible ante conflictos de unicidad.

Regla:
- Los PDFs/XML de ejemplo deben mantenerse como fixtures o archivos de prueba controlados cuando sean necesarios.

### Asistencias
Debe cubrir:
- filtros por periodo y organizacion,
- disciplinas/profesores activos,
- estados de sesion,
- registro de asistencia,
- impacto financiero cuando una asistencia presente genera consumo/deuda.

### Personas y roles
Debe cubrir:
- RUT chileno opcional y validado,
- asignacion unica de rol por persona/organizacion,
- filtros por persona activa/inactiva y rol activo/inactivo,
- perfiles consolidados sin duplicar reglas financieras.

### API
Debe cubrir:
- autenticacion por usuario,
- API key de solo lectura,
- rechazo de escritura con API key,
- throttling cuando aplique,
- filtros base `organizacion`, `periodo_mes`, `periodo_anio`.

### UI y templates
Debe cubrir al menos:
- existencia de botones/enlaces criticos,
- querystring correcto para modales o navegacion,
- no reabrir modales por querystring residual,
- filtros globales preservados.

No conviene testear:
- clases CSS decorativas salvo que representen estado funcional,
- layout exacto de Bootstrap,
- detalles visuales que cambian con frecuencia.

## CI Actual
El workflow ejecuta:
- `ruff check .`
- `python manage.py test asistencias.tests personas.tests finanzas.tests api.tests`

La base de datos de CI usa PostgreSQL mediante service container.

Detalle operativo:
- [docs/operacion/DEPLOY.md](../operacion/DEPLOY.md)

## Cuando No Ejecutar Tests
Cambios solo documentales no requieren tests de Django.

En ese caso se debe:
- revisar enlaces,
- revisar rutas locales accidentales,
- si se modifican diagramas Mermaid, revisar render en GitHub o validar con `mmdc` cuando este disponible,
- mantener fechas de actualizacion,
- verificar que el documento duenio sea el correcto.

## Deuda De Testing
- Falta separar tests por capas de forma mas clara: selectors, services, views y API.
- Falta una convencion de fixtures/factories compartidas.
- Falta documentar datos de prueba para documentos tributarios complejos.
- Falta coverage formal; por ahora se prioriza proteger reglas criticas.

# Testing

Fecha de actualizacion: 2026-08-16

## Proposito
Este documento define la estrategia de pruebas vigente.

La meta no es tener tests por cantidad. La meta es proteger reglas criticas del negocio y evitar regresiones en flujos operativos.

## Base de desarrollo autorizada

La base configurada en este checkout es de desarrollo y está separada de
producción. Para este entorno se instruyó usarla directamente y no crear bases,
clústeres ni bases `test_*` temporales hasta nueva autorización. Los recorridos
locales deben ser de lectura salvo que una tarea autorice expresamente escrituras
sobre esos datos.

Esta autorización no convierte resultados locales en evidencia productiva ni
permite apuntar comandos a producción. Antes de una operación destructiva debe
comprobarse que la configuración activa siga siendo `dev` y que el destino sea
la base de desarrollo esperada.

## Comando Principal
El set principal esperado es:

```bash
python manage.py test
```

Este comando descubre la suite completa y es el que usan los workflows de test y deploy. Los comandos por app se reservan para validaciones focalizadas.

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

Para diagramas Mermaid en documentacion:

```bash
npm run test:mermaid
```

Para enlaces locales de documentación:

```bash
npm run test:docs-links
```

Para reutilizar el recorrido móvil parametrizado de Operación Profesor:

```bash
export ELEMENTAL_E2E_USERNAME='usuario-sintetico'
export ELEMENTAL_E2E_PASSWORD='clave-no-versionada'
npm run test:e2e:profesor
```

La convención, variables y evidencia se mantienen en
[docs/proceso/ARTEFACTOS.md](ARTEFACTOS.md). El runner es de solo lectura salvo
que se habilite explícitamente `ELEMENTAL_E2E_MUTACIONES=1` sobre desarrollo o
QA con datos sintéticos.

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
- `python manage.py test`

La base de datos de CI usa PostgreSQL mediante service container.

Inventario al 2026-08-10: 410 métodos `test_*`. Este número orienta el tamaño,
pero el resultado válido es el del runner; 15 métodos pertenecen a `monitor` y
sus clases de vistas están explícitamente omitidas porque la app está archivada.

Validación local de este corte: `python manage.py test` pasó 404 tests, con 12
omitidos, en 517,437 segundos contra PostgreSQL local de desarrollo. Este
resultado valida el código local, pero no reemplaza CI PostgreSQL 16 ni confirma
la base o runtime productivos. El log sanitizado se conserva en
`docs/evidencia/profesor-20260809/logs/suite-completa-ok.log`.

Después de ese corte se agregaron dos casos para `poblar_mes_pruebas`; ambos
pasaron contra PostgreSQL local en 1,048 segundos. Verifican preview sin escritura,
14 sesiones, 25 asistencias/consumos, idempotencia y bloqueo con `DEBUG=False`.

También se agregó una regresión para el buscador y la selección mutuamente
excluyente al aprobar solicitudes. La clase completa de resolución pasó 6 casos
contra PostgreSQL local en 6,099 segundos.

El corte de búsqueda transversal agregó tres casos y amplió uno existente para
personas, asistentes, alumnos de pago masivo y pagos. Pasaron 100 pruebas
focalizadas más los 6 casos de resolución contra PostgreSQL 18.4 local; la suite
completa de 410 métodos queda pendiente de una futura ejecución integral.

El workflow `test.yml` usa Python 3.12; el job de test previo a deploy usa
Python 3.13. Esta diferencia es riesgo operativo hasta alinear o demostrar ambas
versiones junto al runtime productivo.

Detalle operativo:
- [docs/operacion/DEPLOY.md](../operacion/DEPLOY.md)

## Cuando No Ejecutar Tests
Cambios solo documentales no requieren tests de Django.

En ese caso se debe:
- revisar enlaces,
- revisar rutas locales accidentales,
- si se modifican diagramas Mermaid, ejecutar `npm run test:mermaid` o revisar render en GitHub si `mmdc` no esta disponible,
- mantener fechas de actualizacion,
- verificar que el documento duenio sea el correcto.

## Deuda De Testing
- Falta separar tests por capas de forma mas clara: selectors, services, views y API.
- Falta una convencion de fixtures/factories compartidas.
- Falta documentar datos de prueba para documentos tributarios complejos.
- Falta coverage formal; por ahora se prioriza proteger reglas criticas.

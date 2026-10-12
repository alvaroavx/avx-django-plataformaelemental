# Testing

Fecha de actualizacion: 2026-10-12

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

Este comando descubre la suite completa. **Los workflows no lo usan**: `test.yml`
y `deploy.yml` ejecutan `python manage.py test asistencias finanzas personas`, por
lo que `api`, `auditoria` y `plataformaelemental` no corren en CI. Los comandos
por app se reservan para validaciones focalizadas.

Django crea o reutiliza la base `test_<POSTGRES_DB>`. Si el rol PostgreSQL no
puede crearla en cada corrida, usar `python manage.py test --keepdb --noinput`
sobre una base de pruebas ya existente. No ejecutar dos corridas `--keepdb`
simultáneas sobre la misma base de pruebas.

## Checks Base
Para cambios generales:

```bash
python manage.py check
```

Para cambios de migraciones:

```bash
python manage.py makemigrations --check --dry-run
```

CI ejecuta este mismo comando antes de cualquier deploy. Un archivo de migración
en el push no impide el despliegue: `scripts/deploy.sh` respalda con `pg_dump` y
aplica `migrate` en el servidor, salvo las reparaciones históricas de
`asistencias` (0004b–0007), que abortan el deploy y van por el release escalonado.

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

Los E2E del portal dedicado de profesores están retirados junto con esa
interfaz. Sus resultados se conservan como evidencia histórica, no como prueba
de aceptación de la aplicación actual. La lista de artefactos históricos está
en [docs/proceso/ARTEFACTOS.md](ARTEFACTOS.md).

## Ronda funcional Profesor 2026-08-16

Se ejecutó el runner reutilizable sobre la base de desarrollo configurada, sin
crear una base de test adicional, con dos usuarios Profesor y dos organizaciones.
Pasaron navegación móvil, aislamiento, alta de asistentes, cambio persistente de
asistencia, alta/matrícula de alumno, pago individual con transacción, creación y
liberación de sesión completa y cambio de estado de sesión.

Esa ronda, anterior al refresh visual, encontró capacidades ausentes para
Profesor puro. El refresh habilita quitar asistentes y liberar/revertir una
clase individual mediante servicios auditados. Crear una persona sigue siendo
responsabilidad de Alumnos y ahora la sesión enlaza ese flujo con retorno. La
corrección de pagos permanece restringida porque el modelo no relaciona un
contramovimiento contable con la transacción original. La evidencia histórica y
los conteos de aquella ronda se conservan en
[profesor-flujo-20260816](../evidencia/profesor-flujo-20260816/RESULTADOS.md).

No se ejecutó `manage.py test` en esta ronda porque Django crea o reutiliza una
base de pruebas separada y la instrucción era trabajar exclusivamente sobre la
base de desarrollo actual. Los checks estáticos y de configuración sí forman
parte del cierre. Este recorrido funcional no reemplaza la suite automatizada.

Durante el desarrollo del refresh, antes de la instrucción final de no crear
bases, se ejecutaron 18 pruebas focalizadas de Operación Profesor y
multi-organización con resultado verde. También se ejecutaron 50 pruebas de los
dominios y jornada: 49 pasaron y una detectó un fixture de transferencia sin
comprobante; el caso corregido se reejecutó y pasó. Después de la restricción no
se recreó la base de test, por lo que la suite integral de Asistencias, Finanzas
y Personas queda pendiente y no se declara validación completa.

El 2026-08-17 se completó el login Google real local con una cuenta Profesor y
se ejecutó el recorrido sanitizado a 390×844 en claro, oscuro, contexto agregado
y una segunda organización autorizada sin asignación docente. El recorrido fue
de solo lectura: no creó bases ni modificó datos funcionales. La segunda
organización respondió `200` en listados vacíos, ocultó acciones y respondió
`403` en formularios mutantes directos. La evidencia está en
[profesor-refresh-20260816](../evidencia/profesor-refresh-20260816/RESULTADOS.md).

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
- exportaciones CSV con headers estables,
- reportes sobre el mismo universo filtrado que la vista.

Regla:
- No basta con testear que renderiza la vista; se debe testear la regla o selector/service que calcula.

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
- filtros base `organizacion`, `periodo_mes`, `periodo_anio` cuando existan endpoints de datos (hoy no existen).

### Contrato Cuadratura
Debe cubrir cualquier cambio en `finanzas/services/cuadratura_v1.py`:
- operaciones incluidas y motivos de `pending_records`,
- montos CLP enteros y clasificación `EXEMPT`/`TAXABLE`,
- estabilidad de `batch_id`,
- permisos y aislamiento por organización de `preparar_mes`/`descargar_cuadratura`.

Hoy solo existen dos tests (`finanzas/tests.py`): exportación de un pago válido
sin mutar registros y pendiente por pago sin transacción.

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
Ambos workflows (`test.yml` en pull requests y `deploy.yml` en push a `main`) ejecutan:
- `python scripts/validar_gate_ci.py`
- `python manage.py check`
- `python manage.py makemigrations --check --dry-run`
- `ruff check .`
- `python manage.py test asistencias finanzas personas`

`test.yml` además ejecuta `asistencias.test_profesor_ux` y
`asistencias.test_operacion_profesor`, módulos eliminados en `d792f75`; ese paso
falla hasta corregir el workflow (pendiente en `docs/arquitectura/DEUDA_TECNICA.md`).

La base de datos de CI usa PostgreSQL mediante service container.

Inventario al 2026-10-12: 394 métodos `test_*` en `HEAD` y 400 en el árbol de
trabajo con cambios en curso. La app `monitor` y sus 15 métodos se retiraron en
`a64dbc2`; los tests del portal de profesores, en `d792f75`. Este número orienta
el tamaño, pero el resultado válido es el del runner.

Histórico (corte 2026-08-10, 410 métodos incluyendo `monitor`):

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

Los workflows `test.yml` y `deploy.yml` usan Python 3.12. El runtime productivo
no está fijado desde el repositorio.

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
- Falta coverage formal; por ahora se prioriza proteger reglas criticas.

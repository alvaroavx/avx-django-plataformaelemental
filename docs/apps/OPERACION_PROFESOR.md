# Operación Profesor

Fecha de actualización: 2026-08-17

## Estado implementado

El espacio `/profesor/` es una superficie HTML server-rendered y mobile-first
para usuarios con `User`, `Persona.activo=True` y `PersonaRol` activo con código
normalizado `PROFESOR`. La autenticación sigue siendo la existente; este sprint
no modifica Google ni agrega proveedores.

La autorización no depende de botones ni del menú. Cada vista vuelve a resolver:

1. usuario y persona activos;
2. rol `PROFESOR` activo;
3. organización solicitada explícitamente mediante `?organizacion=<id>` o la
   vista agregada `?organizacion=todos`, siempre limitada a sus
   `PersonaRol(PROFESOR, activo=True)`;
4. `AsignacionProfesorDisciplina` operativa: activa y explícita, o histórica revisada;
5. `SesionClase.profesores` para una sesión concreta;
6. `AlumnoDisciplina` operativa para alumnos, asistentes y pagos;
7. organización y disciplina del pago o lote.

Un identificador de sesión, pago, alumno o lote fuera del alcance no se entrega
al profesor. Las superficies globales de Personas, Finanzas y Django Admin no
forman parte del espacio profesor.

## Contexto multi-organización

`PersonaRol` es la única fuente de verdad del selector. La portada
`GET /profesor/` sin organización no muestra datos operativos: presenta las
organizaciones donde la persona mantiene un rol `PROFESOR` activo. Elegir una
genera un request explícito con `?organizacion=<id>`; no existe selección por
orden, sesión, primera coincidencia ni fallback silencioso. La alternativa
`organizacion=todos` agrega solo esas organizaciones y es de lectura: no admite
sesiones, asistencia, alumnos ni pagos mutables.

Todas las demás vistas del espacio Profesor exigen ese parámetro. Un ID
inexistente, ajeno, inactivo o asociado a otro rol responde `404`. Esto también
aplica a detalle de sesión y endpoints de búsqueda, alta y corrección de
asistencia. La selección viaja en la barra inferior, acciones, formularios,
AJAX, navegación anterior/siguiente y filtros de período. El período usa uno de
dos contratos excluyentes: `periodo_mes=<1..12>&periodo_anio=<YYYY>` o
`periodo=todos`. Combinarlos, enviar solo mes/año o usar valores fuera de rango
responde `404`. `periodo=todos` es un historial de lectura paginado a 25 filas.
Al aplicar un cambio desde la hoja de contexto se vuelve a Inicio, evitando
arrastrar identificadores de recursos de la selección anterior.

Seleccionar una organización no basta para operar: cada lectura y escritura
vuelve a contrastar la organización real del recurso, la asignación operativa
profesor–disciplina, `SesionClase.profesores` y la matrícula vigente. `is_staff`
no amplía este alcance; el comportamiento global explícito de superusuario no
cambia.

Una organización con rol Profesor activo pero sin asignación docente sigue
visible en el selector y puede abrirse para consultar su estado vacío. No expone
acciones mutantes; las URLs directas de creación o pago responden `403`. Nunca
toma disciplinas ni datos de otra organización como fallback.

## Modelo operativo

- `AsignacionProfesorDisciplina`: alcance explícito profesor–disciplina. Es la
  autorización para crear sesiones y operar el roster de esa clase.
- `AlumnoDisciplina`: matrícula operativa alumno–disciplina. Limita búsqueda,
  asistencia y cobro.
- `SesionClase.profesores`: asignación concreta de cada sesión.
- `LiberacionSesion`: cancelación auditable de una sesión, con motivo y actor.
- `Payment.disciplina`: clase/servicio al que se imputa el pago.
- `Payment.transaccion`: vínculo uno-a-uno con el movimiento contable.

La migración `asistencias.0004` no elimina datos: deriva asignaciones de profesor
desde sesiones históricas y matrículas desde asistencias existentes. Toda
relación inferida nace `historica`, inactiva y sin revisión, por lo que no
concede acceso. Una administración debe confirmar cada relación vigente; la
activación guarda actor, fecha y auditoría. Los pagos históricos no reciben una
transacción inventada, porque hacerlo alteraría retroactivamente el libro de caja.

## Rutas

| Ruta | Uso | Restricción principal |
| --- | --- | --- |
| `GET /profesor/` | Selector sin contexto o tablero con `?organizacion=<id>` | Rol profesor activo en la organización solicitada |
| `GET /profesor/sesiones/` | Hoy, futuras e históricas | Solo disciplinas y sesiones asignadas |
| `GET/POST /profesor/sesiones/crear/` | Crear sesión propia futura | Asignación profesor–disciplina |
| `POST /profesor/sesiones/<id>/estado/` | Abrir/cerrar sesión | Sesión propia |
| `POST /profesor/sesiones/<id>/liberar/` | Cancelar con motivo | Sesión propia; auditoría obligatoria |
| `GET /profesor/alumnos/` | Roster acotado | Matrículas de clases asignadas |
| `GET/POST /profesor/alumnos/crear/` | Crear y matricular alumno | Teléfono o email válido |
| `GET /profesor/pagos/` | Resumen, pagos y glosas | Pagos de disciplinas asignadas |
| `GET/POST /profesor/pagos/crear/` | Pago individual | Alumno matriculado en clase propia |
| `GET /profesor/pagos/<id>/` | Detalle de un pago | Organización y disciplina asignada |
| `GET/POST /profesor/pagos/masivo/nuevo/` | Preview y lote 10–20 | Alumnos matriculados; atomicidad |
| `GET /profesor/pagos/masivo/alumnos/` | Búsqueda incremental | Disciplina asignada |
| `GET /profesor/pagos/masivo/<uuid>/` | Resultado verificado | Lote del mismo alcance |

El detalle y endpoints JSON de sesión permanecen bajo
`/asistencias/sesiones/<id>/`; reutilizan autorización efectiva de servidor y
ahora limitan a una profesora a alumnos matriculados en la disciplina.

## Estados y auditoría

Los estados visibles de sesión son:

- `programada`: Planificada;
- `abierta`: Abierta;
- `completada`: Cerrada;
- `cancelada`: Cancelada.

Agregar el primer asistente desde el espacio profesor abre la sesión; no la
cierra silenciosamente. El profesor puede abrir o cerrar de forma explícita.
Correcciones de asistencia delegan en `cambiar_estado_asistencia` y generan
auditoría. Un profesor asignado puede quitar a un asistente; la operación
bloquea la fila, registra sesión, alumno, consumo y pago vinculados en auditoría,
y luego elimina la asistencia dentro de la misma transacción. También puede
liberar o revertir la liberación de una clase individual con las operaciones de
dominio existentes: motivo obligatorio, actor, `ClaseLiberada` y recálculo del
consumo. Crear sesión/alumno, liberar sesión, pagos, transacciones y lotes
también dejan actor y evento.

## Integridad de pagos

`crear_pago_operacional` ejecuta en `transaction.atomic`:

1. valida/consulta la clave de idempotencia;
2. guarda `Payment` con actor, disciplina y eventual lote;
3. crea una `Transaction` de ingreso por el mismo total;
4. enlaza `Payment.transaccion` uno-a-uno;
5. registra auditoría de pago y transacción después del commit.

El lote conserva clave única global, respaldo común, actor, metadatos y claves
determinísticas por ítem. Una fila inválida bloquea confirmación. Un error durante
persistencia revierte lote, pagos y transacciones. La pantalla de resultado solo
muestra éxito cuando recuenta pagos y transacciones enlazadas y únicas.

Los pagos históricos con `transaccion=NULL` se muestran como tales. No se
backfillean automáticamente. Profesor no edita, elimina ni revierte pagos: el
servicio de reversa existente marca `Payment`, pero no crea ni relaciona un
contramovimiento para `Transaction`, que es la fuente del libro de caja. Sin una
trazabilidad contable inequívoca, exponer esa acción dejaría los dos dominios
divergentes.

## UI móvil vigente

- Barra inferior: Inicio, Mis clases, Alumnos y Pagos.
- Cabecera compacta que abre una hoja inferior de contexto: organización,
  período y tema Claro/Oscuro persistido solo en `localStorage`.
- Próxima sesión y acciones frecuentes antes que resúmenes.
- Listas con divisores en lugar de una tarjeta por registro; menú `…` para
  quitar asistente y liberar/revertir clase individual.
- Botones frecuentes y navegación inferior superan 44 px en la medición móvil.
- Selector masivo incremental mantiene foco, usa `Enter`, chips y evita duplicados.
- Formularios deshabilitan el envío mientras guardan cuando corresponde.

Contraste medido en componentes principales:

| Par | Ratio |
| --- | ---: |
| Claro: texto `#15201F` / fondo `#F7F8F6` | 15,67:1 |
| Claro: sesiones `#005F84` / `#F7F8F6` | 6,64:1 |
| Claro: pagos `#006B70` / `#F7F8F6` | 5,91:1 |
| Claro: alumnos `#5A7028` / `#F7F8F6` | 5,21:1 |
| Claro: crítico `#B83F13` / `#F7F8F6` | 5,24:1 |
| Oscuro: texto `#F6F8F7` / fondo `#111918` | 16,74:1 |
| Oscuro: secundario `#B9C7C4` / fondo `#111918` | 10,23:1 |
| Oscuro: acentos / fondo `#111918` | 9,65:1 a 10,90:1 |

## Límites confirmados

- El login Google real se completó en desarrollo local con una cuenta Profesor
  y callback en el puerto local autorizado. Demuestra el flujo OAuth local y la
  entrada al perfil, pero no sustituye un smoke productivo.
- No se implementó edición de nombre, logo, favicon ni acento. El profesor solo
  ve nombre/logo existentes en cabecera.
- Los pagos históricos pueden carecer de transacción enlazada; corregirlos exige
  conciliación administrativa, no una migración que invente movimientos.
- La corrección de pagos Profesor queda bloqueada hasta modelar o demostrar un
  contramovimiento enlazado que corrija también el libro de caja. El detalle es
  de lectura y la URL de reversa Profesor no existe.
- El profesor crea y matricula una persona desde `/profesor/alumnos/crear/`.
  Desde una sesión, “Ir a Alumnos” lleva a ese flujo con la disciplina
  preseleccionada y luego vuelve al detalle conservando el contexto; no se
  duplica el formulario completo dentro de la sesión.
- `asistencias.0004` obtiene pares históricos únicos e inserta lotes de hasta
  2.000 relaciones inactivas en una transacción, sin cargar todo el historial en
  memoria de aplicación. Su duración y el conjunto que requiere revisión deben
  medirse sobre una copia de producción antes del deploy.
- `finanzas.0012` agrega columnas anulables sin reescribir valores históricos,
  pero crea índices únicos, índices de claves foráneas y `ALTER TABLE` no
  concurrentes. En tablas grandes puede bloquear escrituras durante el deploy.
- Revertir esas migraciones después de usar el espacio profesor eliminaría los
  datos que solo existan en las tablas y columnas nuevas.

El procedimiento, SQL, herramienta de medición y gate se mantienen en
[Migraciones de Operación Profesor](../operacion/MIGRACIONES_OPERACION_PROFESOR.md).
No existe QA/staging. El piloto se ejecutará manualmente en producción bajo
mantenimiento: la prueba sintética no reemplaza la medición real, por lo que el
runbook exige backup, `lock_timeout`, criterios de aborto y registro de tiempos.

Evidencia local inicial:
[docs/evidencia/profesor-20260809/RESULTADOS.md](../evidencia/profesor-20260809/RESULTADOS.md).
Ronda anterior sobre la base de desarrollo actual, conservada como evidencia
histórica previa a este refresh:
[docs/evidencia/profesor-flujo-20260816/RESULTADOS.md](../evidencia/profesor-flujo-20260816/RESULTADOS.md).
Refresh visual, aislamiento multi-organización y login Google local:
[docs/evidencia/profesor-refresh-20260816/RESULTADOS.md](../evidencia/profesor-refresh-20260816/RESULTADOS.md).

El recorrido local de navegador comprobó además alta de alumno, persistencia de
asistencia justificada tras recarga, pago individual con transacción visible y
creación/liberación de una sesión futura. No reemplaza el smoke OAuth real con
cuenta solo `PROFESOR`, pendiente para la ventana productiva controlada.

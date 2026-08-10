# Operación Profesor

Fecha de actualización: 2026-08-10

## Estado implementado

El espacio `/profesor/` es una superficie HTML server-rendered y mobile-first
para usuarios con `User`, `Persona.activo=True` y `PersonaRol` activo con código
normalizado `PROFESOR`. La autenticación sigue siendo la existente; este sprint
no modifica Google ni agrega proveedores.

La autorización no depende de botones ni del menú. Cada vista vuelve a resolver:

1. usuario y persona activos;
2. rol `PROFESOR` activo;
3. organización del rol;
4. `AsignacionProfesorDisciplina` operativa: activa y explícita, o histórica revisada;
5. `SesionClase.profesores` para una sesión concreta;
6. `AlumnoDisciplina` operativa para alumnos, asistentes y pagos;
7. organización y disciplina del pago o lote.

Un identificador de sesión, pago, alumno o lote fuera del alcance no se entrega
al profesor. Las superficies globales de Personas, Finanzas y Django Admin no
forman parte del espacio profesor.

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
| `GET /profesor/` | Tablero operativo | Rol profesor activo |
| `GET /profesor/sesiones/` | Hoy, futuras e históricas | Solo disciplinas y sesiones asignadas |
| `GET/POST /profesor/sesiones/crear/` | Crear sesión propia futura | Asignación profesor–disciplina |
| `POST /profesor/sesiones/<id>/estado/` | Abrir/cerrar sesión | Sesión propia |
| `POST /profesor/sesiones/<id>/liberar/` | Cancelar con motivo | Sesión propia; auditoría obligatoria |
| `GET /profesor/alumnos/` | Roster acotado | Matrículas de clases asignadas |
| `GET/POST /profesor/alumnos/crear/` | Crear y matricular alumno | Teléfono o email válido |
| `GET /profesor/pagos/` | Resumen, pagos y glosas | Pagos de disciplinas asignadas |
| `GET/POST /profesor/pagos/crear/` | Pago individual | Alumno matriculado en clase propia |
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
auditoría. Crear sesión/alumno, liberar sesión, pagos, transacciones y lotes
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
backfillean automáticamente. Editar un pago nuevo sincroniza fecha, monto y glosa
de su transacción enlazada.

## UI móvil vigente

- Barra inferior: Inicio, Mis clases, Alumnos y Pagos.
- Cabecera de organización en modo lectura; no expone branding editable.
- Próxima sesión y acciones frecuentes antes que resúmenes.
- Territorios Aire, Tierra, Agua y Fuego con texto e iconos; no representan por
  sí solos estados.
- Botones frecuentes y navegación inferior superan 44 px en la medición móvil.
- Selector masivo incremental mantiene foco, usa `Enter`, chips y evita duplicados.
- Formularios deshabilitan el envío mientras guardan cuando corresponde.

Contraste medido en componentes principales:

| Par | Ratio |
| --- | ---: |
| Aire `#1479A6` / blanco | 4,87:1 |
| Tierra `#697B36` / blanco | 4,68:1 |
| Agua `#087D88` / blanco | 4,88:1 |
| Fuego de acción `#A83B1C` / blanco | 6,35:1 |
| Fondo `#F8F6F1` / texto `#17232B` | 14,82:1 |

## Límites confirmados

- La prueba automatizada de Google demuestra que identidad no concede permisos,
  pero el login real con cuenta Google de prueba en QA no se ejecutó en este
  checkout. Requiere credenciales y entorno externo.
- La evidencia Chrome local usa login local habilitado solo en el proceso de
  desarrollo; no demuestra OAuth ni producción.
- No se implementó edición de nombre, logo, favicon ni acento. El profesor solo
  ve nombre/logo existentes en cabecera.
- Los pagos históricos pueden carecer de transacción enlazada; corregirlos exige
  conciliación administrativa, no una migración que invente movimientos.
- Revertir un pago enlazado conserva actualmente la transacción original; la
  política contable de contramovimiento queda por definir antes de automatizarla.
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

Evidencia local: [docs/evidencia/profesor-20260809/RESULTADOS.md](../evidencia/profesor-20260809/RESULTADOS.md).

El recorrido local de navegador comprobó además alta de alumno, persistencia de
asistencia justificada tras recarga, pago individual con transacción visible y
creación/liberación de una sesión futura. No reemplaza el smoke OAuth real con
cuenta solo `PROFESOR`, pendiente para la ventana productiva controlada.

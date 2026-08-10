# Estado actual de Plataforma Elemental

Fecha de corte: 2026-08-10
Código base auditado: `origin/main` en `d4a4e48`; este corte incorpora el commit
local no publicado `94b5299` y el endurecimiento de migraciones posterior.

## Cómo leer este documento

Esta es la fotografía ejecutiva del sistema que existe. No es un roadmap ni una
descripción aspiracional.

Las afirmaciones se clasifican así:

- **Verificado en código:** existe en modelos, rutas, servicios, configuración o tests.
- **Validado localmente:** además fue comprobado con un comando en este levantamiento.
- **Declarado operativo:** el usuario informó que la plataforma está en producción, pero el estado del servidor no fue inspeccionado desde este checkout.
- **No confirmado:** requiere servidor, proveedor externo, datos productivos o navegador real.

Cuando otro documento contradiga esta fotografía, prevalecen el código y los
tests vigentes. El documento dueño de cada dominio conserva el detalle.

## Resumen ejecutivo

Plataforma Elemental es un monolito modular Django 5.2.9 con UI HTML renderizada
en servidor. Gestiona identidad y organizaciones, operación de clases, cobranza
por clases, documentación tributaria, movimientos contables básicos y auditoría
operativa. PostgreSQL es el único motor configurado en desarrollo y producción.

Superficies activas:

| Componente | Estado verificable | Responsabilidad real |
| --- | --- | --- |
| `personas` | Activo | Personas, organizaciones, roles, cuentas Google y solicitudes de acceso. |
| `asistencias` | Activo | Disciplinas, asignaciones, sesiones, asistencia, panel profesor y excepciones de cobro. |
| `finanzas` | Activo | Planes, pagos, lotes, consumos/deuda, documentos, categorías y transacciones. |
| `auditoria` | Activo | Registro best-effort de mutaciones sensibles. |
| `api` | Activo y mínimo | Salud, estado, versión y usuario autenticado; no hay CRUD de dominio. |
| `monitor` | Instalado pero archivado | Conserva modelos, migración y código; no tiene ruta raíz, navegación ni admin activo. |

La app legacy `database` ya no existe. `monitor` no es parte del producto visible,
pero todavía sí forma parte del runtime por estar en `INSTALLED_APPS`.

## Stack y ejecución

- Python local requerido por el repositorio: 3.12.
- Django 5.2.9; DRF 3.16.1; django-allauth 65.18.0.
- PostgreSQL mediante variables `POSTGRES_*` obligatorias en `dev` y `prod`.
- UI con Bootstrap, DataTables y Tom Select desde CDN.
- Gunicorn detrás de un proxy, gestionado por `systemd` según el ejemplo versionado.
- CI de pull requests: Python 3.12 y PostgreSQL 16.
- Workflow de deploy: prueba con Python 3.13 y PostgreSQL 16, luego despliega `main` por SSH.
- Dominio hardcodeado como público y healthcheck: `apps.espacioelementos.cl`.
- Zona horaria `America/Santiago`; idioma `es-cl`.

No confirmado desde el repositorio: versión real de Python/PostgreSQL en
producción, configuración Nginx, unit instalado, permisos de media, restauración
de backups, credenciales OAuth ni último workflow desplegado. El usuario declara
Google activo y operativo en producción; este checkout no inspeccionó ese runtime.

### Entorno de trabajo autorizado

- Este checkout y la base configurada localmente corresponden a desarrollo.
- Producción vive en otro entorno y sus datos no se comparten con esta base.
- Se autoriza usar directamente la base de desarrollo para pruebas funcionales,
  cargas masivas y validaciones; no es necesario crear una instancia paralela.
- Los resultados obtenidos aquí siguen siendo evidencia de desarrollo y no
  confirman datos, capacidad ni configuración productiva.

## Funcionalidad existente

### Personas y acceso

- Modelos `Organizacion`, `Persona`, `Rol`, `PersonaRol` y `SolicitudAcceso`.
- CRUD HTML de organizaciones y personas; roles activos por organización.
- Identidad mínima por RUT, email o teléfono; normalización en aplicación.
- Vínculo opcional uno-a-uno `Persona.user` con el `User` de Django.
- Login local, login Google controlado y acceso local de emergencia solo para superusuarios.
- Solicitudes Google pendientes, aprobadas o rechazadas; resolución atómica y auditada.
- Google autentica identidad; no concede roles ni organizaciones.
- Los flags separan OAuth, enforcement y solicitudes. Google fue declarado activo
  en producción, pero no se modificó ni se navegó el OAuth productivo en este corte.

### Operación de clases

- Modelos `Disciplina`, `BloqueHorario`, `AsignacionProfesorDisciplina`,
  `AlumnoDisciplina`, `SesionClase`, `Asistencia`, `LiberacionSesion` y `ClaseLiberada`.
- Panel, vista “Hoy”, calendario/listado, detalle y edición de sesiones.
- Creación individual y masiva de sesiones.
- Registro, corrección y eliminación de asistentes según permisos.
- Búsqueda y alta móvil mediante JSON interno acotado a la sesión.
- Estados planificada (`programada`), abierta, cerrada (`completada`) y cancelada
  para sesión; presente, ausente y justificada para asistencia.
- Una clase liberada conserva la asistencia y suspende cobro sin borrar historia.
- `/profesor/` entrega tablero móvil, sesiones propias, roster, asistencia,
  pagos acotados y glosa mensual sin abrir administración global.

### Cobranza operacional

- Modelos `PaymentPlan`, `Payment`, `LotePago` y `AttendanceConsumption`.
- Planes por organización, vigencia y plan por defecto.
- Pago individual o lote masivo con idempotencia y transacción de base de datos atómica.
- Todo pago nuevo confirmado mediante el servicio vigente crea exactamente una
  `Transaction` enlazada; el lote usa claves por lote e ítem y respaldo común.
- Cálculo de neto, IVA y total; organización exenta desactiva IVA.
- Imputación de clases y deuda restringida al mismo mes y año.
- Pagos revertidos conservan registro y recalculan consumos.
- Todos los estados académicos ordinarios consumen derecho o generan deuda; una clase liberada queda pendiente.

### Finanzas y documentos

- `DocumentoTributario` es snapshot fiscal y admite carga manual o asistida XML/PDF.
- Parser XML y fallback PDF con texto; no hay OCR.
- `Transaction` registra ingreso/egreso contable y puede asociar documentos.
- `Category` clasifica transacciones y hoy es global, no por organización.
- `Payment`, `Transaction` y `DocumentoTributario` son entidades distintas.
- Un pago nuevo genera una transacción uno-a-uno; pagos históricos anteriores a
  la migración pueden conservar `transaccion=NULL` y requieren conciliación real,
  no un backfill que invente movimientos.
- Hay reportes y exportaciones CSV/XLSX protegidos por permisos.

### API, auditoría y administración

- Públicos: `GET /api/health/`, `/api/status/` y `/api/version/`.
- Autenticado: `GET /api/me/`.
- `ApiAccessKey` y Token DRF existen por compatibilidad, sin endpoints de datos que los aprovechen.
- `AuditLog` registra mutaciones seleccionadas después del commit; un fallo del log no revierte el caso de negocio.
- No se auditan lecturas, exports, todos los automatismos ni cada cambio hecho por shell/admin.
- Django Admin es soporte; no reemplaza los casos de uso de la UI.

## Decisiones de desarrollo vigentes

1. Mantener el monolito modular y los modelos en su app dueña.
2. Mantener cobranza y contabilidad como subdominios distintos dentro de `finanzas`.
3. No abrir API de datos sin un consumidor y contrato de autorización concretos.
4. Mantener `Payment`, `Transaction` y `DocumentoTributario` separados.
5. Mantener filtros globales de periodo y organización en la navegación HTML.
6. Resolver reglas en services/selectors; las views coordinan HTTP.
7. Preservar datos productivos en migraciones y probar rollback/backup antes de cambios destructivos.
8. Mantener autenticación Google detrás de flags; identidad no equivale a autorización.
9. Mantener `monitor` archivado hasta auditar sus tablas productivas.
10. Usar PostgreSQL; SQLite ya no es alternativa soportada ni configuración de fallback.
11. Autorizar Operación Profesor mediante asignaciones explícitas de disciplina,
    sesión y alumno; el rol o la navegación por sí solos no conceden alcance.
12. Crear pago y movimiento contable enlazado en una sola operación atómica.
13. Tratar toda asignación o matrícula inferida desde historia como inactiva. Una
    relación histórica solo se vuelve operativa con activación administrativa,
    actor, fecha de revisión y auditoría.

## Validación de este corte

| Control | Resultado |
| --- | --- |
| `python manage.py check` con `.env.dev` | Pasa, 0 issues. |
| `makemigrations --check --dry-run` | Sin cambios; confirmado nuevamente contra el corte de búsqueda transversal. |
| `check --deploy` con configuración prod ficticia y sin secretos reales | Ejecuta; reporta `security.W005` y `security.W021` porque HSTS subdomains/preload son deliberadamente `False`. |
| `ruff check .` | Pasa. |
| `git diff --check` antes de editar | Pasa. |
| Inventario ejecutado de tests | 418 tests; incluye Operación Profesor, relaciones históricas, poblador mensual y regresiones de solicitudes y búsqueda transversal. |
| Suite completa PostgreSQL temporal | 418 tests OK, 12 omitidos, en 541,362 s sobre PostgreSQL 18.4. CI oficial sigue usando PostgreSQL 16. |
| Despliegue Operación Profesor | Listo para ventana manual, condicionado a preflight, backup, migraciones medidas, transición y smoke en producción. No existe QA/staging separado y producción no fue usada durante la preparación. |
| Tests focalizados del poblador mensual | 2 tests OK en 1,048 s: preview, escritura, señales financieras, idempotencia y gate `DEBUG=False`. |
| Resolución de solicitudes | 6 tests OK en 6,099 s; incluye búsqueda sin tildes, destino GET seguro y rechazo de User + Persona ambiguos. |
| Búsqueda transversal de personas | 100 tests focalizados OK más los 6 de resolución; cubre Personas, Asistencias, Operación Profesor y Finanzas. |
| Migraciones en PostgreSQL temporal | Desde cero pasan `asistencias.0004` corregida y `finanzas.0012`; 16 tests focalizados pasan. |
| Ensayo sintético `finanzas.0012` | PostgreSQL 18.4, 300.000 pagos y 100.000 transacciones: 2,335 s; espera máxima de escritura 967,264 ms; cero datos históricos inventados. |
| Backup/restauración sintética | `pg_dump` custom 0,86 s y `pg_restore` 4,39 s; conteos, sumas y 26 migraciones coinciden. |
| Gate producción de las migraciones | Listo para ejecución manual condicionada: preflight, backup, medición, transición y smoke se resuelven bajo mantenimiento en producción. |
| Navegador móvil local | Chrome 390×844: Inicio, Sesiones, Alumnos y Pagos 200; lote incremental de 10; gates globales 403/login Admin. |

Una suite local o CI aprobada no confirma el estado de los datos ni del servidor
productivo. El healthcheck público solo comprueba respuesta HTTP y no consulta
explícitamente PostgreSQL ni dependencias externas.

## Riesgos activos

### Acceso y aislamiento

- Asistencias desactiva el bypass operativo de `is_staff`; Personas y Finanzas
  todavía llaman helpers con `permitir_staff_global=True` en varias superficies.
  Un staff de Django puede saltarse roles organizacionales allí. Es comportamiento
  real, no una política ya cerrada.
- Sin organización seleccionada, algunos helpers aceptan un rol activo en cualquier
  organización. Cada vista debe seguir acotando objetos y formularios; no hay una
  única capa que lo garantice para futuras superficies.
- El Django Admin usa permisos Django, no la matriz completa de `PersonaRol`.
- Las acciones masivas están deshabilitadas en varios modelos sensibles, pero no
  en Rol, Disciplina, BloqueHorario, PaymentPlan, AttendanceConsumption,
  Category ni ApiAccessKey. `AuditLog` es visible a cualquier staff y no se
  filtra por organización.

### Integridad y datos productivos

- `Persona.user` usa `CASCADE`: eliminar un `User` elimina la `Persona` vinculada y
  puede arrastrar roles/asistencias; los pagos la protegen solo si existen.
- Eliminar organizaciones o entidades académicas activa cascadas amplias. Algunas
  protecciones (`Payment.persona`, `ClaseLiberada.organizacion`, `LotePago.organizacion`)
  detienen parte del borrado, pero no existe un protocolo único de baja productiva.
- Varias invariantes viven en forms/services y no como constraints PostgreSQL.
- `Category` es global; nombres y tipo se comparten entre organizaciones.
- No está verificada la consistencia de datos productivos ni la restauración real de un backup.

### Operación y despliegue

- Un push a `main` dispara deploy automático tras tests, sin environment protegido
  o aprobación manual visible en el workflow.
- El servidor ejecuta `git reset --hard origin/main`; cualquier cambio manual local se pierde.
- El job de PR usa Python 3.12 y el previo al deploy Python 3.13; producción no está fijada por el repo.
- Un `DJANGO_ENV` desconocido cae silenciosamente en `dev`.
- `DJANGO_SECRET_KEY` tiene fallback inseguro en settings base; `check --deploy`
  puede advertir sin que el script trate warnings como error.
- El runbook de Operación Profesor tiene restauración local comprobada y
  evidencia versionada, pero no existe prueba con copia representativa ni
  RPO/RTO productivos. Ese riesgo fue aceptado para un piloto pequeño; la
  medición real ocurre con mantenimiento y criterios de aborto.
- No hay logging estructurado, alertas ni monitor de salud de base de datos.
- Las migraciones de Operación Profesor no borran datos existentes.
  `asistencias.0004` ya crea relaciones históricas inactivas y exige revisión
  administrativa para volverlas operativas. `finanzas.0012` conserva el riesgo
  de locks por índices/FK y `ALTER TABLE` no concurrentes; el ensayo sintético no
  predice la duración real y el runbook usa `lock_timeout` para abortar sin espera
  indefinida.

### Código y mantenibilidad

- Las views principales siguen siendo grandes: Personas 1.047 líneas, Asistencias
  1.669 y Finanzas 1.563 en este corte.
- `monitor` permanece instalado con código, modelos y tests omitidos; aumenta el
  runtime y el costo de mantenimiento aunque no tenga URL activa.
- La auditoría es parcial y best-effort; no es una fuente completa para reconstruir historia.
- Dependencias visuales CDN introducen una dependencia externa no verificada para producción.
- No existe coverage formal ni separación uniforme de tests por capas.

### Higiene del repositorio

- El SQLite local ignorado y sus referencias comentadas eran residuos de la migración
  y se retiraron en este cambio. La auditoría larga de SQLite queda solo como evidencia histórica.
- `data/` contiene dos cargas de alumnos versionadas y `public/` cinco PDFs tributarios
  con nombres aparentemente reales. No hay referencias de runtime ni tests a esos archivos.
  Deben tratarse como posible información personal/tributaria, no como fixtures seguras.
- Esos archivos no se eliminaron automáticamente porque primero debe confirmarse si son
  evidencia necesaria. Quitarlos del HEAD tampoco los elimina del historial Git.
- `reporte.md` en raíz describe una rama de julio y se conserva solo con aviso histórico.
- `plataformaelemental/settings/base.py` es un placeholder legacy y
  `plataformaelemental/settings.py` un wrapper de compatibilidad; retirarlos requiere
  buscar consumidores externos antes de considerarlos basura.

## Cosas por resolver, en orden de riesgo

1. Cerrar y probar una sola política de `staff`, superusuario, rol y organización para Personas, Asistencias, Finanzas, archivos, exports y Admin.
2. Auditar datos productivos en modo lectura: identidades, roles, pagos, consumos, clases liberadas, documentos y tablas `monitor_*`.
3. Proteger operaciones de baja y corrección histórica; no ejecutar borrados ni recálculos globales sin preview, backup y rollback probado.
4. Confirmar runtime productivo: commit, Python, PostgreSQL, flags, Nginx/media, unit, secrets y último backup restaurable.
5. Revisar y retirar del HEAD los archivos reales de `data/` y `public/`; decidir si corresponde limpieza de historial.
6. Alinear Python 3.12/3.13 entre CI, deploy y runtime, y hacer fallar cerrado la selección de entorno/configuración productiva.
7. Repetir el ensayo de migraciones y la restauración sobre una copia protegida y
   reciente de producción; luego documentar RPO/RTO operativos reales.
8. Decidir si `monitor` se exporta/elimina o se mantiene con dueño y tests activos.
9. Conciliar pagos históricos sin transacción y definir el contramovimiento de
   reversas sin inventar ni duplicar caja.
10. Extraer casos de uso desde views de manera incremental, sin cambiar contratos HTML/JSON innecesariamente.

## Corte Operación Profesor 2026-08-09

Implementado y validado localmente:

- panel `/profesor/` mobile-first y navegación inferior;
- asignaciones explícitas profesor–disciplina y alumno–disciplina;
- sesiones propias planificadas, abiertas, cerradas o liberadas con auditoría;
- creación de alumno con teléfono o email y búsqueda incremental por matrícula;
- asistencia y corrección auditada con autorización de servidor;
- pagos individuales y lotes 10/15/20 con `Payment -> Transaction` uno-a-uno,
  claves de idempotencia y rollback completo probado;
- glosa mensual por disciplina efectivamente realizada;
- evidencia Chrome y matriz de acceso directo.

Pendiente de la ventana productiva para cerrar el criterio OAuth literalmente:
smoke real con una cuenta Google solo `PROFESOR` y registro del resultado. Google
fue declarado operativo en producción, pero no se usaron credenciales externas
durante la preparación. Detalle:
[docs/apps/OPERACION_PROFESOR.md](apps/OPERACION_PROFESOR.md).

## Lo que no debe afirmarse

- Que producción corre una versión concreta de Python o PostgreSQL sin consultarla.
- Que Google está operativo solo porque el código y las variables existen.
- Que toda la plataforma es multi-organización segura mientras persista el bypass de staff.
- Que un backup es recuperable sin haber ejecutado `pg_restore` en un entorno controlado.
- Que la API, el healthcheck o `monitor` ofrecen observabilidad productiva completa.
- Que los PDFs y archivos de carga versionados son ficticios o publicables sin revisión.

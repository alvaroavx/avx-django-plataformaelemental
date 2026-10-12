# Estado actual de Plataforma Elemental

## Revisión documental contra código — 2026-10-12

Auditoría de la documentación contra el árbol de trabajo (código como fuente de
verdad). Correcciones aplicadas a este documento:

- El job de test previo al deploy usa Python 3.12, no 3.13
  (`.github/workflows/deploy.yml`). PR y deploy están alineados en 3.12; el
  runtime productivo sigue sin fijarse desde el repo y `pyproject.toml` declara
  `target-version = "py313"` para ruff.
- El deploy rutinario **sí** aplica migraciones desde el commit `16cb3af`
  (2026-09-11): `scripts/deploy.sh` detiene el servicio, respalda con `pg_dump`
  y ejecuta `migrate`; solo aborta si quedan pendientes las reparaciones
  históricas `asistencias.0004b`–`0007`.
- `deploy.yml` no declara `environment:`; el deploy rutinario no pasa por
  revisores obligatorios de GitHub. Solo `release-asistencias-escalonado.yml`
  usa environments protegidos.
- Ambos workflows ejecutan `python manage.py test asistencias finanzas personas`,
  no la suite completa: `api`, `auditoria` y `plataformaelemental` no corren en CI.
- `.github/workflows/test.yml` (PR) todavía ejecuta
  `asistencias.test_profesor_ux` y `asistencias.test_operacion_profesor`,
  módulos eliminados en `d792f75`; ese paso falla hasta corregir el workflow.
- `finanzas.0013` ya figura aplicada en la base de desarrollo local
  (`showmigrations`, 2026-10-12). En producción sigue sin confirmarse.
- Trabajo en curso sin commitear (2026-10-12): `ConfiguracionPermisoRol`
  (`personas.0011`, aún no versionada), Configuración → Permisos
  (`/personas/permisos/`), calendario propio del Profesor y alta de asistentes en
  sus sesiones, según ADR 0018 y ADR 0019. Mientras no se integre, la afirmación
  “no hay interfaz sustituta” describe `HEAD`, no el árbol de trabajo.
- Validación en esta revisión: `manage.py check` y `makemigrations --check`
  pasan; `manage.py test --keepdb` (401 tests) terminó con 6 fallos, 21 errores
  y 15 omitidos, pero **no es concluyente**: el árbol de trabajo cambió durante
  la corrida y otra corrida `--keepdb` usaba la misma base de pruebas. Los fallos
  visibles son expectativas de tests anteriores a ADR 0019 (profesor asignado).

## Actualización de alcance — 2026-10-08

Se retiró la capacidad de comprobantes fiscales de Elemental. La migración
`finanzas.0013` elimina la tabla `finanzas_invoice`, la FK desde pagos y la
tabla intermedia M2M desde transacciones. También se retiraron cinco PDFs
versionados de `public/`. La migración está creada, pero no se ha aplicado aquí
ni en producción. El usuario confirmó que no hay información productiva de esa
capacidad; esta afirmación no se verificó consultando producción. Los objetos
eliminados y los PDFs continúan en el historial Git.

En el mismo corte (2026-10-08) se retiró el portal dedicado de profesores por
[ADR 0016](adr/0016-retira-portal-profesor-conserva-dominio.md). Se conserva el
rol/perfil `PROFESOR`, sus asignaciones a clases/sesiones y su uso en gestión
administrativa y reportes. No se eliminan modelos ni datos y no hay una interfaz
sustituta aún.

Fecha de corte: 2026-08-10
Código base auditado: `origin/main` en `d4a4e48`; la funcionalidad está cerrada
en `c47ce8225b3221b28a00baf9a4d2909e154c3b30` y el empaquetado operativo vive
en el segundo commit identificado por el tag
`release/operacion-profesor-20260810.1`. Nada fue publicado ni desplegado.

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
por clases, movimientos de caja básicos y auditoría
operativa. PostgreSQL es el único motor configurado en desarrollo y producción.

Superficies activas:

| Componente | Estado verificable | Responsabilidad real |
| --- | --- | --- |
| `personas` | Activo | Personas, organizaciones, roles, cuentas Google y solicitudes de acceso. |
| `asistencias` | Activo | Disciplinas, asignaciones, sesiones, asistencia, borrador de correo de cierre y excepciones de cobro. El panel profesor fue retirado (ADR 0016). |
| `finanzas` | Activo | Planes, pagos, lotes, consumos/deuda, categorías, transacciones y export mensual a Cuadratura. |
| `auditoria` | Activo | Registro best-effort de mutaciones sensibles. |
| `api` | Activo y mínimo | Salud, estado, versión y usuario autenticado; no hay CRUD de dominio. |

Las apps legacy `database` y `monitor` ya no existen: ninguna de las dos forma parte del código, las migraciones ni `INSTALLED_APPS`.

## Stack y ejecución

- Python local requerido por el repositorio: 3.12.
- Django 5.2.9; DRF 3.16.1; django-allauth 65.18.0.
- PostgreSQL mediante variables `POSTGRES_*` obligatorias en `dev` y `prod`.
- UI con Bootstrap, DataTables y Tom Select desde CDN.
- Gunicorn detrás de un proxy, gestionado por `systemd` según el ejemplo versionado.
- CI de pull requests: Python 3.12 y PostgreSQL 16.
- Workflow de deploy: prueba con Python 3.12 y PostgreSQL 16 (solo apps
  `asistencias finanzas personas`), luego despliega por SSH el SHA probado y
  aplica migraciones pendientes con respaldo previo.
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
- El portal dedicado `/profesor/` fue retirado el 2026-10-08. El rol y perfil,
  asignaciones a clases/sesiones y reportes administrativos correspondientes
  permanecen; no hay interfaz sustituta aún.

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

### Finanzas

- `Transaction` registra ingreso/egreso de caja.
- `Category` clasifica transacciones y hoy es global, no por organización.
- `Payment` y `Transaction` son entidades distintas y pueden enlazarse uno a uno.
- La documentación fiscal y la conciliación pertenecen a Cuadratura.
- `Preparar mes` (`/finanzas/preparar-mes/`) genera el contrato JSON
  `elemental-cuadratura-v1` por organización y mes, con pagos no elegibles en
  `pending_records`; la descarga es manual. No existe API ni envío automático.
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
4. Mantener `Payment` y `Transaction` separados, con documentación fiscal en Cuadratura.
5. Mantener filtros globales de periodo y organización en la navegación HTML.
6. Resolver reglas en services/selectors; las views coordinan HTTP.
7. Preservar datos productivos en migraciones y probar rollback/backup antes de cambios destructivos.
8. Mantener autenticación Google detrás de flags; identidad no equivale a autorización.
9. Usar PostgreSQL; SQLite ya no es alternativa soportada ni configuración de fallback.
10. Autorizar Operación Profesor mediante asignaciones explícitas de disciplina,
    sesión y alumno; el rol o la navegación por sí solos no conceden alcance.
11. Crear pago y movimiento contable enlazado en una sola operación atómica.
12. Tratar toda asignación o matrícula inferida desde historia como inactiva. Una
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

- Un push a `main` despliega automáticamente tras CI verde. Si hay migraciones
  pendientes, `scripts/deploy.sh` detiene el servicio, respalda con `pg_dump` y
  ejecuta `migrate`; si la migración falla, el servicio queda detenido y la
  recuperación es forward-only. Solo las reparaciones históricas de asistencias
  quedan reservadas al release escalonado.
- El checkout productivo se rechaza si está sucio y cambia en modo detached al
  SHA exacto probado; ya no se fuerza a `origin/main`.
- `deploy.yml` no usa `environment:`; ningún revisor obligatorio se interpone
  entre un push a `main` y producción. Los environments protegidos solo aplican
  al release escalonado de asistencias.
- PR y deploy prueban con Python 3.12; producción no está fijada por el repo.
- CI no ejecuta los tests de `api`, `auditoria` ni `plataformaelemental`, y el
  workflow de PR referencia dos módulos de test eliminados.
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

- Las views principales siguen siendo grandes: Personas 1.068 líneas, Asistencias
  1.764 y Finanzas 1.016 al 2026-10-12 (árbol de trabajo).
- La auditoría es parcial y best-effort; no es una fuente completa para reconstruir historia.
- Dependencias visuales CDN introducen una dependencia externa no verificada para producción.
- No existe coverage formal ni separación uniforme de tests por capas.

### Higiene del repositorio

- El SQLite local ignorado y sus referencias comentadas eran residuos de la migración
  y se retiraron en este cambio. La auditoría larga de SQLite queda solo como evidencia histórica.
- `data/` contiene dos cargas de alumnos versionadas que no son fixtures seguras.
- `reporte.md` en raíz describe una rama de julio y se conserva solo con aviso histórico.
- `plataformaelemental/settings.py` es un wrapper de compatibilidad sobre
  `plataformaelemental.config`; retirarlo requiere buscar consumidores externos
  antes de considerarlo basura. (`plataformaelemental/settings/base.py` ya no existe.)
- `finanzas/documentos/` solo conserva `__pycache__` ignorado del paquete fiscal retirado.

## Cosas por resolver, en orden de riesgo

1. Cerrar y probar una sola política de `staff`, superusuario, rol y organización para Personas, Asistencias, Finanzas, archivos, exports y Admin.
2. Auditar datos productivos en modo lectura: identidades, roles, pagos, consumos y clases liberadas.
3. Proteger operaciones de baja y corrección histórica; no ejecutar borrados ni recálculos globales sin preview, backup y rollback probado.
4. Confirmar runtime productivo: commit, Python, PostgreSQL, flags, Nginx/media, unit, secrets y último backup restaurable.
5. Revisar y retirar del HEAD los archivos reales de `data/` (los PDFs de `public/` ya se retiraron del HEAD el 2026-10-08); decidir si corresponde limpieza de historial.
6. Fijar el runtime productivo en Python 3.12 (CI y deploy ya usan 3.12; ruff apunta a py313), y hacer fallar cerrado la selección de entorno/configuración productiva.
7. Repetir el ensayo de migraciones y la restauración sobre una copia protegida y
   reciente de producción; luego documentar RPO/RTO operativos reales.
8. Retirar las tablas `monitor_*` (con respaldo previo) en cada ambiente que aún las tenga. Desde `a64dbc2` la app ya no está en `INSTALLED_APPS`, por lo que `migrate monitor zero` no se puede ejecutar desde el `HEAD` actual: requiere un checkout anterior a ese commit o un `DROP` manual revisado, más la limpieza de filas `monitor` en `django_migrations`.
11. Corregir CI: retirar de `test.yml` los módulos de test eliminados y ejecutar la suite completa (`python manage.py test`) en PR y deploy.
9. Conciliar pagos históricos sin transacción y definir el contramovimiento de
   reversas sin inventar ni duplicar caja.
10. Extraer casos de uso desde views de manera incremental, sin cambiar contratos HTML/JSON innecesariamente.

## Corte histórico Operación Profesor 2026-08-09 (retirado 2026-10-08)

Implementado y validado localmente en agosto de 2026; la interfaz descrita fue
retirada después por ADR 0016:

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
- Que la API o el healthcheck ofrecen observabilidad productiva completa.
- Que los archivos de carga versionados en `data/` (o los PDFs retirados que siguen en el historial Git) son ficticios o publicables sin revisión.
- Que el contrato `elemental-cuadratura-v1` acredita emisión fiscal o que Cuadratura ya lo consume automáticamente.

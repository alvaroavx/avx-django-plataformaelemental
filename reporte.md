# Reporte técnico de Plataforma Elemental

> Documento histórico del levantamiento del 2026-07-26. Describe una rama y un
> commit que ya no son el estado actual. La fotografía vigente se mantiene en
> `docs/ESTADO_ACTUAL.md`; no usar este archivo para decidir sobre el código de
> `main` sin volver a verificarlo.

Fecha de levantamiento: 2026-07-26
Base revisada: `HEAD` `8d52a7d`, rama `fase3-cierre-operativo`, alineada con `origin/fase3-cierre-operativo`.
Base de comparación: `origin/main` en `744243c`.

## 1. Propósito y criterio de evidencia

Este reporte describe qué está desarrollado actualmente y deja una agenda técnica para definir Elemental 2.0 con el arquitecto. No implementa cambios de producto ni propone una reescritura automática.

La fuente principal de verdad fue el código actual: modelos, migraciones, URLs, vistas, formularios, servicios, selectors, templates, tests, configuración y workflows. La documentación se contrastó contra el código y se señalan contradicciones cuando corresponde.

Se usa esta clasificación:

- **Verificado en código:** existe en los archivos actuales.
- **Verificado en esta sesión:** además de estar en código, el comando indicado se ejecutó ahora.
- **No confirmado:** requiere PostgreSQL operativo, navegador, Google, servidor productivo, datos reales o un entorno externo.
- **Decisión 2.0:** asunto que debe resolver producto/arquitectura antes de ampliar funcionalidades.

El árbol tenía un cambio previo no realizado durante este levantamiento: eliminación local de `reportePlataforma_20260719.md`. Se preservó y no forma parte de este reporte.

## 2. Resumen ejecutivo

Plataforma Elemental es un monolito Django modular para administrar organizaciones, personas, operación de clases, cobranza por clases, documentos tributarios y movimientos de caja. La interfaz principal es HTML server-side con Bootstrap; la API pública quedó deliberadamente reducida a salud, estado, versión y usuario autenticado.

La plataforma funcional vigente está compuesta por:

1. `personas`: identidad, organizaciones, roles por organización, CRM base y perfiles consolidados.
2. `asistencias`: disciplinas, sesiones, profesores, estudiantes, asistencia, calendario y operación diaria.
3. `finanzas`: planes, pagos operacionales, consumo/deuda de clases, documentos tributarios, categorías, transacciones y exportaciones.
4. `api`: superficie REST mínima, sin datos operacionales o financieros activos.
5. `auditoria`: trazabilidad mínima de mutaciones sensibles.
6. `monitor`: código histórico instalado, pero archivado y fuera de la navegación y rutas activas.

El trabajo central de esta rama es la Fase 3: habilitar técnicamente un camino seguro para autenticación Google y solicitudes de acceso, sin activar todavía la aprobación automática ni forzar Google en producción. La fase también reforzó el aislamiento por organización en el contexto global, en vistas de Personas/Asistencias y en objetos financieros, corrigió accesos directos de Finanzas y convirtió el workflow de pruebas en una suite completa sobre PostgreSQL 16.

El sistema ya tiene una base amplia para operar, pero Elemental 2.0 debería comenzar por estabilizar invariantes y permisos, no por agregar más módulos. Las decisiones más importantes son:

- contrato definitivo de aislamiento multi-organización;
- matriz de roles y permisos por acción y organización;
- ciclo de vida corregible de asistencia, consumo, pago y deuda;
- relación contable futura entre `Payment` y `Transaction`;
- estrategia de migraciones y validación PostgreSQL con datos reales;
- límite interno de crecimiento de `finanzas` y criterios para una futura separación.

## 3. Estado de la rama actual: `fase3-cierre-operativo`

### 3.1 Alcance exacto de la rama

Respecto de `origin/main`, la rama contiene dos commits adicionales:

- `d78d6b6 feat(personas): agrega acceso Google y solicitudes administrativas`.
- `8d52a7d chore: cierra validacion de fase 3`.

El diff de la rama frente a `origin/main` comprende 49 archivos, con 3.137 líneas agregadas y 127 eliminadas. La funcionalidad mobile-first de agregar asistentes (`b3b5bf9`) ya está integrada en `main`; es una base importante sobre la que trabaja la fase actual, pero no es una diferencia exclusiva de esta rama.

### 3.2 Autenticación Google

**Verificado en código:**

- Se incorporó `django-allauth` y el proveedor Google en `requirements.txt` y `plataformaelemental/config/base.py`.
- Google se inicia exclusivamente mediante `POST /accounts/google/iniciar/` con CSRF y vuelve por `/accounts/google/login/callback/`.
- No se incorporan las rutas generales de allauth.
- Se fuerza `process=login`, scopes `openid`, `email`, `profile`, `access_type=online` y PKCE.
- `SOCIALACCOUNT_AUTO_SIGNUP=False` y `SOCIALACCOUNT_STORE_TOKENS=False`.
- El adaptador elimina `extra_data` para no persistir respuestas OAuth completas ni tokens.
- Una identidad Google se resuelve primero por `provider + subject` (`sub`). El fallback por correo exige correo verificado, un único usuario activo y ausencia de conflicto.
- Google autentica la identidad, pero no asigna por sí solo organizaciones, roles ni permisos.
- La ruta local de emergencia `/accounts/emergencia/` queda oculta y solo acepta superusuarios.

Archivos principales: `personas/auth_google.py`, `personas/auth_views.py`, `personas/identidades_google.py`, `plataformaelemental/config/base.py` y `plataformaelemental/urls.py`.

**No confirmado:** no se validó aquí el intercambio real con Google, la configuración de OAuth en Google Cloud, el callback público, el dominio productivo ni la existencia de credenciales reales. El código puede estar preparado sin que el proveedor externo esté operativo.

### 3.3 Solicitudes de acceso

**Verificado en código:**

- `SolicitudAcceso` vive correctamente en `personas` y conserva estado `PENDIENTE`, `APROBADA` o `RECHAZADA`.
- La identidad desconocida puede generar una solicitud, pero no crea inmediatamente `User`, `Persona`, `PersonaRol` ni `SocialAccount`.
- La identidad pendiente se conserva en sesión de servidor durante 10 minutos; el navegador no puede enviar libremente correo, subject ni verificación para fabricar una solicitud.
- La creación es idempotente mientras exista una solicitud pendiente para la identidad/correo y tiene rate limit por identidad.
- La solicitud rechazada conserva historia y puede reabrirse solo con permiso y nota interna.
- La bandeja administrativa está en:
  - `/personas/solicitudes-acceso/`;
  - `/personas/solicitudes-acceso/<id>/`;
  - endpoints POST de aprobar, rechazar y reabrir.
- La administración requiere el permiso Django global `personas.gestionar_solicitudes_acceso`; no se concede solo por `staff` ni por `PersonaRol`.
- La aprobación permite resolver contra usuario existente, persona existente o crear usuario/persona nuevos, asignando organización y rol explícitos.
- La resolución es atómica, audita la decisión y falla cerrado ante conflicto de identidad Google o conflicto de correo.
- Se agregaron constraints parciales para impedir dos solicitudes pendientes de la misma identidad Google o correo normalizado.

Archivos principales: `personas/models.py`, `personas/solicitudes_acceso.py`, `personas/resolucion_solicitudes.py`, `personas/views.py`, `personas/forms.py` y templates de solicitudes.

### 3.4 Concurrencia y bloqueo de identidades

**Verificado en código:** el flujo usa `transaction.atomic()`, `select_for_update()` y locks transaccionales PostgreSQL por identidad Google y por usuario. Esto cubre el caso delicado en que todavía no existe una fila `SocialAccount` que pueda bloquearse.

La intención es impedir que dos solicitudes o callbacks concurrentes vinculen dos identidades Google incompatibles al mismo usuario o que un mismo `sub` termine asociado a usuarios distintos.

**No confirmado:** esta garantía depende de ejecutar sobre PostgreSQL y de que las pruebas de concurrencia corran realmente contra ese motor. El fallback fuera de PostgreSQL existe para documentación/pruebas, pero no ofrece el mismo nivel de serialización.

### 3.5 Endurecimiento del perímetro por organización

La rama incorpora:

- organizaciones visibles según roles activos del usuario;
- validación de que una organización indicada en el querystring pertenece al usuario;
- rechazo servidor de `Todas`/sin organización para usuarios que no sean `staff` o `superuser` en vistas operativas protegidas;
- uso de la organización real de los objetos para validar detalles de sesiones y permisos;
- filtros de organización en los objetos de edición, detalle, eliminación y archivos de Finanzas;
- acotamiento de formularios y roles a organizaciones autorizadas.

Esto es una mejora real respecto del estado anterior y tiene tests específicos de organización. Sin embargo, el ADR de la rama mantiene `ACCESS_REQUEST_APPROVAL_ENABLED=false` y `GOOGLE_AUTH_ENFORCED=false` como gates hasta completar la evidencia de aislamiento multi-organización en todos los listados, detalles, mutaciones, filtros, exports, JSON y navegación directa.

**Decisión 2.0:** convertir esta mejora en una matriz uniforme de autorización por acción, organización y tipo de recurso. El modelo `PersonaRol` ya permite la relación correcta; el problema pendiente es que no todas las superficies futuras necesariamente pasarán por el mismo enforcement.

## 4. Arquitectura y stack actual

**Verificado en código:**

- Django 5.2.9 y Django REST Framework 3.16.1.
- Python 3.12 como entorno local documentado y usado por el virtualenv actual.
- PostgreSQL configurado como base de datos activa en `dev` y `prod`; SQLite aparece solo como fallback comentado.
- `America/Santiago`, idioma `es-cl` y moneda operacional CLP.
- Templates Django, Bootstrap 5, DataTables y Tom Select cargados desde CDN.
- `gunicorn`, `systemd`, GitHub Actions y SSH para el despliegue previsto.
- Contexto transversal en `plataformaelemental.context` y navegación en `plataformaelemental.navigation`.
- Modelos separados por app dueña; la app legacy `database` fue retirada del producto activo.
- `auditoria` depende de los dominios para registrar acciones, pero `monitor` no forma parte del core operacional ni de la navegación.

La arquitectura actual es un monolito modular, no un conjunto de servicios independientes. Esa decisión es coherente con el tamaño y los flujos actuales.

### Capas observadas

| Capa | Estado actual |
|---|---|
| Modelos y migraciones | Separados por dominio y con relaciones transversales explícitas. |
| Forms | Concentran validación de entrada, pertenencia y reglas de UI. |
| Views | Coordinan HTML, pero aún contienen bastante ORM y lógica de caso de uso. |
| Selectors | Consultas y agregaciones reutilizables, especialmente en Asistencias y Finanzas. |
| Services | Imputación, pagos, reportes, parsing tributario, auditoría y resolución de solicitudes. |
| Signals | Creación inicial de consumo financiero e imputación de pago nuevo. |
| Templates | UX responsive, modales, filtros globales y scripts de operación. |
| API | Superficie mínima, sin CRUD de datos activos. |

El tamaño de las vistas confirma que la separación está avanzada pero no terminada: `asistencias/views.py` tiene 1.369 líneas, `personas/views.py` 1.042 y `finanzas/views.py` 1.313.

## 5. Funcionalidad desarrollada por dominio

### 5.1 `personas`: identidad y CRM

**Modelos:** `Organizacion`, `Persona`, `Rol`, `PersonaRol` y `SolicitudAcceso`.

**Funcionalidad verificada:**

- CRUD de organizaciones con nombre, razón social, RUT, contacto, dirección, logo y exención de IVA.
- CRUD de personas con identidad mínima: RUT, email o teléfono.
- Normalización y validación de RUT chileno y teléfono.
- Asociación opcional de `Persona` con `django.contrib.auth.User`.
- Roles por organización, con asignación, reactivación y desactivación.
- `valor_clase` y `retencion_sii` en `PersonaRol` para configurar honorarios de profesores por persona y organización.
- Listado de personas paginado en servidor, filtros de estado/rol/organización y métricas del periodo.
- Perfil consolidado que reúne actividad académica, pagos, consumos, deuda y documentos relacionados.
- Perfil de profesor con sesiones, asistentes, estimación bruta, retención y monto neto.
- Asociación manual de asistencias presentes a pagos elegibles, delegada al servicio financiero.
- Comandos read-only de auditoría de identidades y datos existentes.

**Límite:** `personas` consolida información, pero no debe convertirse en dueño de imputación, contabilidad ni reglas académicas.

### 5.2 `asistencias`: operación académica

**Modelos:** `Disciplina`, `BloqueHorario`, `SesionClase` y `Asistencia`.

**Funcionalidad verificada:**

- Panel operativo.
- Calendario mensual y degradación a listado cuando el periodo no representa un mes único.
- Creación y edición de disciplinas con colores de badge.
- Creación de sesiones puntuales y generación masiva mensual por días de semana, con máximo opcional.
- Estados de sesión: `programada`, `completada` y `cancelada`.
- Asignación de profesores vigentes por organización.
- Registro masivo de asistencias, cambio de estados y eliminación individual.
- Alta rápida de personas como estudiantes de la organización correcta.
- Reactivación de persona/rol estudiante al incorporarlo a una sesión.
- Listados de estudiantes y profesores con métricas de operación y cobranza.
- Exportación XLSX de asistencias con periodo, organización y permiso de exportación.

### 5.3 Trabajo mobile-first integrado desde `main`

La funcionalidad de agregar asistentes desde el detalle de sesión ya está integrada en `main` mediante `b3b5bf9` y es parte de la base vigente:

- `GET /asistencias/sesiones/<pk>/asistentes/buscar/`.
- `POST /asistencias/sesiones/<pk>/asistentes/agregar/`.
- Búsqueda con mínimo de caracteres, límite de resultados, exclusión de asistentes ya agregados y respuesta mínima `id`, `nombre`, `inactivo`.
- Alta con `get_or_create()` dentro de transacción.
- Validación contra `sesion.disciplina.organizacion`, no contra el filtro global enviado por el navegador.
- Sesión inexistente y sesión de organización no autorizada comparten `404 SESION_NO_ENCONTRADA`.
- El frontend consume el estado financiero real devuelto por backend: `consumido`, `deuda`, `pendiente` o `sin_consumo`.
- Tom Select, modales responsive, asociación accesible de etiqueta/campo y preservación de filtros.
- Auditoría de la acción de agregar asistentes.

Este bloque es una de las entregas funcionales más concretas de la evolución reciente: resolvió la necesidad operativa móvil sin abrir una API general de personas o asistencias.

### 5.4 `finanzas`: cobranza operacional

**Modelos:** `PaymentPlan`, `Payment`, `AttendanceConsumption`.

**Funcionalidad verificada:**

- Planes por organización, precio, cantidad de clases, IVA, vigencia y plan por defecto.
- Pagos por persona y organización, método, comprobante, montos snapshot, IVA y clases asignadas.
- Validación de que el estudiante y los documentos seleccionados corresponden a la organización del flujo.
- Cálculo de neto, IVA y total, respetando exención de IVA.
- Saldo de clases, clases consumidas y deuda.
- Imputación automática inicial de una asistencia presente contra un pago con saldo.
- Imputación de un pago nuevo contra deudas del mismo estudiante, organización, mes y año.
- Asociación manual de una asistencia presente a un pago con validación de persona, organización, periodo y saldo.
- Alta rápida de estudiante desde pagos.
- Exportación operacional de pagos de alumnos y estimación de pagos de profesores.

Regla vigente: el consumo de clases está restringido al mismo mes y año; no hay arrastre automático de saldo entre meses.

### 5.5 `finanzas`: contabilidad básica y documentos

**Modelos:** `DocumentoTributario`, `Category` y `Transaction`.

**Funcionalidad verificada:**

- Documentos tributarios manuales o importados.
- Importación XML-first para DTE y boleta de honorarios.
- Fallback PDF basado en texto seleccionable.
- DTO normalizado, sugerencia de contraparte, detección de duplicados, warnings y revisión humana.
- Visor inline del PDF/XML temporal y de archivos guardados.
- Soporte de comprobantes PDF/imagen en transacciones.
- Categorías globales de ingreso/egreso.
- Transacciones por organización, con categoría, monto, fecha, descripción, respaldo y documentos asociados.
- Reporte por categorías, CSV de libro de caja y exportaciones XLSX.

Regla conceptual importante:

- `Payment` representa cobranza operacional de clases.
- `Transaction` representa movimiento contable/exportable.
- `DocumentoTributario` representa respaldo fiscal/snapshot.
- Crear uno no crea automáticamente los otros.
- El libro de caja usa exclusivamente `Transaction` para evitar doble conteo.

**Límite conocido:** no hay OCR para PDFs escaneados; un PDF sin texto seleccionable requiere revisión manual o queda fuera del parseo confiable.

### 5.6 `api`: superficie REST mínima

Rutas activas:

- `GET /api/health/`.
- `GET /api/status/`.
- `GET /api/version/`.
- `GET /api/me/`, autenticado.

No están registradas rutas activas para personas, asistencias, pagos, documentos, transacciones ni reportes. `ApiAccessKey`, autenticación por token DRF y throttling permanecen en la configuración por compatibilidad, pero no habilitan datos operativos en la API v1.

**Decisión 2.0:** si aparece un consumidor real, abrir endpoints por caso de uso, con organización, autorización, versionado y tests; no reactivar la API antigua completa por anticipación.

### 5.7 Auditoría, Admin y Monitor

`auditoria` implementa `AuditLog` con usuario, fecha, acción, dominio, modelo, objeto, organización, resumen y metadata JSON. La escritura se difiere con `transaction.on_commit()` y no bloquea la operación principal si falla el log.

Se auditan mutaciones sensibles de Personas, Asistencias y Finanzas, además de solicitudes de acceso y vínculos Google. No se auditan lecturas, exports, API mínima, signals ni imputaciones automáticas.

Django Admin funciona como soporte/diagnóstico. `AuditLog` es de solo lectura.

`monitor` permanece en `INSTALLED_APPS` y con migraciones históricas, pero no está incluido en las URLs raíz ni en la navegación. Sus tests históricos están explícitamente omitidos. No debe tratarse como producto vigente.

## 6. Modelo de datos y reglas de negocio centrales

### 6.1 Ownership

| App dueña | Entidades principales | Responsabilidad |
|---|---|---|
| `personas` | `Organizacion`, `Persona`, `Rol`, `PersonaRol`, `SolicitudAcceso` | Identidad y pertenencia organizacional. |
| `asistencias` | `Disciplina`, `BloqueHorario`, `SesionClase`, `Asistencia` | Operación académica. |
| `finanzas` | `PaymentPlan`, `Payment`, `AttendanceConsumption`, `DocumentoTributario`, `Category`, `Transaction` | Cobranza, documentos y contabilidad básica. |
| `auditoria` | `AuditLog` | Trazabilidad transversal. |
| `api` | `ApiAccessKey` | Credencial de compatibilidad para API. |

La app `database` legacy fue retirada. Las migraciones vigentes crean tablas desde las apps dueñas y no deben reintroducir dependencias a `database`.

### 6.2 Relaciones e integridad ya protegidas

- `PersonaRol` es único por persona, rol y organización.
- `Asistencia` es única por sesión y persona.
- `AttendanceConsumption` es uno-a-uno con `Asistencia`.
- `PaymentPlan` es único por organización y nombre.
- `DocumentoTributario` es único por organización, tipo, folio y RUT emisor.
- `Persona.email`, `Organizacion.rut`, `Rol.nombre` y `Rol.codigo` tienen unicidad declarada.
- `Payment.persona` usa `PROTECT`; `Transaction.categoria` usa `PROTECT`.
- Documentos tributarios guardan snapshots legales y pagos guardan montos históricos.

### 6.3 Reglas que hoy viven principalmente en aplicación

- Persona estudiante válida para un pago.
- Compatibilidad de organización entre pago, plan, documento y asistencia.
- Exclusión entre `persona_relacionada` y `organizacion_relacionada` en documento tributario.
- Único plan por defecto por organización.
- Estado financiero derivado de asistencia y pago.

Estas reglas están cubiertas por forms/services/tests en buena parte, pero no todas están protegidas por constraints de base de datos ni por una capa única para futuras escrituras.

## 7. Deuda y riesgos para Elemental 2.0

### Alta prioridad

#### A. Contrato de aislamiento multi-organización

La rama corrigió varios caminos de acceso y agregó pruebas, pero la política completa debe quedar escrita y aplicada a todas las superficies:

- navegación y filtro global;
- listados y dashboards;
- detalle por ID;
- formularios y mutaciones POST;
- archivos adjuntos;
- exports;
- endpoints JSON internos;
- Admin, comandos y futuras APIs;
- usuarios compartidos entre organizaciones.

**Decisión 2.0:** definir si `staff/superuser` tiene acceso global total, si existe un administrador global distinto, y qué puede hacer un usuario con roles en una o varias organizaciones. La organización activa debe ser una restricción del servidor, no solamente un estado visual.

#### B. Ciclo de vida financiero de una asistencia

El signal de `Asistencia` solo procesa `created=True` (`finanzas/signals.py`). El servicio de imputación sí sabe recalcular una asistencia, pero el cambio posterior de `PRESENTE` a `AUSENTE/JUSTIFICADA` no dispara automáticamente ese servicio.

Además, `AttendanceConsumption.pago` usa `SET_NULL`. Al eliminar un `Payment`, el consumo puede quedar sin pago pero conservar el estado `CONSUMIDO` si no existe una política adicional de reparación.

**Decisión 2.0:** definir estados y operaciones reversibles: cambio de asistencia, eliminación/anulación de pago, edición de clases asignadas, corrección retroactiva, cierre mensual y auditoría de recálculo. No se debe resolver con un recálculo destructivo sobre producción sin respaldo, preview y estrategia de reconciliación.

#### C. PostgreSQL como condición de verificación

La configuración activa de desarrollo y producción usa PostgreSQL. La validación local de esta sesión no pudo crear/usar la base de pruebas porque la conexión respondió `connection is bad` sin detalle.

**Decisión 2.0:** disponer de PostgreSQL 16 reproducible localmente o una preproducción equivalente, con datos sintéticos y proceso de restauración probado. Las migraciones de cambios futuros deben probarse sobre copia de datos antes de tocar producción.

### Prioridad media

#### D. Frontera interna de Finanzas

`finanzas` contiene dos subdominios legítimos: cobranza operacional y finanzas/contabilidad. Ya existen `selectors`, `services/imputacion.py`, `services/pagos.py`, `services/reportes.py` y un paquete de documentos.

**Decisión 2.0:** mantener el monolito modular y completar separación interna por casos de uso. Crear una app `cobranzas` solo si adquiere ciclo de vida, modelos y permisos claramente independientes; no crearla solo para mover vistas.

#### E. Conciliación contable

Actualmente `Payment` y `Transaction` están separados intencionalmente. Esto evita doble conteo, pero deja sin resolver conciliación bancaria, comprobante de caja y relación formal entre cobranza operacional y contabilidad.

**Decisión 2.0:** decidir si un pago genera una transacción, si se registra una conciliación separada, quién puede corregirla, cómo se manejan anulaciones y qué documento es fuente de verdad para cierres contables.

#### F. Lógica de dominio concentrada en views

Las vistas siguen siendo grandes y mezclan coordinación HTTP, consultas, autorización contextual y mutaciones. Los siguientes candidatos son `finanzas/views.py` para importación tributaria, `asistencias/views.py` para operaciones de sesión y `personas/views.py` para perfiles/roles.

**Decisión 2.0:** extraer incrementalmente servicios/selectors con contratos y tests existentes, sin cambiar URLs o templates innecesariamente.

#### G. Matriz de permisos definitiva

Existe una matriz funcional base para `admin`, `finanzas`, `solo_lectura` y `staff_asistencia`, además de roles académicos. Sin embargo, aún deben formalizarse acciones como crear personas rápidas, cambiar estado de sesión, eliminar pagos, ver adjuntos, crear API keys y administrar datos compartidos.

**Decisión 2.0:** cerrar una tabla por acción, método HTTP, organización, recurso y rol. Los tests de autorización deben derivarse de esa matriz.

### Prioridad baja o futura

- OCR para documentos escaneados.
- Retención/expurgo de `AuditLog`.
- UI propia de auditoría.
- Alertas y métricas activas.
- Eliminación definitiva de `monitor`, solo después de auditar sus tablas/datos históricos.
- Revisión de `ApiAccessKey` y Token DRF mientras no existan endpoints de datos.
- Regeneración del inventario de reglas de negocio desde el código vigente.

## 8. Lo que no está desarrollado o no debe darse por confirmado

- No existe API pública de CRUD de personas, asistencias o finanzas.
- No existe conciliación bancaria/formal ni puente automático `Payment -> Transaction`.
- No existe cierre mensual financiero con bloqueo y reconciliación.
- No existe OCR confiable para PDFs escaneados.
- No está confirmado el funcionamiento del login Google contra Google real.
- No está confirmado el despliegue real, `systemd`, Nginx, almacenamiento de media, secrets ni healthcheck externo.
- No está confirmado el estado de los datos productivos, duplicados de identidad, usuarios sin Persona, roles históricos o inconsistencias financieras.
- No debe considerarse que la aprobación de solicitudes de acceso está habilitada solo porque el código existe: los flags parten apagados y el ADR exige completar los gates de seguridad.

## 9. Validación realizada en este levantamiento

| Control | Resultado |
|---|---|
| `set -a; source .env.dev; set +a; .venv/bin/python manage.py check` | **Pasa:** `System check identified no issues (0 silenced)`. |
| `set -a; source .env.dev; set +a; .venv/bin/python manage.py makemigrations --check --dry-run` | **Sin cambios de migración:** `No changes detected`; emitió advertencia porque no pudo verificar la historia contra PostgreSQL. |
| `.venv/bin/ruff check .` | **Pasa:** `All checks passed!`. |
| `git diff --check` | **Pasa** para el árbol previo al nuevo reporte. |
| Suite `set -a; source .env.dev; set +a; timeout 180 .venv/bin/python manage.py test --keepdb -v 2` | **No ejecutó tests:** encontró 313 tests, pero abortó al crear/usar la base PostgreSQL por `OperationalError: connection is bad`. |

La falla de la suite local es un bloqueo de infraestructura/conectividad, no evidencia de que los 313 tests fallen. Tampoco permite afirmar que toda la rama esté validada localmente contra PostgreSQL.

## 10. Documentación y trazabilidad

Documentos que deben seguir siendo referencia para 2.0:

- `docs/INDICE.md`.
- `docs/arquitectura/PLATAFORMA.md`.
- `docs/arquitectura/MODELO_DATOS.md`.
- `docs/arquitectura/PERMISOS_Y_ROLES.md`.
- `docs/arquitectura/DEUDA_TECNICA.md`.
- `docs/apps/PERSONAS.md`.
- `docs/apps/ASISTENCIAS.md`.
- `docs/apps/FINANZAS.md`.
- `docs/apps/API.md`.
- `docs/apps/AUDITORIA.md`.
- `docs/adr/0001-autenticacion-google-y-solicitudes-acceso.md`.
- `docs/operacion/DEPLOY.md`.

Hay documentación que debe actualizarse o tratarse como histórica antes de usarla como evidencia:

- `README.md` conserva una “última validación conocida” de 99 tests, anterior a la rama actual.
- `docs/apps/UX.md` todavía contiene una limitación que dice que no se implementa auditoría transversal, mientras `auditoria` sí existe y tiene documentación propia.
- `docs/reporte.md` está ignorado por Git y corresponde a un briefing local anterior; no debe reemplazar este levantamiento como fotografía de la rama actual.

## 11. Orden recomendado de decisiones para Elemental 2.0

1. **Cerrar el modelo de acceso:** organizaciones, roles, permisos por acción, alcance de `staff/superuser`, usuarios compartidos y comportamiento sin organización activa.
2. **Auditar datos antes de migrar:** identidades, RUT/email, `Persona.user`, roles, pagos, consumos y documentos. Solo lectura, sin corregir automáticamente.
3. **Definir invariantes financieras:** ciclo de vida de asistencia/consumo/pago, anulaciones, recálculos, cierre mensual y fuente contable.
4. **Preparar PostgreSQL reproducible:** instalación o entorno equivalente, pruebas de concurrencia, `migrate --plan`, backup/restore y suite completa.
5. **Aplicar correcciones mínimas de seguridad e integridad:** primero reglas de organización y consumo financiero, luego constraints compatibles con los datos existentes.
6. **Extraer responsabilidades desde views de forma incremental:** conservar contratos HTML/JSON y mover solo casos de uso claros a services/selectors.
7. **Decidir la expansión de producto:** API de datos, conciliación, OCR, monitor y posibles dominios nuevos solo después de estabilizar el núcleo.

## 12. Conclusión para la reunión de arquitectura

La plataforma ya tiene un núcleo operativo real y no parte desde cero: administra personas, organizaciones, clases, asistencias, cobranza, documentación tributaria, caja, exportaciones, auditoría y despliegue automatizado. La rama actual agrega una base seria para gobernar el acceso mediante Google y solicitudes administrativas, con flags seguros por defecto y controles de concurrencia.

El riesgo principal para Elemental 2.0 no es la falta de pantallas, sino la consistencia transversal: quién puede ver o mutar cada organización, cómo se corrige una operación financiera histórica y cuál es la fuente contable definitiva. Si esas decisiones se cierran primero, el monolito modular actual puede evolucionar sin una reescritura ni una expansión arquitectónica prematura.

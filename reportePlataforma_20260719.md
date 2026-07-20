# Reporte de estado actual — Plataforma Elemental

Fecha de levantamiento: 2026-07-19  
Base revisada: árbol de trabajo actual, limpio al inicio de la revisión (`git status --short` sin salida), HEAD `b3b5bf9`.

## 1. Propósito, alcance y criterio de evidencia

Este documento describe **lo que está desarrollado hoy** para entregarlo a otro agente que continúe la plataforma. Es un levantamiento técnico y funcional: no propone una reescritura ni modifica comportamiento del producto.

Se revisaron código Python, modelos, migraciones, rutas, vistas, formularios, servicios, selectors, templates, tests, configuración, documentación y automatización de deploy. La fuente principal de verdad es el código; la documentación se usó como contexto y se contrastó contra él.

Leyenda:

- **Verificado en código:** ruta, modelo, regla o flujo presente en los archivos indicados.
- **Verificado con ejecución SQLite temporal:** pasó `manage.py check` o la detección de cambios de migración usando una configuración temporal fuera del repositorio.
- **No verificado en runtime:** no se confirmó contra PostgreSQL local/producción, navegador real ni servicios externos.
- **Riesgo:** observación comprobable que conviene priorizar antes de ampliar el producto.

## 2. Resumen ejecutivo

Plataforma Elemental es un **monolito Django modular** para operación interna de organizaciones: CRM de personas y roles, operación académica, cobranza por clases, documentos tributarios y caja/contabilidad básica. La interfaz HTML es el producto operativo; la API REST quedó intencionalmente reducida a salud, versión y autenticación mínima.

El producto activo se divide en cuatro dominios visibles:

1. `personas`: identidad, organizaciones, roles y perfiles consolidados.
2. `asistencias`: disciplinas, sesiones, asistencia y operación diaria de clases.
3. `finanzas`: planes, pagos, consumo de clases, documentos tributarios, transacciones, categorías y exportaciones.
4. `api`: health/status/version y `me` autenticado.

Además existe `auditoria` como infraestructura de trazabilidad y `monitor` como app histórica aún migrada e instalada, pero no enrutable desde las URLs raíz ni visible en la navegación principal.

La base funcional es amplia y está cubierta por 255 métodos de prueba declarados en el árbol. Los controles estáticos ejecutados no encontraron errores de Django ni migraciones pendientes. La validación completa contra PostgreSQL no pudo realizarse porque la conexión local falla antes de construir el grafo de migraciones.

Las prioridades técnicas más importantes detectadas son:

1. Formalizar y endurecer aislamiento de permisos por organización: varias vistas HTML autorizan por rol global y permiten trabajar con `organizacion=Todas`.
2. Reducir lógica de negocio aún concentrada en vistas, especialmente `finanzas/views.py`, `asistencias/views.py` y el perfil de personas.
3. Promover reglas críticas que están solo en formularios/servicios a constraints de base de datos cuando sean estables.
4. Recuperar validación real de PostgreSQL local/preproducción y ejecutar la suite CI completa allí.
5. Decidir explícitamente la conciliación entre `Payment` y `Transaction`; hoy están correctamente separados, pero no existe puente contable formal.

## 3. Arquitectura y componentes

### 3.1 Stack y ejecución

**Verificado en código:**

- Python local disponible en `.venv`: 3.12.13.
- Django 5.2.9, Django REST Framework 3.16.1.
- Dependencias de producto: Django, DRF, Gunicorn, OpenPyXL, Pillow, psycopg 3 y pypdf (`requirements.txt`).
- Base configurada: PostgreSQL tanto para `dev` como para `prod` (`plataformaelemental/config/dev.py`, `prod.py`).
- Zona horaria: `America/Santiago`; idioma `es-cl` (`config/base.py`).
- UI: Django templates + Bootstrap 5, Bootstrap Icons, DataTables, Tom Select; las librerías de UI se cargan desde CDN.
- WSGI/ASGI estándar Django; producción prevista con Gunicorn y systemd.

Configuración:

- `DJANGO_ENV` resuelve `dev` por defecto y `prod` para producción (`plataformaelemental/config/__init__.py`).
- El desarrollo exige variables `POSTGRES_*`; no hay fallback SQLite activo en el código, solo bloques comentados.
- `base.py` carga `monitor` y `rest_framework.authtoken` en `INSTALLED_APPS`.
- Las plantillas reciben el contexto de período/organización y navegación mediante context processors globales.

### 3.2 Dependencias entre dominios

El ownership está en general bien delimitado:

- `personas` es dueño de `Organizacion`, `Persona`, `Rol`, `PersonaRol`.
- `asistencias` es dueño de `Disciplina`, `BloqueHorario`, `SesionClase`, `Asistencia`.
- `finanzas` es dueño de `PaymentPlan`, `Payment`, `AttendanceConsumption`, `DocumentoTributario`, `Transaction`, `Category`.
- `auditoria` es dueño de `AuditLog`.
- `api` es dueño de `ApiAccessKey`.

No se encontraron imports directos de `views.py` entre apps, cumpliendo la regla declarada. Sí existen dependencias de modelos entre dominios, coherentes con los casos de uso: asistencias consume identidad; finanzas consume identidad y asistencias; auditoría referencia organización y usuario.

La dependencia transversal correcta para filtros y navegación vive en `plataformaelemental.context` y `plataformaelemental.navigation`.

### 3.3 Capas actuales

| Capa | Estado comprobado |
|---|---|
| Models/migraciones | Separadas por app; relaciones transversales explícitas. |
| Forms | Validación de ingreso y límites de selección para la mayoría de flujos HTML. |
| Views | Coordinan UI, pero aún contienen bastante lógica de negocio y acceso ORM. |
| Selectors | Consultas y agregaciones reutilizables en asistencias y finanzas. |
| Services | Imputación de pagos, reportes/exportaciones, creación de estudiante rápida, parsing tributario y auditoría. |
| Signals | Crean consumo al crear una asistencia e imputan deudas al crear un pago. |
| Templates | Interfaz responsive con modales, filtros y scripts específicos. |
| API | Superficie mínima, sin endpoints operativos de datos. |

Tamaño orientativo: `asistencias/views.py` tiene 1.362 líneas, `finanzas/views.py` 1.295 y `personas/views.py` 812. Esto confirma que la separación en services/selectors es parcial, no completa.

## 4. Navegación, autenticación y contexto transversal

### 4.1 Accesos y rutas raíz

**Verificado en `plataformaelemental/urls.py`:**

- `/`: panel general `Elemental Apps`.
- `/app/`: redirección temporal a `/`.
- `/accounts/login/` y `/accounts/logout/`: autenticación de sesión Django.
- `/admin/`: Django Admin.
- `/asistencias/`, `/personas/`, `/finanzas/`: productos HTML activos.
- `/api/`: API mínima.
- `/monitor/` **no está incluido** en las URLs raíz.
- `MEDIA_URL` se sirve mediante `static(...)` desde URLs raíz; en despliegue debe quedar cubierto también por la configuración de servidor correspondiente.

El login utiliza `CustomLoginForm`, conserva CSRF y respeta `next`. El panel y la navegación requieren usuario autenticado; la navegación se genera según los permisos evaluados por código.

### 4.2 Filtros globales

Los filtros globales son query parameters:

- `periodo_mes`
- `periodo_anio`
- `organizacion`

`plataformaelemental.context` normaliza mes/año, permite `todos`, usa el mes/año corriente por defecto y entrega organización activa si el identificador existe. También provee descripciones de período y la lista de organizaciones.

`plataformaelemental.navigation` conserva estos filtros en los enlaces de sidebar. Las vistas y selectors de los tres dominios principales los consumen en forma amplia. Hay tests para preservación de querystring, modales y filtros.

Límite comprobado: seleccionar una organización inexistente produce `organizacion_activa=None`; no se trata como error explícito. La operación resultante es equivalente a no filtrar en las vistas que usan `if organizacion:`.

### 4.3 Navegación visible

La sidebar responsive muestra, según permisos:

- Asistencias: Panel, Calendario, Asistencias, Estudiantes, Profesores, Disciplinas.
- Finanzas: Panel, Pagos, Documentos, Transacciones, Planes, Categorías.
- Personas: Panel, Personas, Organizaciones.
- Admin: sólo para `staff` o `superuser`.

No muestra Monitor ni una UI para API. En móvil usa patrón offcanvas; la barra superior conserva filtros, usuario, logout y logo/iniciales de la organización activa.

## 5. Modelo de datos e integridad

### 5.1 Identidad y organizaciones (`personas`)

`Organizacion`:

- Nombre, razón social, RUT único, logo opcional, exención de IVA, contacto, dirección y timestamps.
- `es_exenta_iva` modifica el cálculo de IVA de planes y pagos.

`Persona`:

- Nombres, apellidos, email opcional único, teléfono, RUT opcional, fecha de nacimiento, activo y vínculo opcional uno-a-uno con usuario Django.
- En `clean()` exige identidad mínima: RUT, email o teléfono; normaliza RUT/teléfono y detecta RUT repetido a nivel de aplicación.
- El campo `rut` no tiene constraint `unique=True` de base de datos; la unicidad depende de `clean()` y no protege escrituras que lo eviten.

`Rol` y `PersonaRol`:

- Rol con `nombre` y `codigo` únicos.
- La asignación está ligada a persona + rol + organización y tiene `unique_together` para esa terna.
- `PersonaRol` posee `activo`, `valor_clase` y `retencion_sii`; estos últimos permiten que el costo del profesor varíe por organización.

### 5.2 Operación académica (`asistencias`)

`Disciplina`:

- Pertenece a organización; nombre/nivel únicos por organización; activa; color de badge.

`BloqueHorario`:

- Pertenece a organización, contiene día y horario, y puede apuntar a disciplina. La disciplina se pone a `NULL` si se elimina.

`SesionClase`:

- Pertenece a disciplina, tiene bloque opcional, profesores M2M, fecha, estado (`programada`, `completada`, `cancelada`), cupo y notas.
- Índice por fecha y disciplina.

`Asistencia`:

- Une sesión y persona; estados `presente`, `ausente`, `justificada`.
- Una persona sólo puede tener una asistencia por sesión (`unique_together`).

### 5.3 Cobranza y contabilidad (`finanzas`)

`PaymentPlan`:

- Organización, nombre, número de clases, precio, IVA incluido/no incluido, vigencia, activo y bandera de plan por defecto.
- La lógica de `save()` garantiza por aplicación que una organización tenga un plan por defecto y lo reasigna al borrar el plan por defecto.
- No existe constraint parcial de base de datos que impida dos planes por defecto en escrituras concurrentes o administrativas que eviten esa lógica.

`Payment`:

- Cobranza operacional a una persona: organización, plan opcional, documento tributario opcional, fecha, método, comprobante, IVA, montos snapshot, clases y observaciones.
- Al guardar, toma clases del plan si no se indicaron, aplica exención de IVA de la organización y calcula neto/IVA/total.
- Tiene índices por fecha/organización y persona/fecha.
- El filtro `limit_choices_to` de persona ayuda al admin, pero la condición “estudiante activo de esa organización” se hace cumplir realmente en `PaymentForm.clean_persona()`; no es un constraint de BD.

`AttendanceConsumption`:

- Relación uno-a-uno con asistencia; vincula opcionalmente un pago y registra fecha de clase y estado `consumido`, `pendiente` o `deuda`.
- Un consumo por asistencia queda protegido por `OneToOneField`.

`DocumentoTributario`:

- Documento fiscal con tipo, fuente, folio, emisor/receptor, montos, retención, archivos PDF/XML, metadata, documento relacionado y contraparte opcional (persona u organización).
- Unicidad operativa de BD: organización + tipo + folio + RUT emisor.
- La exclusión entre `persona_relacionada` y `organizacion_relacionada` está en el formulario, no en una constraint de BD.

`Category` y `Transaction`:

- Categoría global de ingreso/egreso; no está ligada a organización.
- Transacción: organización, categoría, fecha, tipo, monto, descripción, respaldo y M2M con documentos tributarios.
- `Transaction.tipo` se deriva de la categoría en el formulario.

### 5.4 Auditoría y API

`AuditLog` guarda usuario, fecha, acción, dominio, modelo, objeto, organización, resumen y metadata JSON. Tiene índices para objeto, organización/fecha y usuario/fecha.

`ApiAccessKey` guarda sólo prefijo y hash SHA-256; la clave plana se genera y se imprime una única vez mediante comando. No tiene relación con personas/usuarios.

### 5.5 Migraciones

Hay migraciones para `personas`, `asistencias`, `finanzas`, `api`, `auditoria` y `monitor`. La app legacy `database` no existe en el árbol ni está instalada. `finanzas` pasa de `0001` a `0003`: la `0003_repair_missing_tables` es una `RunPython` de reparación histórica; no hay archivo `0002` versionado.

**Verificado con SQLite temporal:** `manage.py makemigrations --check --dry-run` informó “No changes detected”. Esto valida que los modelos actuales no generan migraciones nuevas, pero no confirma el estado aplicado de la base PostgreSQL real.

## 6. Roles, permisos y aislamiento organizacional

### 6.1 Política implementada

`personas.permissions` define roles normalizados:

- `admin`
- `finanzas`
- `profesor`
- `solo_lectura`
- `staff_asistencia`

Y acciones: ver/operar finanzas, pagos, transacciones, documentos, exportar, editar asistencias, administrar personas y administrar sesiones.

`superuser` y `staff` pasan todos los chequeos. Para usuarios normales se consulta `PersonaRol` activo; cuando se entrega organización al helper, filtra correctamente por ella.

Matriz efectiva resumida:

| Acción | Roles permitidos por código |
|---|---|
| Ver finanzas | admin, finanzas, solo_lectura |
| Operar pagos/transacciones/documentos | admin, finanzas |
| Exportar datos | admin, finanzas |
| Administrar personas | admin |
| Administrar sesiones / editar asistencias | admin, staff_asistencia |

### 6.2 Diferencias de enforcement detectadas

**Riesgo alto — aislamiento por organización incompleto en UI HTML.**

- Todas las vistas principales de `asistencias` y `personas` usan `@role_required(ROLE_ADMIN)` (`asistencias/views.py`, `personas/views.py`). Ese decorador consulta roles activos sin filtrar organización.
- Si el querystring no trae organización, las vistas normalmente construyen querysets sin filtro. Por código, un usuario con rol `admin` en una organización puede ver/operar el conjunto completo en estas vistas si no hay otro control específico.
- En finanzas, los decoradores sí entregan la organización tomada de la URL a `usuario_tiene_permiso`. Pero con `organizacion` ausente o inválida se evalúa el rol sin organización, y los selectors/listados quedan sin filtro de organización. Por código, un rol `finanzas` activo en alguna organización puede acceder a “Todas” las organizaciones.
- La navegación usa la misma lógica con la organización activa; puede ocultar accesos para una organización concreta, pero no impone el aislamiento sobre las rutas ya conocidas.

**Riesgo medio — permiso de `staff_asistencia` no es consistente entre UI y endpoints móviles.**

- El mapa de acciones permite `staff_asistencia` para administrar sesiones.
- Los endpoints JSON de búsqueda/agregado de asistentes verifican `ACCION_ADMINISTRAR_SESIONES` contra la organización real de la sesión y, por ello, admiten ese rol.
- Las vistas HTML principales de asistencias piden sólo `ROLE_ADMIN`, por lo que `staff_asistencia` no puede usar el flujo HTML equivalente. Es una diferencia comprobable de contrato, no sólo documental.

No se debe asumir que cada usuario Django tenga `Persona`, ni que todos los códigos de rol en datos sean los mencionados: el código normaliza aliases, pero los datos productivos no fueron consultados.

## 7. Funcionalidad desarrollada por dominio

### 7.1 Personas / CRM

Rutas activas (`personas/urls.py`):

- Panel: `/personas/`.
- Organizaciones: listado, creación, detalle, edición.
- Personas: listado, creación, detalle, edición.

Flujos comprobados:

1. Crear y editar personas con validación de identidad mínima, RUT chileno y teléfono normalizado.
2. Crear/editar organizaciones, incluyendo logo y bandera de exención IVA.
3. Asignar, reactivar, desactivar y configurar roles por organización.
4. Configurar valor por clase y retención SII para roles `PROFESOR`.
5. Perfil consolidado de estudiante: asistencias, pagos, consumos, deuda, saldo y documentos asociados.
6. Perfil consolidado de profesor: sesiones del período, asistentes, estimación bruta, retención y neto; permite cambiar estado de sesiones donde esa persona es profesor.
7. Desde el perfil de estudiante se puede asociar manualmente una asistencia presente a un pago elegible del mismo mes y organización.
8. Panel/listado con métricas y filtros de período/organización; búsqueda y paginación del lado servidor.
9. Auditoría al crear/editar persona y cambiar/asignar roles.

Límite funcional: personas consolida información de asistencias y finanzas, pero no es dueño de la lógica de imputación; delega a `finanzas.services.imputacion`.

### 7.2 Asistencias / operación académica

Rutas activas (`asistencias/urls.py`):

- Panel, calendario, listado de asistencias, estudiantes, profesores y disciplinas.
- Detalle/edición de sesión y disciplina.
- Exportación XLSX de asistencias.
- Dos endpoints JSON para la experiencia móvil de agregar asistentes.

Flujos comprobados:

1. Crear, editar y listar disciplinas; sólo las activas aparecen en selección operativa.
2. Crear sesiones puntuales y generación masiva mensual a partir de días seleccionados/bloques, con máximo opcional.
3. Ver calendario/listado de sesiones por período y organización; `sesiones/` redirige al calendario por compatibilidad.
4. Asociar profesores vigentes a sesiones; la selección filtra persona y rol activo de profesor.
5. Registrar asistencias masivas y cambiar su estado.
6. Crear rápidamente una persona-estudiante desde operación, siempre que exista organización seleccionada y rol `ESTUDIANTE` configurado.
7. Al agregar asistentes, puede reactivar persona o rol de estudiante inactivo para continuidad operativa.
8. Cerrar/completar la sesión desde el flujo de asistentes y eliminar sesión o asistencia individual.
9. Consultar listados operativos de estudiantes/profesores y panel con deuda, actividad, clases restantes y sesiones.
10. Exportar asistencias XLSX con filtros globales y permiso explícito de exportación.

#### Experiencia móvil de agregar asistentes

Endpoints:

- `GET /asistencias/sesiones/<pk>/asistentes/buscar/`
- `POST /asistencias/sesiones/<pk>/asistentes/agregar/`

Contrato comprobado:

- El GET busca por nombre, email o RUT, exige término mínimo, limita resultado y devuelve sólo `id`, `nombre`, `inactivo`.
- Ambos endpoints validan el permiso sobre la organización real de la sesión. Sesión inexistente y sesión ajena se devuelven de forma deliberadamente indistinguible (`404`, código `SESION_NO_ENCONTRADA`).
- El POST acepta formulario o JSON, evita duplicar la asistencia, crea consumo financiero vía signal y devuelve estado financiero calculado para la UI.
- El template de detalle usa Tom Select y tiene controles para accesibilidad y modales mobile-first.

### 7.3 Cobranza operacional

Concepto fundamental comprobado: un pago (`Payment`) no es una transacción de caja (`Transaction`) ni un documento fiscal (`DocumentoTributario`). Estas tres entidades pueden asociarse, pero no se crean mutuamente de forma automática.

Flujo de pago:

1. Usuario autorizado abre Pagos y crea/edita un `Payment`.
2. El formulario filtra estudiantes, exige rol `ESTUDIANTE` activo en la organización, precarga plan por defecto e IVA según la organización.
3. Una transferencia exige número de comprobante; otros métodos lo limpian.
4. El modelo calcula neto, IVA y total y conserva los montos históricos.
5. El `post_save` de un pago nuevo intenta imputarlo a deudas de la misma persona, organización, mes y año, en orden de clase.
6. Un pago sólo puede consumir asistencias presentes del mismo mes/año; las clases no se arrastran entre meses.

Flujo de asistencia a consumo:

1. Al crear `Asistencia`, el signal llama a `asignar_consumo_asistencia`.
2. Si no está `presente`, queda `pendiente` y sin pago.
3. Si está presente, busca el primer pago con saldo de esa persona, organización y mismo mes/año.
4. Si existe, queda `consumido`; si no, genera `deuda`.
5. Un pago posterior puede convertir deudas del mismo período a consumos.

El servicio también permite asociación manual a un pago; valida estado presente, misma persona, misma organización, mismo mes/año y saldo disponible.

### 7.4 Finanzas / contabilidad básica

Rutas activas (`finanzas/urls.py`):

- Panel, planes, pagos y detalle de pago.
- Documentos tributarios: listado, importación, preview de parseo, archivos temporales, detalle, edición y eliminación.
- Categorías, transacciones, detalle/archivo/edición/eliminación.
- Reporte por categorías.
- Exportaciones CSV/XLSX de pagos y transacciones; libro de caja CSV; estimación de pagos a profesores.

Funcionalidad comprobada:

- Gestión de planes: primer plan por organización queda por defecto; se puede reasignar; precio puede incluir IVA; respeta exención de organización.
- Gestión de pagos con modales, alta rápida de estudiante, estado operacional y detalle de consumo.
- Gestión de categorías de ingreso/egreso.
- Gestión de transacciones: tipo derivado de categoría, respaldo de archivo, asociación M2M a documentos tributarios y detalle con visor inline de PDF/imagen cuando corresponde.
- Dashboard separa métricas contables (`Transaction`) de cobranza (`Payment`/`AttendanceConsumption`) para evitar doble conteo.
- Reporte de categorías y exportaciones filtradas por período/organización.
- El libro de caja CSV usa exclusivamente `Transaction`, exige mes y año específicos, ordena fecha/id ascendente y genera correlativo/Msg estable.
- La estimación de pagos a profesores se basa en sesiones/asistencias y la tarifa/retención del `PersonaRol`; no es una transacción contable.

### 7.5 Documentos tributarios asistidos

Flujo comprobado:

1. Se sube un único archivo XML o PDF.
2. El backend clasifica contenido/extensión.
3. Para XML identifica DTE clásico o boleta de honorarios; para PDF utiliza fallback de texto (pypdf y alternativa de sistema según parser).
4. Normaliza a DTO interno, detecta posibles duplicados y sugiere contraparte por RUT/nombre dentro de la organización.
5. Guarda temporalmente archivos/payload por sesión para mostrar revisión y visor inline.
6. Presenta formularios precargados; subir no crea documento definitivo.
7. Al confirmar, crea el documento y opcionalmente un pago sugerido cuando el documento es boleta de venta; la revisión humana es obligatoria.
8. El documento puede asociarse manualmente a una persona o a otra organización como contraparte, y a pagos/transacciones.

Cobertura declarada por código/tests: DTE XML, boleta de honorarios XML, PDFs con texto de boleta de honorarios y boletas electrónicas tipo 39/41. PDFs escaneados/OCR no están resueltos.

### 7.6 API mínima

Endpoints registrados:

- `GET /api/health/` → `{status: ok}` público.
- `GET /api/status/` → estado y nombre de servicio público.
- `GET /api/version/` → nombre y versión pública.
- `GET /api/me/` → requiere usuario autenticado de Django/DRF; devuelve username, booleano y timestamp.

No están registrados endpoints API de personas, asistencias, pagos, documentos, transacciones ni reportes. Las rutas legacy/v1 desactivadas responden 404 por ausencia de URL.

La autenticación API soporta sesión, Token DRF y API key. La API key se puede recibir por `X-API-Key` o `Authorization: ApiKey ...`, se hashea, actualiza último uso y sólo entrega permisos de lectura. En la práctica no hay recursos operativos de lectura expuestos que la usen; tampoco autoriza `/api/me/`, porque esa vista exige `IsAuthenticated`.

Throttling configurado: 120/min y 5.000/día para API por usuario/API key/IP; hay clases separadas de auth que no se ven aplicadas específicamente a una vista de login API activa.

### 7.7 Auditoría, Admin y Monitor

Auditoría:

- Registro asíncrono con `transaction.on_commit` para no auditar transacciones revertidas.
- Si falla el log, registra warning y no bloquea la operación principal.
- Evita persistir RUT/email/teléfono completos en diffs de persona.
- Cubre creación/edición de personas y roles, operaciones sensibles de sesiones/asistencias, pagos, documentos y transacciones.
- No audita lecturas, exports, API mínima, signals ni imputación automática.
- `AuditLog` es de sólo lectura en Django Admin.

Django Admin:

- Es herramienta de soporte para staff/superuser, no operación diaria.
- Cubre modelos críticos de personas, asistencias, finanzas y auditoría.
- La documentación declara bloqueo de `delete_selected` para modelos críticos y los tests lo cubren.

Monitor:

- Código, modelos, migración, formularios, servicios de discovery y tests históricos están presentes.
- No está enrutable desde la app raíz, no aparece en sidebar/Admin, y documentación lo declara archivado.
- Se mantiene en `INSTALLED_APPS` por migraciones/datos potencialmente históricos.
- Existe `auditar_monitor`, comando read-only que cuenta registros.
- Varias clases de tests de monitor están marcadas `@skip` de forma explícita por archivo archivado.

## 8. Operación, seguridad y despliegue

### 8.1 Controles configurados

- Password validators estándar de Django.
- Cookies HttpOnly y SameSite=Lax; en producción Secure, expiración al cerrar navegador y renovación por request.
- `SECURE_CONTENT_TYPE_NOSNIFF`, política de referrer same-origin y X-Frame-Options DENY por defecto.
- Producción configura proxy HTTPS, redirect SSL y HSTS configurable.
- Vistas de archivos tributarios/transacciones usan `xframe_options_sameorigin` para permitir visores inline de origen propio, como excepción puntual al default DENY.
- `.env` y artefactos de base/dumps están ignorados; `docs/SECURITY.md` prohíbe secretos reales versionados.

No se verificó el contenido de secretos ni conectividad externa. No se ejecutó un escáner de secretos; el repo documenta que no existe job obligatorio para ello.

### 8.2 CI/CD implementado

`.github/workflows/deploy.yml`:

1. En push a `main` o ejecución manual, levanta PostgreSQL 16 en GitHub Actions.
2. Usa Python 3.13, instala dependencias y desarrollo.
3. Ejecuta `ruff check .` y `python manage.py test asistencias.tests personas.tests finanzas.tests api.tests`.
4. Si pasa, abre SSH, hace `git fetch`, `checkout main` y `git reset --hard origin/main` en el servidor remoto.
5. Ejecuta `scripts/deploy.sh` y finalmente llama healthcheck HTTPS a `apps.avx.cl/`.

`scripts/deploy.sh`:

- exige archivo de entorno, `DJANGO_ENV=prod`, host/puerto/usuario/base PostgreSQL esperados;
- crea backup PostgreSQL custom antes de migrar;
- instala dependencias, migra, limpia sesiones, colecta estáticos, corre `check --deploy` y reinicia systemd;
- falla si no existe la unidad configurada.

**No verificado:** secrets de GitHub, host remoto, backup, restauración, deploy real, systemd y healthcheck externo.

## 9. Pruebas y verificación de este levantamiento

### 9.1 Evidencia estática

- 255 métodos `test_*` declarados en 21 clases de prueba en el árbol.
- Pruebas amplias para asistencias, finanzas, personas, API, UX/admin, auditoría y monitor histórico.
- `ruff` está declarado en `requirements-dev.txt`, pero el binario no está instalado en `.venv` actual (`.venv/bin/ruff: No such file or directory`). Por tanto no se pudo ejecutar lint localmente.

### 9.2 Comandos ejecutados durante este reporte

| Comando/acción | Resultado |
|---|---|
| `git status --short` | Árbol limpio antes de crear este archivo. |
| SQLite temporal: `manage.py check` | Pasa: 0 issues silenciados. |
| SQLite temporal: `makemigrations --check --dry-run` | Pasa: no hay cambios detectados. |
| Suite completa contra SQLite temporal | El único fallo aislado fue `api.tests.PostgreSQLDatabaseConnectionTests.test_default_database_usa_postgresql_y_responde_consulta_basica`, porque el entorno temporal era SQLite y el test exige vendor PostgreSQL. No se interpreta como fallo de la aplicación. |
| API mínima y relaciones cross-app en SQLite temporal | Sus primeros tests aislados pasan; la aserción específica de vendor PostgreSQL no aplica a SQLite. |
| Suite extensa por módulos en SQLite | Iniciada, pero la ejecución disponible se interrumpió antes del resumen por límite de sesión. No afirmar que pasó completa. |
| PostgreSQL local: `showmigrations --plan` | Bloqueado: `django.db.utils.OperationalError: connection is bad: no error details available`. |

Conclusión de calidad: el código pasa los checks de estructura Django y no tiene migraciones pendientes. La evidencia de tests no sustituye una ejecución completa sobre PostgreSQL, que es la base real configurada y la que CI usa.

## 10. Riesgos y brechas priorizadas

### Alta prioridad

1. **Autorización multi-organización insuficientemente cerrada.** Ver sección 6.2. El modelo almacena roles por organización, pero varias rutas autorizan por rol global o permiten acceder con filtro “Todas”. Antes de crecer en usuarios/organizaciones, definir contrato: si un rol no staff debe ver sólo sus organizaciones, el filtro debe ser una restricción de servidor, no sólo UX.

2. **PostgreSQL local no verificable en este entorno.** La conexión falla sin detalle; no se pudo leer estado aplicado de migraciones ni correr la suite de CI sobre el motor de destino. Resolver conectividad o establecer una réplica/preproducción reproducible antes de migraciones funcionales nuevas.

3. **Reglas críticas sin constraint de BD.** Comprobadas: exclusión persona/organización contraparte tributaria, único plan por defecto y pertenencia de relaciones de pago/documento/transacción se validan mayormente en formularios/servicios. Esto es susceptible a admin, comandos, concurrencia o integraciones futuras que no reutilicen los forms.

### Prioridad media

4. **Lógica de dominio en views.** Las vistas largas contienen mutaciones ORM, autorizaciones contextuales, reglas de formación de datos y flujo de negocio. El parsing tributario, edición/importación de documentos, sesiones y perfiles son los candidatos de extracción incremental, preservando contratos y tests.

5. **Conciliación contable pendiente.** `Payment` y `Transaction` están separados de forma sana para evitar doble conteo, pero no hay relación formal ni flujo de conciliación. Esto debe ser decisión de producto/contabilidad, no una automatización implícita.

6. **Monitor archivado pero instalado.** Aumenta superficie de migraciones y dependencias aunque no esté activo. Antes de eliminarlo se requiere auditoría real de tablas/datos; mientras tanto debe tratarse como histórico, no como funcionalidad ofrecida.

7. **Cobertura de CI no incluye explícitamente `auditoria.tests`, `monitor.tests` ni `plataformaelemental.tests`.** Existen esas pruebas y son ejecutables a nivel de proyecto, pero la workflow sólo enumera cuatro módulos. Decidir si la exclusión es intencional.

8. **Ruff no está disponible en el entorno local actual.** El workflow lo instala desde `requirements-dev.txt`, pero `.venv` no. El setup local no permite reproducir exactamente el lint sin instalar esa dependencia.

### Prioridad baja / decisiones abiertas

9. No hay OCR para PDFs escaneados; el importador depende de texto seleccionable.
10. No existe retención/expurgo automático para `AuditLog`.
11. No existe UI de auditoría fuera de Django Admin.
12. No existe alerta formal ni observabilidad activa.
13. API key y Token DRF permanecen configurados para una API de datos actualmente inexistente; conservarlos tiene compatibilidad histórica, pero agrega superficie conceptual que debe revisarse al reabrir endpoints.
14. El inventario de reglas de negocio (`docs/arquitectura/INVENTARIO_REGLAS_NEGOCIO.md`) declara estar pendiente de regeneración; este reporte puede servir como insumo, pero no reemplaza una matriz mantenida junto al código.

## 11. Requerimientos funcionales que hoy sí soporta la plataforma

- Administrar varias organizaciones, con período y organización como contexto global de operación.
- Mantener personas, identidad mínima, organizaciones, roles y parámetros económicos de profesores por organización.
- Crear disciplinas y programar sesiones, incluidas sesiones masivas mensuales.
- Registrar y gestionar asistencias, con interfaz desktop y experiencia de agregado optimizada para móvil.
- Detectar automáticamente deuda de clases y consumir cupos de pagos dentro del mismo mes/año.
- Registrar planes y pagos académicos con IVA/exención, comprobantes y saldo de clases.
- Operar documentos tributarios manualmente o mediante importación XML/PDF con revisión humana.
- Registrar movimientos reales de caja, categorizarlos, respaldarlos y exportarlos para contabilidad.
- Exportar información operacional y contable en CSV/XLSX, con permisos específicos.
- Mantener trazabilidad mínima de operaciones sensibles.
- Ofrecer health/status/version y una comprobación mínima de autenticación por API.
- Desplegar automáticamente desde `main` a una infraestructura prevista con PostgreSQL, SSH y systemd.

## 12. Requerimientos no implementados o no confirmados

- API de datos operacionales o financieros para consumidores externos.
- Conciliación bancaria/formal y puente `Payment -> Transaction`.
- Cierre de mes, recálculo o corrección automática de inconsistencias financieras.
- OCR de documentos escaneados.
- Política formal y completamente aplicada de aislamiento por organización para usuarios no staff.
- Matriz de roles/pantallas plenamente formalizada y consistente entre HTML, JSON, Admin y futuras APIs.
- Alertas, métricas operativas activas y monitor integrado.
- Validación de runtime PostgreSQL, producción y disponibilidad externa durante este levantamiento.

## 13. Orden recomendado para continuar sin romper el producto

1. Acordar y testear el contrato de autorización por organización; luego aplicarlo de forma uniforme a navegación, listados, detalles, mutaciones, endpoints JSON y exports.
2. Recuperar una base PostgreSQL reproducible y correr el set CI completo antes de cambios de modelo o migración.
3. Añadir constraints sólo después de auditar datos existentes y preparar migraciones compatibles con producción.
4. Extraer por casos de uso las reglas de vistas más largas, empezando por documentos tributarios y operaciones de sesión, manteniendo las URLs/templates estables.
5. Decidir modelo de conciliación y cierre contable antes de automatizar transacciones desde pagos.
6. Mantener `monitor` archivado hasta tener evidencia de sus datos; no mezclar su reactivación con core de operación.

## 14. Archivos de orientación para el siguiente agente

- Arquitectura: `docs/arquitectura/PLATAFORMA.md`, `MODELO_DATOS.md`, `NAVEGACION_Y_CONTEXTO.md`, `PERMISOS_Y_ROLES.md`, `DEUDA_TECNICA.md`.
- Dominios: `docs/apps/ASISTENCIAS.md`, `PERSONAS.md`, `FINANZAS.md`, `API.md`, `AUDITORIA.md`, `MONITOR.md`.
- Reglas ejecutables: `personas/permissions.py`, `plataformaelemental/context.py`, `finanzas/services/imputacion.py`, `finanzas/signals.py`.
- Flujos críticos: `asistencias/views.py`, `personas/views.py`, `finanzas/views.py`, `finanzas/forms.py`, `finanzas/documentos/`.
- Contratos externos: `plataformaelemental/urls.py`, `<app>/urls.py`, `api/views.py`.
- Verificación: `asistencias/tests.py`, `personas/tests.py`, `finanzas/tests.py`, `api/tests.py`, `auditoria/tests.py`, `plataformaelemental/tests.py`.
- Operación: `.github/workflows/deploy.yml`, `scripts/deploy.sh`, `docs/operacion/DEPLOY.md`.

---

Estado final del levantamiento: **aplicación funcional amplia, con arquitectura modular adecuada para su tamaño actual; requiere endurecimiento de permisos multi-organización, verificación PostgreSQL y reducción gradual de lógica en views antes de expandir dominios o exponer datos por API.**

# PLATAFORMA - Estado tecnico actual

## 1. Objetivo
Este documento resume el estado actual de la plataforma administrativa de Espacio Elementos sobre Django.

Incluye:
- arquitectura vigente
- apps y responsabilidades
- rutas HTML activas
- flujos funcionales principales
- integracion financiera
- estado de pruebas y observaciones tecnicas

Fecha de actualizacion: 2026-03-14

## 2. Resumen ejecutivo
La plataforma opera hoy como un monolito Django modular con tres apps funcionales visibles:
- `asistencias`
- `personas`
- `finanzas`

Adicionalmente existen:
- `database` como fuente unica de modelos
- `api` para exponer endpoints REST
- `plataformaelemental` como configuracion del proyecto

La navegacion principal entre apps mantiene filtros globales de:
- `periodo_mes`
- `periodo_anio`
- `organizacion`

La gestion de organizaciones ya no vive en `asistencias`; fue movida a `personas`, donde ahora existe listado, detalle, creacion y edicion.

## 3. Arquitectura vigente
- Framework: Django 5
- API: Django REST Framework
- Base de datos: SQLite local
- UI: Bootstrap 5 + DataTables + Tom Select (via CDN)
- Zona horaria: `America/Santiago`
- Idioma base: `es-cl`
- Estilo de desarrollo: codigo mayoritariamente en espanol

### 3.1 Estructura funcional
- `database/`: todos los modelos del dominio
- `asistencias/`: operacion academica, sesiones, asistencias, vistas operativas
- `personas/`: CRM de personas, roles, organizaciones y perfil ampliado
- `finanzas/`: pagos, planes, documentos tributarios, categorias, transacciones y reportes
- `api/`: endpoints para consumo externo

### 3.2 Modelos principales
Modelos relevantes actualmente presentes en `database`:
- `Organizacion`
- `Persona`
- `Rol`
- `PersonaRol`
- `Disciplina`
- `BloqueHorario`
- `SesionClase`
- `Asistencia`
- `PaymentPlan`
- `Payment`
- `AttendanceConsumption`
- `DocumentoTributario`
- `Category`
- `Transaction`

## 4. Navegacion y filtros globales
Las tres apps HTML comparten una barra superior de cambio de app y una barra de filtros.

Regla vigente:
- el `mes`, `anio` y `organizacion` seleccionados deben arrastrarse en toda la navegacion interna

Esto hoy aplica a:
- menus superiores
- links entre apps
- detalles y listados
- botones volver/cancelar
- redirects posteriores a POST en vistas principales

## 5. Apps web y rutas activas

### 5.1 Asistencias (`/asistencias/`)
Responsabilidad:
- operacion academica diaria
- sesiones y asistencia
- panel operativo para estudiantes y profesores

Rutas principales:
- `/asistencias/` dashboard operativo
- `/asistencias/sesiones/` calendario mensual de sesiones
- `/asistencias/sesiones/<id>/` detalle de sesion
- `/asistencias/asistencias/` pantalla operativa de sesiones y registro masivo
- `/asistencias/personas/<id>/` perfil operativo de estudiante/profesor
- `/asistencias/estudiantes/` listado de estudiantes
- `/asistencias/profesores/` listado de profesores
- `/asistencias/disciplinas/` resumen de disciplinas
- `/asistencias/disciplinas/nueva/` crear disciplina
- `/asistencias/disciplinas/<id>/` detalle de disciplina
- `/asistencias/disciplinas/<id>/editar/` editar disciplina

Capacidades relevantes:
- crear sesiones desde la vista de asistencias
- alta rapida de persona desde la operacion diaria
- agregar asistentes en bloque
- cambiar estado de sesion
- ver estado financiero del estudiante en su perfil operativo
- asociar asistencias a pagos existentes desde `asistencias/personas/<id>/`
- colorear asistentes segun estado financiero en el listado de sesiones:
  - amarillo: deuda
  - verde: pagada
  - azul: liberada/sin cobro

### 5.2 Personas (`/personas/`)
Responsabilidad:
- CRM de personas
- roles y organizaciones
- vista transversal de actividad academica y financiera
- administracion de organizaciones

Rutas principales:
- `/personas/` dashboard CRM
- `/personas/listado/` listado de personas
- `/personas/nuevo/` crear persona
- `/personas/<id>/` detalle CRM de persona
- `/personas/<id>/editar/` editar persona
- `/personas/organizaciones/` listado de organizaciones
- `/personas/organizaciones/nueva/` crear organizacion
- `/personas/organizaciones/<id>/` detalle de organizacion
- `/personas/organizaciones/<id>/editar/` editar organizacion

Capacidades relevantes:
- resumen por persona del periodo filtrado
- gestion de roles por organizacion
- vista financiera integrada por pagos y consumos
- vista de sesiones como profesor
- listado de organizaciones con metadatos y metricas
- detalle de organizacion con informacion relevante:
  - personas activas
  - estudiantes y profesores activos
  - disciplinas
  - sesiones del periodo
  - pagos e ingresos del periodo

### 5.3 Finanzas (`/finanzas/`)
Responsabilidad:
- gestion de pagos y sus consumos de clases
- documentos tributarios
- categorias y transacciones
- reportes financieros basicos

Rutas principales:
- `/finanzas/` dashboard financiero
- `/finanzas/pagos/`
- `/finanzas/pagos/<id>/`
- `/finanzas/pagos/<id>/editar/`
- `/finanzas/pagos/<id>/eliminar/`
- `/finanzas/planes/`
- `/finanzas/planes/<id>/editar/`
- `/finanzas/planes/<id>/eliminar/`
- `/finanzas/documentos-tributarios/`
- `/finanzas/documentos-tributarios/importar/`
- `/finanzas/documentos-tributarios/<id>/`
- `/finanzas/documentos-tributarios/<id>/archivo/<tipo>/`
- `/finanzas/documentos-tributarios/<id>/editar/`
- `/finanzas/documentos-tributarios/<id>/eliminar/`
- `/finanzas/categorias/`
- `/finanzas/categorias/<id>/editar/`
- `/finanzas/categorias/<id>/eliminar/`
- `/finanzas/transacciones/`
- `/finanzas/transacciones/<id>/`
- `/finanzas/transacciones/<id>/archivo/`
- `/finanzas/transacciones/<id>/editar/`
- `/finanzas/transacciones/<id>/eliminar/`
- `/finanzas/reportes/categorias/`

Capacidades relevantes:
- resumen superior en pagos con:
  - total pagos
  - total clases pagadas
  - saldo
- filtro de planes por organizacion en el formulario de registrar pago
- validacion backend para impedir asociar un plan de otra organizacion
- validacion backend para impedir asociar un documento tributario de otra organizacion a un pago
- detalle de pago con consumos imputados y documento tributario asociado
- listado de documentos tributarios separados de las transacciones
- documentos tributarios con PDF/XML, tasas de IVA y retencion, fuente y relacion entre documentos
- carga asistida de documentos tributarios con parseo XML-first y revision manual antes de guardar
- detalle de transaccion con visor PDF embebido
- transacciones con asociaciones manuales a documentos tributarios
- ruta dedicada para archivo de transaccion con `X-Frame-Options: SAMEORIGIN`

## 6. Integracion academica-financiera
La plataforma ya integra asistencia con pago de clases.

Flujo actual:
1. Se registra una asistencia.
2. Se crea o actualiza `AttendanceConsumption`.
3. Si existe pago disponible del estudiante en la misma organizacion, la asistencia se consume.
4. Si no existe saldo disponible, queda como deuda.
5. Si luego se crea un pago, este puede imputar deudas previas.

Estado operativo visible:
- en `asistencias/personas/<id>/` se ve el resumen del estudiante acotado al filtro vigente
- en `asistencias/personas/<id>/` se puede reasociar una asistencia a un pago existente
- en `asistencias/asistencias/` los asistentes se distinguen visualmente por estado financiero

## 7. API REST
Autenticacion disponible:
- session authentication
- token authentication

Endpoints activos documentados en el repo:
- `/api/health/`
- `/api/auth/login/`
- `/api/auth/refresh/`
- `/api/auth/logout/`
- `/api/sesiones/`
- `/api/sesiones/<id>/asistencias/`
- `/api/estudiantes/`
- `/api/estudiantes/<id>/estado/`
- `/api/reportes/resumen/`

## 8. Acceso y seguridad
- login: `/accounts/login/`
- raiz `/` redirige a `/asistencias/`
- `/app/` redirige a `/asistencias/`
- las vistas HTML usan control de acceso por autenticacion y roles
- `role_required(...)` considera valido:
  - superuser
  - `is_staff`
  - o rol activo compatible segun `PersonaRol`

## 9. Estado reciente validado
Validaciones ejecutadas durante la actualizacion documental:
- `python manage.py test asistencias.tests personas.tests finanzas.tests`
- resultado: `29 tests OK`

Tambien quedaron validados recientemente flujos puntuales de:
- filtros y querystring entre apps
- colores financieros en asistentes
- resumen de pagos
- visor PDF de transacciones
- gestion de organizaciones en `personas`

## 10. Observaciones tecnicas vigentes
- Sigue existiendo logica de negocio relevante en views; no toda esta encapsulada en servicios.
- El proyecto sigue en SQLite local para desarrollo.
- La UI depende de CDN para varios componentes.
- La documentacion historica del repo puede haber quedado atrasada en otros archivos si no se actualiza en paralelo.

## 11. Conclusiones
La plataforma hoy ya no es solo un panel de asistencias; funciona como una base administrativa integrada para:
- operacion academica
- CRM de personas
- finanzas y trazabilidad de pagos
- administracion de organizaciones

El estado funcional actual es consistente con una operacion interna real y con filtros globales compartidos entre apps.

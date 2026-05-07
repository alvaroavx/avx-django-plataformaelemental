# PLATAFORMA

Fecha de actualizacion: 2026-05-07

## Proposito
Este documento resume el estado tecnico vigente de Plataforma Elemental.

Sirve para:
- entender la arquitectura actual
- ubicar responsabilidades por app
- recordar reglas transversales de navegacion
- tener una foto razonablemente actual del sistema

## Resumen ejecutivo
La plataforma opera hoy como un monolito Django modular con cuatro apps funcionales visibles:
- `asistencias`
- `personas`
- `finanzas`
- `monitor`

Adicionalmente existen:
- `database` como namespace legado de migraciones y compatibilidad historica
- `api` para endpoints REST y consumo externo
- `plataformaelemental` para configuracion del proyecto

## Reglas transversales
- Los filtros globales `periodo_mes`, `periodo_anio` y `organizacion` deben mantenerse en toda la navegacion.
- Si no existe filtro explicito en la URL, `periodo_mes` y `periodo_anio` deben partir en la fecha actual; `organizacion` debe partir en `Todas`.
- Los filtros globales deben autoaplicarse al cambiar un selector; no usan boton `Aplicar filtros`.
- `periodo_mes` y `periodo_anio` aceptan `Todos`, por lo que el sistema debe soportar filtros parciales como `todos los meses de un año`, `un mismo mes en todos los años` o `todo el historial`.
- La barra compartida de apps debe mantener enlaces a `asistencias`, `finanzas`, `personas` y `monitor`, arrastrando los filtros globales activos.
- El contexto global de UI, periodo y organizacion activa vive en `plataformaelemental.context`; ninguna app debe importar helpers desde `asistencias.views`.
- Los modelos del dominio viven en su app duena:
  - `personas`: personas, roles y organizaciones
  - `asistencias`: disciplinas, sesiones y asistencias
  - `finanzas`: pagos, documentos tributarios, consumos y transacciones
- `database` se mantiene solo para conservar compatibilidad historica de migraciones y no debe recibir modelos nuevos.
- El codigo debe mantenerse en espanol siempre que no complique artificialmente la comprension.
- La plataforma debe funcionar aunque no existan documentos tributarios; estos son opcionales y no la fuente obligatoria de verdad del sistema.

## Arquitectura vigente
- Framework: Django 5
- API: Django REST Framework
- Base de datos: PostgreSQL activa por entorno en `plataformaelemental/config/dev.py` y `plataformaelemental/config/prod.py`
- UI: Bootstrap 5, DataTables y Tom Select via CDN
- Zona horaria: `America/Santiago`
- Despliegue minimo versionado: GitHub Actions + SSH + `systemd` + `gunicorn`

## Base de datos
- `plataformaelemental/config/base.py` no declara `DATABASES`; solo mantiene defaults comunes y helpers de entorno.
- `plataformaelemental/config/dev.py` declara PostgreSQL activo usando exclusivamente variables `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST` y `POSTGRES_PORT`.
- `plataformaelemental/config/prod.py` declara PostgreSQL activo usando las mismas variables `POSTGRES_*`; en produccion todas son obligatorias y deben venir desde el archivo de entorno del servidor.
- Ambos archivos dejan SQLite comentado como fallback local/manual, no como base activa.
- Desarrollo local usa como referencia `POSTGRES_DB=plataforma_elemental_dev`, `POSTGRES_USER=elementos`, `POSTGRES_HOST=127.0.0.1` y `POSTGRES_PORT=5432`; la clave queda en `POSTGRES_PASSWORD`.
- `requirements.txt` mantiene `psycopg[binary]==3.2.9` como driver PostgreSQL.
- La suite `api.tests` incluye pruebas transversales de PostgreSQL que validan backend activo, tablas migradas, relaciones entre apps, constraints unicos y reglas de cascada/SET_NULL sobre modelos de `personas`, `asistencias`, `finanzas`, `api` y `monitor`.

## Apps

### `asistencias`
Responsabilidad:
- operacion academica diaria
- sesiones y registro de asistencia
- enlaces operativos hacia perfiles consolidados en `personas`
- exponer una base externa de lectura y carga de asistencia via API

Rutas principales:
- `/asistencias/`
- `/asistencias/sesiones/`
- `/asistencias/sesiones/<id>/`
- `/asistencias/asistencias/`
- `/asistencias/estudiantes/`
- `/asistencias/profesores/`
- `/asistencias/disciplinas/`

### `personas`
Responsabilidad:
- CRM transversal
- personas, roles y organizaciones
- vista administrativa consolidada por persona y por organizacion
- exponer personas y organizaciones para consumo externo

Reglas vigentes:
- `Persona.rut` es opcional y se valida como RUT chileno.
- El RUT de personas se administra desde la app `personas`; los flujos rapidos de otras apps no lo editan.

Rutas principales:
- `/personas/`
- `/personas/listado/`
- `/personas/nuevo/`
- `/personas/<id>/`
- `/personas/<id>/editar/`
- `/personas/organizaciones/`
- `/personas/organizaciones/nueva/`
- `/personas/organizaciones/<id>/`
- `/personas/organizaciones/<id>/editar/`

### `finanzas`
Responsabilidad:
- pagos academicos
- documentos tributarios
- transacciones de caja
- categorias, planes y reportes
- exponer resumentes y listados financieros base para consumo externo

Rutas principales:
- `/finanzas/`
- `/finanzas/pagos/`
- `/finanzas/planes/`
- `/finanzas/documentos-tributarios/`
- `/finanzas/documentos-tributarios/importar/`
- `/finanzas/transacciones/`
- `/finanzas/categorias/`
- `/finanzas/reportes/categorias/`

### `api`
Responsabilidad:
- exponer una API REST externa y versionada
- servir una base reutilizable para futuras apps moviles e integraciones
- controlar autenticacion de API key de lectura y rate limiting

Rutas principales:
- `/api/health/`
- `/api/me/`
- `/api/auth/login/`
- `/api/auth/refresh/`
- `/api/auth/logout/`
- `/api/v1/personas/...`
- `/api/v1/asistencias/...`
- `/api/v1/finanzas/...`

Reglas vigentes:
- La API versionada base vive en `/api/v1/`.
- Las consultas `GET` aceptan usuario autenticado o API key valida.
- Las escrituras requieren usuario autenticado.
- La API key es solo de lectura.
- La API aplica throttling por usuario, API key o IP.

### `monitor`
Responsabilidad:
- agrupar vistas internas de monitoreo operativo
- servir como punto inicial para futuros indicadores transversales

Rutas principales:
- `/monitor/`

Reglas vigentes:
- La pantalla inicial requiere usuario autenticado.
- La app no define modelos propios en su creacion inicial.

## Modelo financiero actual
- `Payment`: cobro academico a estudiante.
- `Transaction`: movimiento real de caja, banco o tarjeta.
- `DocumentoTributario`: documento fiscal opcional que puede ayudar a precargar informacion o respaldar operaciones, pero no es obligatorio para usar el sistema.

Regla vigente:
- `Payment`, `Transaction` y `DocumentoTributario` son entidades separadas.
- Pueden asociarse entre si, pero no deben colapsarse en una sola entidad.
- En resumentes de `documentos tributarios`, un documento cuenta como `ingreso` si la organizacion asociada es la emisora y como `egreso` si la organizacion asociada es la receptora.
- `DocumentoTributario` puede asociar opcionalmente una contraparte interna del sistema como `Persona` o `Organizacion`, usando sugerencia por RUT cuando el dato exista.

## Integracion academica-financiera
- Las asistencias presentes pueden consumirse contra pagos existentes.
- Si no hay saldo disponible, la asistencia queda como deuda.
- Luego un pago puede imputar deudas previas.
- El estado financiero del estudiante es visible desde `asistencias`.

Regla vigente:
- una asistencia solo puede consumir clases pagadas del mismo mes y anio
- las clases no se arrastran entre meses
- la configuracion operativa de profesor vive en `personas.PersonaRol` para el rol `PROFESOR`, porque depende de persona + organizacion; hoy incluye `valor_clase` y `retencion_sii`, y el perfil de profesor usa esos datos para desglosar `pago bruto`, `retencion SII` y `monto neto` del periodo

## Carga asistida tributaria
Estado actual:
- flujo XML-first
- soporte inicial para DTE XML clasico
- soporte inicial para boleta de honorarios XML
- PDF fallback basico
- fallback PDF mejorado para boletas de honorarios electronicas
- fallback PDF mejorado tambien para boletas de venta electronicas tipo 39 y 41 con glosa libre, medio de pago y total extraible desde PDF
- fallback PDF con `pdftotext` del sistema cuando no hay parser Python disponible
- parseo y revision antes del guardado
- la revision muestra visor inline del archivo temporal para comparar PDF/XML con los campos precargados

Regla vigente:
- subir un archivo no debe guardar automaticamente registros definitivos
- la carga asistida expone un solo input de archivo y detecta internamente si el archivo subido es XML o PDF
- el flujo debe ser:
  - subir
  - extraer
  - revisar
  - confirmar
- la unicidad de documentos tributarios debe considerar al emisor; dentro de una organizacion, el criterio vigente es `tipo_documento + folio + rut_emisor`
- el fallback PDF requiere texto seleccionable; un PDF escaneado sin OCR no se puede parsear de forma confiable
- en montos tributarios, valores como `500.000` deben interpretarse como `500000` sin decimales en la carga asistida

## Seguridad y acceso
- `/` redirige a `/asistencias/`
- `/app/` redirige a `/asistencias/`
- login en `/accounts/login/`
- las vistas HTML operan con autenticacion y roles
- la API externa base usa token de DRF para usuarios y API key de solo lectura para consultas
- la API tiene rate limiting por usuario, API key o IP, y un throttling mas estricto para login
- la API key puede enviarse por `X-API-Key` o por `Authorization: ApiKey <clave>`
- En produccion, las sesiones expiran por inactividad en 2 horas por defecto (`SESSION_COOKIE_AGE=7200`) y se renuevan solo con actividad (`SESSION_SAVE_EVERY_REQUEST=True`).
- En produccion, la cookie de sesion se llama `elemental_sessionid`; esto invalida cookies historicas `sessionid` despues del deploy.
- En produccion, `SESSION_COOKIE_SECURE=True`, `CSRF_COOKIE_SECURE=True`, `SECURE_SSL_REDIRECT=True` y HSTS inicia con `SECURE_HSTS_SECONDS=3600`.
- La guia operativa de seguridad vive en `docs/operacion/SEGURIDAD_PRODUCCION.md`.

## Deploy
- Dominio publico vigente: `apps.avx.cl`.
- En produccion, `plataformaelemental/config/prod.py` garantiza `apps.avx.cl` en `ALLOWED_HOSTS` y `https://apps.avx.cl` en `CSRF_TRUSTED_ORIGINS`, incluso si el archivo de entorno no los declara explicitamente.
- El flujo minimo de CI/CD corre en GitHub Actions al hacer push a `main`.
- La estrategia vigente es:
  - tests en GitHub Actions
  - conexion SSH al servidor
  - `git reset --hard origin/main`
  - `scripts/deploy.sh`
  - reinicio de `systemd`
- La guia operativa vive en `docs/operacion/DEPLOY.md`.

## Estado reciente validado
Ultima validacion conocida:
- `python manage.py test asistencias.tests personas.tests finanzas.tests api.tests`
- resultado: `99 tests OK`

## Observaciones tecnicas
- Sigue existiendo logica de negocio importante en views; no toda esta encapsulada en servicios.
- La documentacion viva del repo vive en `docs/`, con un indice central y documentos por app en `docs/apps/`.
- Si una decision cambia comportamiento o modelo, debe actualizarse la documentacion en el mismo cambio.

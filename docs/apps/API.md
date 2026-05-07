# API

Fecha de actualizacion: 2026-05-04

## Proposito
La app `api` expone una capa externa consumible por clientes fuera del frontend Django, incluyendo una base para futuras apps moviles de profesores.

## Criterio actual
- Se expone una version base y conservadora.
- Solo se incluye lo que ya es claro en el dominio actual.
- Todo lo que todavia tenga ambiguedad funcional queda fuera por ahora.

## Referencias base
Este diseno se apoya en documentacion oficial de Django y DRF:
- Django auth: https://docs.djangoproject.com/en/5.2/topics/auth/default/
- Django auth customization: https://docs.djangoproject.com/en/5.2/topics/auth/customizing/
- Django security: https://docs.djangoproject.com/en/5.2/topics/security/
- Django deployment checklist: https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/
- DRF throttling: https://www.django-rest-framework.org/api-guide/throttling/

## Reglas vigentes
- La API publica base vive bajo `/api/v1/`.
- Las consultas `GET` pueden autenticarse con API key o con usuario autenticado.
- Las escrituras requieren usuario autenticado; la API key actual es solo de lectura.
- La autenticacion actual para usuarios externos sigue siendo token de DRF.
- La API key se acepta por `X-API-Key` o por `Authorization: ApiKey <clave>`.
- Existe rate limiting para toda la API y un rate limiting mas estricto para login.

## Superficie minima expuesta

### Personas
- `/api/v1/personas/organizaciones/`
- `/api/v1/personas/personas/`
- `/api/v1/personas/resumen/`

### Asistencias
- `/api/v1/asistencias/disciplinas/`
- `/api/v1/asistencias/sesiones/`
- `/api/v1/asistencias/sesiones/<id>/asistencias/`
- `/api/v1/asistencias/asistencias/`
- `/api/v1/asistencias/resumen/`

### Finanzas
- `/api/v1/finanzas/planes/`
- `/api/v1/finanzas/pagos/`
- `/api/v1/finanzas/documentos-tributarios/`
- `/api/v1/finanzas/transacciones/`
- `/api/v1/finanzas/resumen/`

### Identidad y salud
- `/api/health/`
- `/api/me/`
- `/api/auth/login/`
- `/api/auth/refresh/`
- `/api/auth/logout/`

## Filtros y forma de uso
- Los endpoints base privilegian filtros simples por querystring.
- Donde aplica, la API soporta `organizacion`, `periodo_mes` y `periodo_anio`.
- Otros filtros base ya expuestos incluyen `persona`, `disciplina`, `profesor`, `tipo`, `tipo_documento`, `fecha` y `estado`, segun el endpoint.

Ejemplos:
- `GET /api/v1/asistencias/sesiones/?organizacion=1&periodo_mes=4&periodo_anio=2026`
- `GET /api/v1/finanzas/pagos/?organizacion=1&periodo_mes=4&periodo_anio=2026`
- `GET /api/v1/personas/personas/?organizacion=1&rol=PROFESOR`

## Decisiones explicitas
- No se implementa aun una API de "sueldo docente" porque la regla de negocio no esta formalizada.
- No se expone aun una API movil especializada por profesor; la base actual es general y reusable.
- No se implementa aun OAuth2/OIDC; por ahora se usa token de DRF mas API key de lectura.
- La API key sirve para integraciones y consultas externas, no para mutaciones.

## Operacion
- Las API keys se crean por management command: `python manage.py crear_api_key <nombre>`.
- La clave plana se muestra una sola vez al momento de crearla.
- En base de datos se guarda solo hash de la clave.
- Los endpoints de lectura aceptan:
  - header `X-API-Key: <clave>`
  - header `Authorization: ApiKey <clave>`
- Los endpoints de escritura deben seguir usando usuario autenticado por token DRF.

## Pruebas De Base De Datos
- `api.tests` contiene el set transversal de validacion PostgreSQL porque este modulo ya forma parte del comando principal de tests.
- Estas pruebas validan que la conexion default use PostgreSQL, que existan las tablas migradas de todas las apps funcionales y que las relaciones, constraints unicos, JSONField, DecimalField, many-to-many, one-to-one, cascadas y `SET_NULL` funcionen sobre la base real.

## Seguridad actual
- `ApiKeyAuthentication` para lectura externa.
- Permiso global `ApiKeyLecturaOUsuarioAutenticado`.
- Throttles por usuario, API key o IP:
  - `api_burst`
  - `api_sustained`
  - `auth_burst`
  - `auth_sustained`

## Siguiente recomendacion
- Si la app movil pasa a produccion publica, la mejora recomendada es migrar el login movil a OAuth2/OIDC con PKCE y mantener la API key solo para integraciones servidor a servidor o dashboards externos.

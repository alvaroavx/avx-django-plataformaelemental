# Evidencia: búsqueda transversal de personas

Fecha: 2026-08-10

## Objetivo

Comprobar que las cajas que buscan alumnos, profesores, asistentes y personas
encuentran nombres completos por fragmentos aunque el texto almacenado tenga
tildes, sin alterar el aislamiento por organización o clase.

## Cobertura implementada

| Superficie | Campos buscables | Alcance aplicado antes de buscar |
| --- | --- | --- |
| Candidatos de solicitud de acceso | username, nombre, apellido, correo | permiso de gestión y candidatos activos |
| Listado CRM de personas | nombre, apellido, correo, teléfono, RUT | organización visible |
| Asistentes de una sesión | nombre, apellido, correo, RUT | sesión autorizada y roster permitido |
| Pago masivo de profesor | nombre, apellido, correo, RUT | clases asignadas al profesor |
| Listado de pagos | nombre, apellido, correo, RUT | permisos, organización y período |
| Pago masivo administrativo | nombre, apellido, correo, RUT | organización autorizada |
| Filtros locales de estudiantes/profesores | texto visible | solo filas/opciones ya renderizadas y autorizadas |

## Validación

Entorno: PostgreSQL 18.4 local por socket Unix, base aislada de pruebas Django.
El clúster reproducible se conserva durante esta sesión en
`/tmp/elemental-search-pg18-20260810`; no contiene datos productivos. El proceso
se detuvo al terminar las pruebas, pero el directorio y su log no se eliminaron.

Resultados:

- `python manage.py check`: sin observaciones.
- 100 pruebas focalizadas de Personas, Operación Profesor, acceso financiero y
  pago masivo: **OK**.
- 6 pruebas del flujo original de resolución de solicitudes: **OK**.
- `python manage.py makemigrations --check --dry-run`: `No changes detected`.
- `ruff check` focalizado, `compileall`, sintaxis JavaScript, enlaces Markdown y
  `git diff --check`: **OK**.
- Casos nuevos confirmados: `alvaro vargas` / `Álvaro José Várgas Peña`,
  `angela nunez` / `Ángela María Núñez Peña`, `barbara munoz` /
  `Bárbara Inés Muñoz Cáceres` y `matias perez` /
  `Matías Andrés Pérez Muñoz`.

## Incidencia de entorno conservada

El primer intento alcanzó `manage.py check`, pero PostgreSQL configurado en
`127.0.0.1:5432` no estaba disponible y las pruebas terminaron antes de ejecutar
casos con `django.db.utils.OperationalError: connection is bad`. Se levantó el
clúster local anterior y la repetición final quedó verde. Este fallo inicial no
corresponde a una regresión del código.

## Datos y migraciones

La corrección no cambia modelos, no agrega migraciones y no escribe datos en la
base de desarrollo. Las pruebas usan la base `test_plataforma_elemental_busqueda`
creada por Django.

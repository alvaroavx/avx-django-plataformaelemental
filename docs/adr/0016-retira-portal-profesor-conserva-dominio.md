# ADR 0016: Retirar el portal dedicado de profesores y conservar el dominio

Fecha: 2026-10-08
Estado: Aceptada
Decisor: Álvaro

## Contexto

La interfaz dedicada bajo `/profesor/` no se utilizará. La aplicación Elemental
seguirá usando profesores como parte central de la operación de clases y
asistencias, pero no se construirá ahora una interfaz alternativa para ellos.

## Decisión

- Retirar las rutas, vistas, formularios, templates, estilos y pruebas exclusivas
  del portal de profesores.
- Eliminar accesos y modos de navegación que daban a perfiles profesor una
  experiencia distinta de la aplicación común.
- Conservar el rol y perfil `PROFESOR`, las asignaciones a disciplinas y sesiones,
  su administración desde Asistencias/Personas, y los cálculos/exportaciones
  financieras que usan esos datos.
- No eliminar ni transformar datos, modelos, tablas ni migraciones. No crear por
  ahora una nueva experiencia para profesores.
- Mantener smoke público de portada/login, retirando la validación que requería
  una cuenta operativa del portal.

## Consecuencias

- `/profesor/` deja de estar disponible.
- Usuarios con rol profesor conservan su perfil y aparecen en los flujos
  administrativos pertinentes; el rol por sí solo ya no autoriza el modo de
  edición o lectura de sesiones que existía para el portal.
- No se requiere migración de base de datos y no se borran relaciones históricas.
- Los E2E y evidencias históricos del portal se conservan como archivo, pero no
  describen una capacidad vigente ni deben usarse como gate de aceptación.

## Revisión

No se fija fecha para crear un reemplazo. Cualquier futura interfaz debe ser una
decisión y alcance nuevos, conservando el contrato del dominio documentado en
Asistencias y Personas.

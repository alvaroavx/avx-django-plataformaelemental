# ADR-0019: asistencia propia del Profesor

- Estado: aceptada
- Fecha: 2026-10-12
- Decisor: Álvaro

## Contexto

El Profesor ya puede consultar su calendario. Para operar una clase necesita abrir su sesión y registrar quién asistió, sin recibir por ello permisos administrativos sobre sesiones, personas o finanzas.

## Decisión

Se incorpora la capacidad configurable `agregar_asistentes_propios`, presentada como “Gestionar asistencia de mis sesiones”. Está habilitada por defecto por organización para el rol Profesor y permite:

- abrir únicamente sesiones donde la persona está asignada como profesor;
- buscar alumnos activos y vinculados operativamente a la disciplina;
- agregar esos alumnos como asistentes, sin duplicarlos.

No permite crear personas, editar o eliminar la sesión, cambiar su estado manualmente, quitar asistentes, corregir estados de asistencia, liberar clases ni consultar datos financieros. El servidor valida asignación, organización y capacidad en las vistas HTML y endpoints JSON; la visibilidad de botones no sustituye esta autorización.

## Alternativas descartadas

- Reutilizar “Administrar sesiones”: concedería operaciones y datos fuera del objetivo.
- Entregar toda la edición de asistencia: agregar, corregir, quitar y liberar tienen riesgos diferentes.
- Mostrar cualquier alumno de la organización: el Profesor sólo buscará alumnos vinculados a la disciplina.

## Consecuencias

Calendario y gestión de asistencia propia pueden activarse por separado. Las correcciones o ampliaciones futuras deben incorporarse como capacidades explícitas y no ensanchar silenciosamente este permiso.

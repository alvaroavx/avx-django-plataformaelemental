# ADR-0018: permisos de producto por rol y organización

- Estado: aceptada
- Fecha: 2026-10-12
- Decisor: Álvaro

## Contexto

Django ofrece permisos CRUD por modelo, pero esa granularidad no expresa bien acciones del negocio como “ver solamente mi calendario”. Elemental ya autoriza principalmente mediante capacidades de dominio, roles activos y organización seleccionada.

## Decisión

La administración mostrará capacidades de producto con nombres comprensibles. Las excepciones configurables se persistirán por organización, rol y capacidad; los permisos internos de Django seguirán siendo un detalle técnico.

La primera capacidad configurable es `ver_calendario` para Profesor. Está habilitada por defecto para preservar una incorporación simple y el administrador de cada organización puede deshabilitarla. Al usarla, el profesor:

- ve únicamente sesiones donde está asignado como profesor;
- no crea sesiones ni sesiones masivas;
- no abre todavía el detalle operativo de asistencia;
- no obtiene por implicación permisos sobre personas, finanzas o configuración.

La sección Configuración → Permisos sólo puede ser operada por un administrador autorizado para la organización. Los cambios quedan auditados.

## Alternativas descartadas

- Exponer la tabla completa de permisos Django: demasiado técnica y no representa alcance por organización.
- Codificar permanentemente el acceso del profesor: no permite que Álvaro controle la activación.
- Configurar permisos por cada persona: agrega complejidad prematura; la unidad inicial es rol más organización.

## Consecuencias

Cada nueva capacidad debe definir alcance de datos, operaciones de lectura y escritura y valor por defecto. Ocultar botones nunca sustituye la autorización del servidor. La autorización individual sólo se reconsiderará si aparecen excepciones reales que no puedan expresarse con roles.

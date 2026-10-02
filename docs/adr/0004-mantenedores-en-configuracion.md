# D-004: Los mantenedores viven en Configuración al final del menú

**Fecha:** 2026-10-02 | **Decidió:** Álvaro | **Estado:** vigente

## Contexto

El menú lateral mezclaba trabajo operativo frecuente con catálogos y superficies
que cambian rara vez. Esa mezcla alargaba cada dominio y daba el mismo peso a
Sesiones o Pagos que a Disciplinas, Planes y Categorías.

## Alternativas descartadas

- Mantener cada catálogo dentro de su dominio — conserva la clasificación técnica, pero no prioriza la frecuencia real de uso.
- Llamar al grupo `Mantenedores` — es jerga de desarrollo y no expresa claramente la intención para una persona operadora.
- Llamar Django Admin `Mantenedor de data` — mezcla idiomas, reduce su alcance real y no advierte que es una superficie sensible.

## Decisión

El último grupo del menú se llama `Configuración` y reúne Disciplinas, Planes,
Categorías, Organizaciones, Solicitudes de acceso y el Django Admin, presentado
como `Administración avanzada`.

## Consecuencias asumidas

- Los dominios Sesiones, Finanzas y Personas conservan sus tareas frecuentes y dejan de repetir estos mantenedores.
- Configuración muestra únicamente accesos ya autorizados para cada usuario; no amplía permisos.
- Administración avanzada continúa enlazando `/admin/` y permanece limitada a staff o superusuarios.
- En el rail contraído, Configuración usa un único acceso y mantiene los badges autorizados de sus hijos.

## Condiciones de revisión

Revisar si alguno de estos catálogos se convierte en una tarea operacional de
alta frecuencia o si aparece una configuración por organización que requiera un
flujo propio y menos privilegiado que Django Admin.

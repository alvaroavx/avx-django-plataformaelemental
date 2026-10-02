# D-005: La portada existente es el Panel transversal por capacidades

**Fecha:** 2026-10-02 | **Decidió:** Álvaro | **Estado:** vigente

## Contexto

La portada `Resumen de operación` ya concentraba los KPI principales, la jornada
y acciones del período, mientras Personas mantenía otro Panel de uso secundario.
La duplicación dispersaba la entrada al sistema y separaba cifras de personas de
la consulta que les da utilidad.

## Alternativas descartadas

- Crear un Panel nuevo — duplicaría rutas y composición; la instrucción explícita es evolucionar la portada existente.
- Conservar el Panel de Personas — mantiene métricas repetidas y un paso adicional antes del listado.
- Mostrar el mismo contenido a todos los roles — expondría agregados administrativos a profesoras sin esas capacidades.
- Mantener `Resumen de operación` — describe solo una parte de una portada que será el inicio común del producto.

## Decisión

La ruta existente `/` se llama `Panel`, conserva una composición condicionada
por permisos y recibe el resumen de Personas junto a su consulta. El Panel propio
de Personas se elimina de la interfaz y su ruta histórica redirige al listado.

## Consecuencias asumidas

- No se crea una página ni ruta de Panel adicional.
- Administradores de Personas ven total registrado y conteos de estudiantes y profesores con roles activos; los roles pueden superponerse.
- Profesoras puras entran a `/` y ven solo su jornada asignada y el acceso a sus clases; la app Profesor no se elimina en esta etapa.
- `Próximas sesiones del período` se retira de la interfaz y del cálculo porque el calendario ya resuelve esa consulta.
- Personas enlaza directamente a su listado y `/personas/` conserva compatibilidad mediante redirección autorizada.

## Condiciones de revisión

Revisar cuando se decida retirar la app Profesor, cuando cambie la semántica de
persona registrada o rol activo, o si el Panel necesita personalización más allá
de la composición actual por capacidades.

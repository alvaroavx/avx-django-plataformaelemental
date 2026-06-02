# Inventario De Reglas De Negocio

Estado: pendiente de regenerar.

El inventario anterior quedo obsoleto despues del retiro de la app legacy `database` en Sprint 14B.

Regla vigente:
- Las reglas de identidad viven en `personas`.
- Las reglas de operacion academica viven en `asistencias`.
- Las reglas de cobranza operacional y finanzas viven en `finanzas`.
- Las reglas transversales deben documentarse en `docs/arquitectura/PLATAFORMA.md` o en el documento de la app duena.

Antes de tocar reglas de negocio, revisar:
- `docs/arquitectura/PLATAFORMA.md`
- `docs/arquitectura/MODELO_DATOS.md`
- `docs/apps/PERSONAS.md`
- `docs/apps/ASISTENCIAS.md`
- `docs/apps/FINANZAS.md`

TODO:
- Regenerar este inventario desde el codigo vigente.
- Referenciar archivos reales de `personas`, `asistencias`, `finanzas`, services, selectors y forms.
- No usar namespaces legacy como fuente de verdad.

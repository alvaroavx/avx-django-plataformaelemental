# Personas

Fecha de actualizacion: 2026-03-17

## Proposito
`personas` es el CRM transversal de la plataforma.

Debe concentrar:
- personas
- roles por organizacion
- organizaciones
- vista administrativa consolidada de actividad academica y financiera

## Reglas vigentes
- La administracion de organizaciones vive en esta app y no en `asistencias`.
- Los perfiles de persona deben mantener filtros globales de periodo y organizacion.
- Desde aqui se debe poder ver actividad academica y financiera relevante de cada persona dentro del periodo seleccionado.

## Decisiones funcionales vigentes
- Debe existir listado, detalle, creacion y edicion de organizaciones.
- El detalle de persona muestra pagos, consumos y documentos tributarios relacionados sin duplicar archivos.
- `personas` no reemplaza la operacion diaria de `asistencias`; cumple una funcion administrativa y transversal.

## Relacion con otras apps
- `asistencias` usa perfiles operativos y flujos rapidos.
- `finanzas` mantiene la logica de cobros, documentos y caja.
- `personas` conecta ambas vistas desde una perspectiva administrativa.

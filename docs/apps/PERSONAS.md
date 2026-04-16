# Personas

Fecha de actualizacion: 2026-04-08

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
- Si no hay filtros explicitos en la URL, el periodo global debe partir en el mes y año actuales, y la organizacion debe partir en `Todas`.
- Los filtros globales deben autoaplicarse al cambiar `mes`, `anio` u `organizacion`, sin boton `Aplicar filtros`.
- `periodo_mes` y `periodo_anio` deben aceptar `Todos` y reflejar esa seleccion tanto en los listados como en los resumentes de organizaciones y personas.
- Desde aqui se debe poder ver actividad academica y financiera relevante de cada persona dentro del periodo seleccionado.
- El `RUT` de una persona se edita solo desde `personas`, es opcional y debe validarse como RUT chileno.
- Los modelos propios de personas, roles y organizaciones viven en `personas.models`; no deben declararse en `database`.

## Decisiones funcionales vigentes
- Debe existir listado, detalle, creacion y edicion de organizaciones.
- `Persona.identificador` fue reemplazado por `Persona.rut`; el valor se normaliza y guarda formateado como RUT chileno cuando se ingresa desde formularios CRM.
- El detalle de persona muestra pagos, consumos y documentos tributarios relacionados sin duplicar archivos.
- `personas` no reemplaza la operacion diaria de `asistencias`; cumple una funcion administrativa y transversal.

## Relacion con otras apps
- `asistencias` usa perfiles operativos y flujos rapidos.
- `finanzas` mantiene la logica de cobros, documentos y caja.
- `personas` conecta ambas vistas desde una perspectiva administrativa.

## API externa base
- `personas` expone una base de consumo externo en:
  - `/api/v1/personas/organizaciones/`
  - `/api/v1/personas/personas/`
  - `/api/v1/personas/resumen/`
- La API permite filtrar y reutilizar personas y organizaciones sin acoplar clientes externos al frontend HTML.

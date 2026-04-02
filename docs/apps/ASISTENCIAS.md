# Asistencias

Fecha de actualizacion: 2026-04-01

## Proposito
`asistencias` es la capa operativa diaria de la plataforma.

Debe privilegiar:
- velocidad de registro
- claridad operativa
- visibilidad academica y financiera inmediata

## Reglas vigentes
- Los filtros globales `periodo_mes`, `periodo_anio` y `organizacion` deben arrastrarse en toda la app.
- La administracion de organizaciones no vive aqui; vive en `personas`.
- El perfil operativo de persona debe respetar siempre el periodo y la organizacion activos.
- Las asistencias deben poder verse junto con su estado financiero.
- Los modelos propios de esta app viven en `asistencias.models`; no deben declararse en `database`.

## Decisiones funcionales vigentes
- La vista de profesores muestra solo profesores con asistencias o sesiones activas en el periodo.
- El filtro local de organizacion bajo el titulo de profesores fue eliminado; se usa solo el filtro superior global.
- En detalle de sesion, el nombre del profesor enlaza a su perfil operativo dentro de `asistencias`.
- En `asistencias/personas/<id>/` se puede asociar una asistencia a un pago existente.
- En `asistencias/asistencias/`, los asistentes usan colores financieros:
  - amarillo: deuda
  - verde: pagada
  - azul: liberada o sin cobro

## Relacion con finanzas
- `asistencias` no define la verdad financiera completa.
- Solo consume el estado financiero necesario para operar.
- La logica global de pagos, documentos y caja vive en `finanzas`.
- Los consumos de clases y deudas usan modelos de `finanzas`, pero las entidades academicas base son propias de `asistencias`.

## API externa base
- `asistencias` expone una base de consumo externo en:
  - `/api/v1/asistencias/disciplinas/`
  - `/api/v1/asistencias/sesiones/`
  - `/api/v1/asistencias/sesiones/<id>/asistencias/`
  - `/api/v1/asistencias/asistencias/`
  - `/api/v1/asistencias/resumen/`
- Las consultas pueden usarse con API key de solo lectura.
- La carga de asistencias via API requiere usuario autenticado.

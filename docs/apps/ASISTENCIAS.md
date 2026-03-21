# Asistencias

Fecha de actualizacion: 2026-03-17

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

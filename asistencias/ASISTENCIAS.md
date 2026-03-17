# Asistencias

Fecha de actualizacion: 2026-03-16

## Decisiones vigentes
- Los filtros globales `periodo_mes`, `periodo_anio` y `organizacion` deben arrastrarse en toda la app.
- La vista de profesores muestra solo profesores con asistencias o sesiones activas en el periodo.
- El filtro local de organizacion bajo el titulo de profesores fue eliminado; se usa solo el filtro superior global.
- En detalle de sesion, el nombre del profesor enlaza a su perfil operativo dentro de `asistencias`.
- En `asistencias/personas/<id>/` el resumen del estudiante debe respetar el periodo y la organizacion seleccionados.
- La tabla de asistencias en el perfil operativo muestra estado financiero y permite asociar asistencias a pagos existentes.
- En `asistencias/asistencias/`, el listado de asistentes usa colores:
  - amarillo: deuda
  - verde: pagada
  - azul: liberada o sin cobro

## Criterio de uso
- `asistencias` es la capa operativa diaria.
- Debe privilegiar velocidad de registro y visibilidad del estado academico/financiero del estudiante.
- Las organizaciones ya no se administran aqui; eso vive en `personas`.

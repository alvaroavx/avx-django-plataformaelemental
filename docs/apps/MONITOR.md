# MONITOR

Fecha de actualizacion: 2026-04-29

## Proposito
La app `monitor` agrupa vistas internas de monitoreo operativo de la plataforma.

## Estado inicial
- App Django registrada como `monitor.apps.MonitorConfig`.
- Ruta base disponible en `/monitor/`.
- Vista inicial `monitor:dashboard` protegida por autenticacion.
- Enlace disponible desde la barra compartida de apps.
- Sin modelos propios en la creacion inicial.

## Reglas locales
- Los indicadores futuros deben consumir datos desde las apps duenas del dominio, sin duplicar modelos.
- Los filtros globales `periodo_mes`, `periodo_anio` y `organizacion` deben mantenerse activos en las vistas HTML de monitor.
- Cualquier indicador que mezcle datos de varias apps debe documentar su criterio de calculo en este archivo.

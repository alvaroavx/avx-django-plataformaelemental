# AGENTS.md - monitor

Este archivo gobierna el trabajo dentro de la app `monitor`.

Alcance:
- Modificar solo archivos dentro de `monitor/`.
- Si una tarea necesita tocar otra app, detenerse y explicar el motivo antes de cambiar codigo fuera de `monitor/`.
- Consumir modelos y servicios de otras apps cuando haga sentido, pero sin mover responsabilidades de dominio hacia `monitor`.

Objetivo de la app:
- Centralizar monitoreo operativo, auditoria tecnica y vistas de control para sitios/proyectos.
- Mantener una base Django clara antes de sumar alertas, reportes avanzados o IA.

Convenciones:
- Codigo en espanol cuando no complique integraciones o nombres de librerias.
- Vistas HTML autenticadas por defecto.
- Mantener filtros globales `periodo_mes`, `periodo_anio` y `organizacion` cuando una vista use el layout compartido.
- Evitar logica pesada en templates; preferir servicios, querysets claros o helpers locales.
- No crear modelos duplicados de personas, organizaciones, finanzas o asistencias.

Documentacion local:
- `PLANS.md`: estado de fases y foco actual.
- `docs/00-roadmap.md`: roadmap general.
- `docs/01-phase-1-plan.md`: alcance cerrado de fase 1.
- `docs/02-django-architecture.md`: arquitectura de la app.
- `docs/03-data-model.md`: modelo de datos esperado.
- `docs/13-design-direction.md`: direccion visual AVX Mission Control.

Comandos utiles:
- `python manage.py check`
- `python manage.py test monitor`

Antes de cerrar una tarea:
- Revisar si se actualizo el documento local correspondiente.
- Ejecutar al menos `python manage.py check`.
- Ejecutar tests de `monitor` si se tocaron vistas, modelos, formularios, servicios o URLs.

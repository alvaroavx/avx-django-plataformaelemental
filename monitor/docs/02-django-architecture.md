# Arquitectura Django

## App
`monitor` es una app Django interna dentro del monolito Plataforma Elemental.

## Capas esperadas
- `models.py`: entidades propias de monitor.
- `forms.py`: validacion de formularios HTML.
- `services/`: discovery, checks y normalizacion de URLs.
- `views.py`: orquestacion HTTP y render de templates.
- `urls.py`: rutas HTML de la app.
- `static/monitor/`: estilos propios de monitor.
- `templates/monitor/`: vistas de usuario.
- `tests.py` o `tests/`: cobertura de flujo principal.

## Dependencias permitidas
- Django auth para autenticacion.
- `personas` para organizaciones y personas si el flujo necesita owner o responsable.
- Librerias HTTP solo cuando haya una necesidad concreta y documentada.

## Reglas
- Las vistas no deben contener parsing HTTP complejo.
- Las llamadas externas deben estar encapsuladas en servicios testeables.
- Los timeouts deben ser explicitos.
- El discovery inicial debe degradar bien si el sitio no responde.
- Las URLs deben normalizarse antes de persistirse.

## Rutas esperadas
- `/monitor/`: dashboard.
- `/monitor/sitios/nuevo/`: agregar sitio.
- `/monitor/sitios/<id>/`: detalle de sitio.
- `/monitor/sitios/<id>/configuracion/`: configuracion por sitio.
- `/monitor/configuracion/`: configuracion global.

## Templates
Usar `asistencias/base_app.html` mientras sea el layout compartido vigente. Si `monitor` necesita identidad visual mas fuerte, crear templates propios dentro de `monitor/templates/monitor/` sin modificar templates globales fuera de la app.

# Plan Fase 1

## Objetivo
Dejar `monitor` como app Django usable para registrar sitios, ejecutar discovery inicial y ver estado general desde una interfaz responsive.

## Estado
Primera version implementada.

## Entregables
- Modelos base:
  - `Proyecto`
  - `Sitio`
  - `ConfiguracionMonitor`
  - `ConfiguracionSitio`
  - `DiscoverySitio`
- Flujo de agregar sitio por URL.
- Dashboard general.
- Vista detalle por sitio.
- Tests de modelos, vistas y flujo principal.
- Documentacion actualizada.

## Rutas implementadas
- `/monitor/`
- `/monitor/sitios/nuevo/`
- `/monitor/sitios/<id>/`
- `/monitor/sitios/<id>/configuracion/`
- `/monitor/configuracion/`

## Flujo minimo
1. Usuario autenticado entra a `/monitor/`.
2. Crea o selecciona un proyecto.
3. Agrega un sitio por URL.
4. El sistema normaliza la URL.
5. El sistema ejecuta discovery inicial sin worker externo.
6. El sitio queda visible en el dashboard.
7. El detalle muestra estado, configuracion y resultado inicial.

## Criterios de aceptacion
- Un usuario anonimo no accede a vistas HTML de `monitor`.
- Una URL invalida muestra error claro.
- Una URL valida crea un sitio normalizado.
- La configuracion global puede existir sin configuracion por sitio.
- El dashboard carga aunque no existan sitios.
- Mobile muestra las mismas acciones esenciales sin depender de tablas anchas.

## Fuera de alcance
- Workers periodicos.
- Alertas por email, Slack o WhatsApp.
- Reportes PDF.
- Scoring SEO definitivo.
- Multi-tenant complejo.

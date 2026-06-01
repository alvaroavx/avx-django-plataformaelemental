# Monitor Archivado

Fecha de actualizacion: 2026-06-01

## Que era
`monitor` era una app Django interna para registrar sitios, ejecutar discovery tecnico inicial y visualizar estado basico de URLs.

No era parte del dominio core de `Elemental Apps`.

## Funcionalidades historicas
- Crear proyectos y sitios.
- Normalizar URLs.
- Ejecutar discovery HTTP inicial.
- Guardar estado HTTP, URL final, titulo, meta description, SSL basico, tiempo de respuesta y error.
- Configurar timeout/frecuencia/redirecciones globales o por sitio.

## Modelos
- `Proyecto`
- `Sitio`
- `ConfiguracionMonitor`
- `ConfiguracionSitio`
- `DiscoverySitio`

## Rutas antiguas
- `/monitor/`
- `/monitor/sitios/nuevo/`
- `/monitor/sitios/<id>/`
- `/monitor/sitios/<id>/configuracion/`
- `/monitor/configuracion/`

## Servicios
- `monitor.services.urls.normalizar_url`
- `monitor.services.discovery.ejecutar_discovery_inicial`

El servicio de discovery realiza requests HTTP reales a sitios externos.

## Estado actual
- Archivado/desactivado del producto principal.
- `/monitor/` no esta registrado en URLs raiz.
- No aparece en navegacion.
- Se mantiene en `INSTALLED_APPS` temporalmente para preservar modelos, migraciones y posible data historica.
- No se eliminan tablas `monitor_*`.

## Como auditar datos antes de retirar completamente
Usar:

```bash
python manage.py auditar_monitor
```

Si hay filas relevantes en produccion, exportarlas o decidir conservacion antes de retirar la app de `INSTALLED_APPS`.

## Plan futuro
Opciones:
- Extraer a proyecto separado.
- Convertir contenido util en pagina estatica.
- Eliminar app en sprint posterior, luego de confirmar que no hay datos necesarios.

No reactivar dentro de `Elemental Apps` v1.0 salvo nueva decision explicita.

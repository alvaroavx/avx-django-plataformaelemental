# MONITOR

Fecha de actualizacion: 2026-06-01

## Estado
`monitor` esta archivada/desactivada del producto principal `Elemental Apps` v1.0.

Decision:
- No forma parte de la navegacion principal.
- La ruta `/monitor/` ya no esta registrada en las URLs raiz.
- La app se mantiene temporalmente en `INSTALLED_APPS`.
- No se borran modelos, migraciones ni tablas.
- Antes de quitarla de `INSTALLED_APPS`, se debe auditar si existen filas `monitor_*` en produccion.

## Motivo
La app `monitor` es una herramienta distinta al core operacional de Plataforma Elemental. Puede ser util como proyecto separado o pagina estatica futura, pero no debe aumentar la superficie viva de la plataforma interna v1.0.

## Modelos historicos
- `Proyecto`
- `Sitio`
- `ConfiguracionMonitor`
- `ConfiguracionSitio`
- `DiscoverySitio`

## Rutas historicas
- `/monitor/`
- `/monitor/sitios/nuevo/`
- `/monitor/sitios/<id>/`
- `/monitor/sitios/<id>/configuracion/`
- `/monitor/configuracion/`

## Auditoria de datos
Existe comando read-only:

```bash
python manage.py auditar_monitor
```

El comando solo cuenta registros. No borra ni modifica datos.

## Futuro posible
Si se decide recuperar `monitor`, hacerlo fuera del producto principal:
- proyecto separado
- pagina estatica
- herramienta interna independiente

La referencia de archivo vive en:
- `docs/archivo/MONITOR.md`

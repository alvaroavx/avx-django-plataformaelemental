# Reglas de configuracion

## Niveles
1. Defaults de codigo.
2. `ConfiguracionMonitor` global.
3. `ConfiguracionSitio` por sitio.

La configuracion mas especifica gana sobre la general.

## Defaults sugeridos
- Timeout: 10 segundos.
- Frecuencia: 60 minutos.
- Seguir redirecciones: si.
- User-Agent: identificable como Plataforma Elemental Monitor.

## Reglas
- Un sitio debe poder operar solo con defaults.
- La configuracion por sitio no debe duplicar todos los valores si solo cambia uno.
- Los valores fuera de rango deben validarse en forms y modelos.
- Los cambios de configuracion deben ser visibles para usuarios administrativos.

## Validaciones
- Timeout minimo: 1 segundo.
- Timeout maximo: 60 segundos.
- Frecuencia minima: 5 minutos.
- Frecuencia maxima: 1440 minutos.

# Monitoreo y alertas

## Fase 1
No hay alertas reales. Solo discovery manual/inicial y visualizacion de estado.

## Fase 2
Agregar checks programados y alertas internas.

Checks candidatos:
- Disponibilidad HTTP.
- Codigo de estado.
- Tiempo de respuesta.
- SSL valido y fecha de expiracion.
- Redirecciones.
- Cambios de titulo o metadatos relevantes.

## Severidad
- `info`: cambio menor o dato nuevo.
- `warning`: degradacion o configuracion riesgosa.
- `critical`: caida, SSL roto o error sostenido.

## Reglas
- Una alerta debe tener sitio, severidad, mensaje y timestamp.
- Evitar ruido: no crear alertas duplicadas para el mismo problema activo.
- Toda alerta debe poder cerrarse o marcarse como revisada cuando exista el modelo.

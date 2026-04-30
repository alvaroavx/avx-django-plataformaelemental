# Modelo de datos

## Principio
`monitor` solo modela entidades de monitoreo. Personas, organizaciones, pagos y asistencias siguen viviendo en sus apps duenas.

## Entidades fase 1
Estado: implementadas en `monitor.models`.

### Proyecto
Agrupa sitios bajo una unidad operativa.

Campos sugeridos:
- `nombre`
- `descripcion`
- `organizacion` opcional hacia `personas.Organizacion`
- `activo`
- `creado_en`
- `actualizado_en`

### Sitio
Representa una URL monitoreable.

Campos sugeridos:
- `proyecto`
- `nombre`
- `url`
- `dominio`
- `activo`
- `ultimo_estado`
- `ultimo_check_en`
- `creado_en`
- `actualizado_en`

### ConfiguracionMonitor
Define defaults globales.

Campos sugeridos:
- `timeout_segundos`
- `frecuencia_minutos`
- `seguir_redirecciones`
- `user_agent`

### ConfiguracionSitio
Sobrescribe defaults por sitio.

Campos sugeridos:
- `sitio`
- `timeout_segundos`
- `frecuencia_minutos`
- `seguir_redirecciones`
- `activo`

### DiscoverySitio
Registra resultado inicial o manual de discovery.

Campos sugeridos:
- `sitio`
- `estado_http`
- `url_final`
- `titulo`
- `meta_description`
- `ssl_valido`
- `tiempo_respuesta_ms`
- `error`
- `creado_en`

## Migracion
La migracion inicial vive en `monitor/migrations/0001_initial.py`.

## Reglas
- Dinero no pertenece a `monitor`.
- No guardar HTML completo salvo decision explicita.
- Guardar errores como texto acotado, no como dumps extensos.
- No hacer unique global solo por dominio si el producto permite ambientes distintos con rutas distintas.

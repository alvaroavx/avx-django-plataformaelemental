# API

Fecha de actualizacion: 2026-06-01

## Proposito v1.0
La app `api` queda reducida a una superficie minima operativa para `Elemental Apps`.

Decision:
- No exponer datos personales, asistencias, pagos, documentos tributarios ni transacciones por API mientras no exista consumidor real.
- Mantener endpoints de salud/version para operacion.
- Mantener `GET /api/me/` como check minimo de autenticacion.
- Conservar `ApiAccessKey` temporalmente por compatibilidad historica, pero sin endpoints de datos activos que la usen.

## Endpoints activos

### Salud
- `GET /api/health/`

Respuesta:
```json
{"status": "ok"}
```

### Estado
- `GET /api/status/`

Respuesta:
```json
{"status": "ok", "service": "elemental-apps"}
```

### Version
- `GET /api/version/`

Respuesta:
```json
{"name": "Elemental Apps", "version": "v1.0"}
```

### Usuario actual
- `GET /api/me/`
- Requiere usuario autenticado.
- Devuelve payload minimo.

Respuesta:
```json
{
  "username": "usuario",
  "is_authenticated": true,
  "timestamp": "..."
}
```

## Endpoints desactivados
Quedan desactivados por reduccion de superficie y mantenimiento:

- `/api/sesiones/`
- `/api/estudiantes/`
- `/api/reportes/resumen/`
- `/api/v1/personas/*`
- `/api/v1/asistencias/*`
- `/api/v1/finanzas/*`
- endpoints de pagos
- endpoints de documentos tributarios
- endpoints de transacciones

Estos endpoints deben responder `404` al no estar registrados en `api.urls`.

## Seguridad
- No hay endpoints publicos de datos operacionales o financieros.
- `GET /api/me/` exige autenticacion.
- API key no entrega acceso a datos en v1.0 porque no hay endpoints de datos activos.
- `ApiAccessKey` se conserva temporalmente para no tocar tabla/migracion y para una futura decision explicita.
- Token DRF se mantiene disponible a nivel de dependencias/settings, pero no existe flujo publico de login API activo en v1.0.

## Operacion
Comandos utiles:

```bash
curl https://apps.espacioelementos.cl/api/health/
curl https://apps.espacioelementos.cl/api/status/
curl https://apps.espacioelementos.cl/api/version/
```

## Decision arquitectonica
La API anterior era amplia y exponia personas, asistencias y finanzas sin consumidor real actual desde la UI HTML.

Para v1.0 interna, la prioridad es reducir:
- superficie de ataque
- costo de mantenimiento
- riesgo de fuga de datos personales o financieros
- deuda de tests sobre endpoints no usados

Si en el futuro aparece un consumidor real, se debe reabrir API por caso de uso concreto, con permisos, filtros por organizacion y tests especificos.

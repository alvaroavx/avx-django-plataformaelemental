# Workflow agregar sitio

## Objetivo
Permitir que un usuario agregue un sitio por URL con el menor roce posible y con validaciones claras.

## Flujo
1. Usuario abre `Agregar sitio`.
2. Ingresa URL.
3. El sistema normaliza:
   - agrega `https://` si falta esquema
   - limpia espacios
   - conserva path si existe
4. El sistema valida formato.
5. Se crea `Sitio`.
6. Se ejecuta discovery inicial.
7. Usuario llega al detalle del sitio.

Estado: implementado en `SitioCreateForm`, `monitor.views.sitio_create` y `monitor.services.discovery.ejecutar_discovery_inicial`.

## Estados
- `pendiente`: sitio creado sin discovery exitoso.
- `activo`: discovery respondio correctamente.
- `advertencia`: discovery respondio con senales parciales.
- `error`: no hubo respuesta usable.

## Errores esperados
- URL invalida.
- Dominio no resolvible.
- Timeout.
- SSL invalido.
- HTTP 4xx o 5xx.

## UX
- Mostrar errores cerca del campo URL.
- No perder lo ingresado si falla la validacion.
- En mobile, el formulario debe ocupar ancho completo y priorizar el boton principal.

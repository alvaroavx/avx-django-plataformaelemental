# Permisos Y Roles

Fecha de actualizacion: 2026-05-11

## Proposito
Este documento define el criterio transversal de roles y permisos.

Los roles ya afectan navegacion, filtros, operacion academica, pagos y perfiles. Por eso no deben crecer de forma implicita.

## Modelo Actual
La identidad vive en `personas`.

Modelos principales:
- `Persona`
- `Organizacion`
- `Rol`
- `PersonaRol`

Relacion central:

```text
Persona -- PersonaRol -- Rol
              |
         Organizacion
```

Regla:
- El rol se asigna por persona y organizacion.
- Una persona puede tener roles distintos en organizaciones distintas.
- No puede repetirse la misma combinacion `persona + rol + organizacion`.

## Roles Funcionales Vigentes
Los codigos relevantes hoy son:
- `ESTUDIANTE`
- `PROFESOR`

Tambien existen roles administrativos historicos o base segun datos/migraciones, pero no deben asumirse como politica final sin revisar codigo y datos vigentes.

## Superuser Y Staff
Regla operativa:
- `superuser` y `staff` pueden saltar chequeos de rol donde el codigo vigente lo permita.
- Esto no reemplaza una politica formal de permisos.
- Si se agrega una accion sensible, se debe decidir explicitamente si basta con staff/superuser o si requiere rol por organizacion.

## Reglas Por Rol

### Estudiante
Uso:
- puede tener asistencias,
- puede tener pagos,
- puede tener consumos financieros,
- puede aparecer en seguimiento de deuda/saldo.

Reglas:
- `Payment.persona` debe apuntar a personas con rol `ESTUDIANTE` activo segun organizacion cuando el flujo lo valide.
- El alta rapida desde pagos o asistencias puede crear persona con rol `ESTUDIANTE` en la organizacion filtrada.

### Profesor
Uso:
- puede dictar sesiones,
- puede aparecer como profesor en `SesionClase.profesores`,
- puede tener configuracion economica en `PersonaRol`.

Reglas:
- Para seleccion operativa, profesor vigente equivale a `Persona.activo=True` y `PersonaRol.activo=True` con rol `PROFESOR`.
- `valor_clase` y `retencion_sii` viven en `PersonaRol`, porque dependen de persona + organizacion.

## Acceso HTML
Estado actual:
- Las vistas HTML requieren autenticacion.
- Algunas vistas usan decoradores de acceso por rol.
- La politica fina todavia no esta centralizada como matriz completa.

Reglas:
- No implementar chequeos de permiso dispersos sin test.
- Si una accion modifica datos criticos, debe tener permiso explicito o al menos quedar cubierta por test de acceso.
- Las reglas de permisos deben considerar organizacion activa, no solo rol global.

## API
La API usa:
- token DRF para usuarios,
- API key de solo lectura para consultas.

Reglas:
- API key no permite escrituras.
- Escrituras requieren usuario autenticado.
- La API no debe inferir permisos administrativos solo por conocer una API key.

Detalle:
- [docs/apps/API.md](../apps/API.md)

## Riesgos Actuales
- Roles administrativos no estan formalizados como matriz completa.
- Hay diferencias entre rol activo de persona y estado activo de persona.
- Algunas pantallas filtran por rol para operar, pero no necesariamente eso equivale a permiso de escritura.
- Si se agregan mas apps, roles y permisos pueden volverse ambiguos rapidamente.

## Recomendacion
Antes de agregar permisos mas complejos:
- definir matriz de acciones sensibles,
- definir si permiso depende de organizacion,
- definir si staff/superuser basta,
- agregar tests de acceso,
- documentar en este archivo.

## Matriz Minima Pendiente
Acciones que deberian formalizarse:
- crear/editar pagos,
- editar documentos tributarios,
- cambiar estado de sesion,
- registrar asistencia,
- crear personas desde modales rapidos,
- crear API keys,
- ver documentos tributarios adjuntos,
- acceder a monitor.

# UX

Fecha de actualizacion: 2026-05-30

## Proposito
`Elemental Apps` es el nombre visible de Plataforma Elemental para la operacion diaria.

La UX v1.0 prioriza:
- navegacion clara
- uso mobile-first
- continuidad de filtros globales
- accesos visibles segun permisos existentes

## Home Oficial
La ruta `/` muestra el dashboard general `Elemental Apps`.

El dashboard muestra cards de acceso a:
- Personas
- Asistencias
- Finanzas
- Admin, solo para `staff` o `superuser`

No muestra:
- Monitor, porque queda fuera de navegacion v1.0 y se evaluara eliminarlo.
- API, porque no existe una vista HTML operativa para usuarios internos.

Si un usuario autenticado no tiene accesos visibles, se muestra un mensaje controlado y no un error.

## Login
El login usa una pantalla limpia y centrada con el nombre `Elemental Apps`.

Reglas:
- no cambia backend de autenticacion
- mantiene CSRF
- respeta `next`
- muestra errores del formulario existente

## Navegacion
La navegacion principal vive en un sidebar global responsive.

Desktop:
- sidebar izquierdo persistente
- nombre `Elemental Apps`
- grupos por dominio visible

Mobile:
- boton hamburguesa
- sidebar como offcanvas Bootstrap
- el contenido mantiene prioridad de pantalla

La navegacion se construye desde `plataformaelemental.navigation`, no desde templates individuales.

## Barra De Contexto
La parte superior del area principal contiene:
- boton de menu en mobile
- descripcion del periodo activo
- filtros `periodo_mes`, `periodo_anio` y `organizacion`
- usuario actual
- logout

Los filtros conservan parametros adicionales del querystring y se autoaplican al cambiar.

## Visibilidad Por Permisos
La navegacion usa permisos existentes:
- `Personas`: permisos administrativos de personas
- `Asistencias`: permisos administrativos/operativos de sesiones
- `Finanzas`: permiso de lectura financiera
- `Admin`: `staff` o `superuser`

No se agregan permisos nuevos de backend en este sprint.

## Footer
El layout principal muestra footer discreto:

`Implementado por AVX`

## Limitaciones Conocidas
- No se implementa auditoria transversal.
- No se implementa backoffice/configuracion.
- No se implementa rediseño profundo del Django Admin.
- No se cambia la app `monitor`; solo se oculta de navegacion principal.
- Algunas acciones secundarias conservan botones compactos existentes para evitar tocar demasiadas vistas antes de v1.0.

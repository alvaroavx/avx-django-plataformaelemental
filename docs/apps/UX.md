# UX

Fecha de actualizacion: 2026-06-01

## Proposito
`Elemental Apps` es el nombre visible de Plataforma Elemental para la operacion diaria.

La UX v1.0 prioriza:
- navegacion clara
- uso mobile-first
- continuidad de filtros globales
- accesos visibles segun permisos existentes

## Home Oficial
La ruta `/` muestra el panel general `Elemental Apps`.

El panel muestra cards de acceso a:
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
- logo de la organizacion seleccionada, si existe
- fallback con iniciales cuando la organizacion seleccionada no tiene logo
- descripcion del periodo activo
- filtros `periodo_mes`, `periodo_anio` y `organizacion`
- usuario actual
- logout

Los filtros conservan parametros adicionales del querystring y se autoaplican al cambiar.

Si la organizacion seleccionada es `Todas`, la barra muestra `Elemental Apps` y no muestra logo de ninguna organizacion.

El logo de organizacion vive en `Organizacion.logo`, es opcional y se administra inicialmente desde Django Admin.

## Navegacion De Retorno
Las pantallas internas priorizan un boton `Volver` con icono `bi-arrow-left`.

Regla:
- usa la pagina anterior cuando la view expone `HTTP_REFERER`
- usa fallback seguro por pantalla cuando no existe pagina anterior
- conserva filtros globales cuando la URL de fallback los conoce

## Lenguaje Visible
Desde v1.0 se usa `Panel` para vistas principales. `Dashboard` queda reservado solo para nombres internos de rutas/views cuando cambiarlo podria romper compatibilidad.

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
- `monitor` queda archivado: no aparece en navegacion y `/monitor/` no esta registrado como ruta activa.
- Algunas acciones secundarias conservan botones compactos existentes para evitar tocar demasiadas vistas antes de v1.0.

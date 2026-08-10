# UX

Fecha de actualizacion: 2026-07-26

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
- Google muestra el texto explicativo, un botón visible `Continuar con Google` con identificador gráfico de Google y un isotipo Elemental ampliado cuando `GOOGLE_AUTH_ENABLED=true`; no repite el nombre de la plataforma dentro de la tarjeta.
- La pantalla pública `personas/solicitar-acceso/` usa la misma composición centrada del login, con un isotipo Elemental más pequeño, tarjeta de estado y acciones a ancho completo. Conserva el texto aprobado del flujo de solicitud.
- El inicio Google es POST con CSRF; `next` se valida en servidor y no acepta destinos externos. El servidor fija los scopes, `access_type=online` y `process=login`.
- Mientras `GOOGLE_AUTH_ENFORCED=false`, el formulario local existente sigue disponible. Cuando se fuerza Google, el acceso local operacional se oculta y rechaza POST.
- La ruta no enlazada `/accounts/emergencia/` mantiene recuperacion local solo para superusuarios.
- La bandeja de solicitudes de acceso usa listado paginado, filtros y tarjetas móviles; el detalle busca candidatos de forma explícita y acotada. Los formularios anuncian errores, deshabilitan la acción durante el envío y mantienen foco visible. Esta revisión cubre teclado, reflow y zoom manualmente, sin declarar conformidad WCAG formal.
- Cuando `ACCESS_REQUESTS_ENABLED=true`, el menú lateral de Personas muestra `Solicitudes de acceso` solo a quienes poseen el permiso global `personas.gestionar_solicitudes_acceso`. Si existen pendientes, el enlace muestra su cantidad; abrir la bandeja no la reduce, solo resolverlas.

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

## Acciones En Formularios
- El boton `Agregar` de roles en detalle y edicion de Persona usa el componente solido de Bootstrap, conserva foco visible y tiene una altura minima de 44 px.
- En mobile, el formulario apila sus campos y la accion ocupa el ancho disponible sin provocar desplazamiento horizontal a 320 px.

## Prototipo móvil Sprint 2

La gramática mínima de `Hoy`, detalle de sesión y resumen administrativo se documenta en `docs/apps/GRAMATICA_MOVIL_SPRINT2.md`. El prototipo vive en `docs/prototipos/`, separado de rutas activas. Su validación con Beisics y dos profesoras continúa pendiente.

## Jornada móvil de clases — Sprint 3

La ruta activa `/asistencias/hoy/` materializa la parte operativa del prototipo
para profesoras autorizadas. La experiencia incluye:

- sesiones del día ordenadas por horario, con organización, equipo, cantidad de
  asistentes y estado temporal expresado con texto e icono;
- detalle de sesión en tarjetas móviles, sin controles administrativos ni
  detalles financieros para profesoras;
- búsqueda incremental de estudiantes elegibles de la organización;
- agregado consecutivo sin recargar la pantalla, con limpieza y reenfoque tras
  el éxito;
- conservación del texto y mensaje anunciable en errores, duplicados o pérdida
  de conexión;
- cambio rápido entre presente, ausente y justificada con estado textual,
  `aria-pressed` y confirmación mediante `aria-live`;
- objetivos principales de al menos 44 px, foco visible, reflow a 390 y 320 px
  y navegación por teclado.

La implementación no añade funcionamiento offline: cuando se pierde conexión
informa que la operación no fue confirmada y permite reintentar. La validación
usuaria con Beisics y dos profesoras continúa pendiente. La evidencia renderizada
con fixtures de prueba está en `docs/prototipos/SPRINT3_EVIDENCIA.md`.

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
- Existe auditoria transversal parcial para mutaciones seleccionadas; no cubre lecturas, exports ni todos los automatismos.
- No se implementa backoffice/configuracion.
- No se implementa rediseño profundo del Django Admin.
- `monitor` queda archivado: no aparece en navegacion y `/monitor/` no esta registrado como ruta activa.
- Algunas acciones secundarias conservan botones compactos existentes para evitar tocar demasiadas vistas antes de v1.0.

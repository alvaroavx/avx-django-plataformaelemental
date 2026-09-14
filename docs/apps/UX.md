# UX

Fecha de actualizacion: 2026-09-11

## Proposito
`Elemental Apps` es el nombre visible de Plataforma Elemental para la operacion diaria.

La UX v1.0 prioriza:
- navegacion clara
- uso mobile-first
- continuidad de filtros globales
- accesos visibles segun permisos existentes

## Home Oficial
La ruta `/` muestra un resumen operacional transversal, no un catálogo de apps
ni una réplica de los paneles especializados.

La primera entrega incluye, según permisos y organizaciones visibles:
- sesiones completadas;
- personas con una asistencia registrada, sin inferir presencia ni participación;
- clases en deuda desde `AttendanceConsumption.DEUDA`;
- ingresos contables desde `Transaction.INGRESO`;
- incidencias calculables con enlace al flujo resolutivo;
- hasta tres sesiones futuras no canceladas;
- consulta acotada de persona para administradores de Personas.

Los cuatro indicadores principales no enlazan a índices genéricos. Cada uno abre
un detalle paginado construido desde el mismo queryset que produce su cifra:

- sesiones completadas muestra exclusivamente esas sesiones;
- personas con asistencia agrupa personas únicas e indica cantidad y último registro;
- clases en deuda muestra cada consumo que permanece en deuda;
- ingresos contables muestra las transacciones de ingreso cuya suma produce el total.

El detalle conserva período, organización y permisos, explicita la definición
del indicador y permite volver al resumen sin perder el contexto.

La consulta conserva período y organización. Distingue pagos operacionales de
ingresos contables y no muestra todavía saldo de clases: las superficies actuales
usan cortes temporales diferentes para ese concepto. Profesor puro conserva su
redirección a `/profesor/`.

Si un usuario autenticado no tiene información operacional visible, se muestra
un mensaje controlado y no un error. `Monitor` y `API` permanecen fuera del home.

## Login
El login usa una pantalla limpia y centrada con el nombre `Elemental Apps`.

El tema oscuro utiliza un fondo azul profundo continuo, superficies elevadas y
texto de alto contraste; no conserva el lienzo claro del tema diurno. Los
botones de Google y acceso local tienen estados propios legibles sobre la tarjeta
oscura sin cambiar sus acciones ni la política de autenticación.

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
- sidebar izquierdo expandido o contraído mediante un control visible de 44 px
- la preferencia se conserva localmente en `elemental-sidebar-collapsed`
- el rail contraído muestra Inicio y un acceso primario inequívoco por dominio
- los enlaces compactos conservan nombre accesible, contexto activo y badges
- el control permanece disponible al desplazar el menú y el estado guardado se
  aplica antes de habilitar la transición visual
- nombre `Elemental Apps`
- Inicio como destino independiente
- dominios visibles como encabezados no clickeables
- páginas autorizadas siempre visibles bajo cada dominio
- página actual marcada visualmente y mediante `aria-current="page"`
- el dominio académico se presenta como `Sesiones`; no cambia las URLs ni el
  nombre técnico de la app `asistencias`

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
- control de tema claro/oscuro siempre visible

Los filtros conservan parametros adicionales del querystring y se autoaplican al cambiar.

Si la organizacion seleccionada es `Todas`, la barra muestra `Elemental Apps` y no muestra logo de ninguna organizacion. Staff y superusuarios pueden operar agregados globales; los roles acotados a organizaciones deben seleccionar una antes de recibir navegación y métricas operativas.

El logo de organizacion vive en `Organizacion.logo`, es opcional y se administra inicialmente desde Django Admin.

## Tema visual

El shell administrativo y Operación Profesor comparten una única preferencia
cliente `elemental-theme`. Se aplica en el `<head>` antes de cargar Bootstrap
para evitar un destello del tema contrario, y mantiene sincronizados
`data-theme` y `data-bs-theme` para reutilizar tanto las variables propias de
Profesor como el soporte nativo de Bootstrap 5.3.

Si no existe preferencia guardada, se respeta `prefers-color-scheme`; el control
de la barra de contexto alterna Claro/Oscuro con nombre accesible e icono. La
clave anterior `profesor-theme` se lee una vez como compatibilidad y se elimina
al guardar una nueva elección. No se persiste ninguna preferencia en la base de
datos.

En modo oscuro, paneles, tablas, tarjetas de métricas y eventos de calendario
usan superficies y bordes semánticos del shell. Los botones de contorno deben
mantener texto y borde reconocibles en reposo; el hover no puede ser la única
forma de descubrir una acción. Las variantes de métricas conservan su familia
de color, pero elevan contraste de fondo, borde y texto.

## Resumen de operación y jornada diaria

El Resumen de operación incorpora las sesiones de la fecha actual visibles para
el usuario, con organización, horario, profesores, estado y asistentes. La
selección global de organización limita también esta sección. El acceso `Hoy`
se retira del menú administrativo para evitar dos puntos de entrada a la misma
información; la ruta `/asistencias/hoy/` se conserva porque sigue siendo la
jornada operativa de la aplicación de profesores.

## Calendario responsive

En pantallas menores a `768px`, el calendario abre en modo semanal: cada semana
ocupa el ancho del contenedor, sus siete días se ordenan verticalmente y el
desplazamiento horizontal permite recorrer las demás semanas del mes. Si el
período corresponde al mes actual, la posición inicial es la semana de hoy; en
otros meses comienza en la primera semana. El control `Ver mes` alterna a la
grilla mensual y cambia su etiqueta a `Ver semana`. En desktop la vista mensual
continúa siendo la presentación predeterminada.

## Densidad operativa en mobile

Los encabezados móviles priorizan el título y el contenido propio de la página.
Las acciones superiores se representan con iconos de al menos `44px`, nombre
accesible y una sola fila horizontal desplazable cuando no caben; sus etiquetas
completas reaparecen desde tablet/desktop. Las métricas de resumen se compactan
en grillas de dos o tres columnas según cantidad y longitud, evitando que cada
tarjeta consuma por sí sola el ancho y alto inicial de la pantalla. En desktop
se conservan las etiquetas y acciones expandidas.

Los filtros extensos de listados permanecen visibles en desktop. En mobile se
agrupan bajo un control `Filtros` cerrado por defecto, cuya descripción breve
anticipa los criterios disponibles y cuyo chevron comunica el estado abierto o
cerrado. Este patrón se usa en sesiones/asistencias, estudiantes, personas y
pagos para que los resultados aparezcan antes sin eliminar capacidad de ajuste.

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

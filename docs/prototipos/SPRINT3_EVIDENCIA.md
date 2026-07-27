# Evidencia móvil Sprint 3

Fecha: 2026-07-26

Las capturas se generaron con Chrome headless desde respuestas reales de las
vistas Django, usando exclusivamente fixtures ficticias en la base PostgreSQL
de pruebas. No contienen datos históricos ni información de personas reales.
Los estados transitorios de sugerencias, éxito y duplicado se representaron
sobre una copia del render para hacer visible el contenido que anuncia el
JavaScript durante cada operación.

## Capturas a 390 × 844 px

- [Vista Hoy](capturas/sprint3/hoy-390x844.png)
- [Detalle de sesión](capturas/sprint3/detalle-390x844.png)
- [Buscador con sugerencias](capturas/sprint3/buscador-sugerencias-390x844.png)
- [Asistente agregado correctamente](capturas/sprint3/agregado-exitoso-390x844.png)
- [Reintento o persona duplicada](capturas/sprint3/duplicado-390x844.png)

## Reflow a 320 × 900 px

- [Detalle de sesión](capturas/sprint3/detalle-320x900.png)

## Zoom al 200 %

- [Detalle a escala efectiva 200 %](capturas/sprint3/detalle-zoom200-390x844.png)

La comprobación automatizada usó un viewport físico de 390 × 844 px con
`devicePixelRatio=2`, equivalente a 195 CSS px de ancho. Chrome informó
`clientWidth=180`, `scrollWidth=180` y ningún elemento fuera del ancho visible.

La revisión visual confirma que no existe desplazamiento horizontal en ambos
anchos, las acciones principales mantienen área táctil cercana o superior a
44 px y la jerarquía sesión → agregar → asistentes permanece estable.

## Accesibilidad técnica comprobada

- controles nativos y botones alcanzables por teclado;
- foco global visible con `:focus-visible`;
- grupos de estado con `role="group"` y `aria-pressed`;
- feedback de búsqueda y guardado mediante regiones `aria-live`;
- estados expresados con texto e icono, no solo color;
- reflow a 320 px y estructura compatible con zoom de navegador al 200 %;
- errores de red conservan el texto de búsqueda y no confirman operaciones que
  el servidor no recibió.

Esta evidencia es técnica. La prueba de uso con Beisics y dos profesoras sigue
pendiente y no se reemplaza por estas capturas.

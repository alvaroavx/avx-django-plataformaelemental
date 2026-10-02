# ADR 0007: botonera móvil de una fila e iconos en el detalle de sesión

- Estado: en revisión
- Fecha: 2026-10-02
- Decisor: Álvaro

## Contexto

En `asistencias/sesiones/<id>/`, las cinco acciones superiores ocupaban tres
filas en una pantalla móvil y mezclaban botones de ancho completo con controles
pequeños. La composición consumía altura antes de mostrar la información de la
sesión.

## Alternativas descartadas

- Mantener texto y repartir las acciones en dos filas: conserva comprensión
  inmediata, pero no resuelve la altura ni la irregularidad observadas.
- Llevar acciones secundarias a un menú: reduce espacio, pero agrega una apertura
  y cambia más profundamente el flujo.

## Decisión

En móvil, las acciones superiores forman una sola fila de controles con igual
alto y ancho, mostrando únicamente iconos. En escritorio conservan sus textos.
Cada control mantiene `aria-label` y `title` para preservar un nombre accesible.

## Consecuencias asumidas

La cabecera gana compacidad y ritmo uniforme. A cambio, el significado de cada
icono puede no ser evidente para todas las personas, especialmente editar,
calendario y crear persona.

## Condiciones de revisión

Revisar después de probar el flujo en uso real. Si una acción no se reconoce sin
explicación, incorporar texto breve, tooltip activable por toque o agrupar las
acciones secundarias sin volver a tres filas.

# ADR 0014: Asistencias usa cards en mobile y tabla en escritorio

- Estado: Aceptada
- Fecha: 2026-10-06
- Decidió: Álvaro

## Contexto

La tabla de sesiones registradas reúne disciplina, organización, profesores,
fecha, estado, asistentes, total y acciones. En pantallas angostas obliga a
desplazarse horizontalmente para reconstruir una sola fila.

## Alternativas descartadas

- Ocultar columnas: perdería información necesaria para operar una sesión.
- Mantener scroll horizontal: conserva el problema señalado.
- Reordenar la tabla solo con CSS: mantiene una lectura tabular difícil de
  explorar verticalmente y complica las acciones.

## Decisión

En anchos inferiores a `768px`, Asistencias presenta cada sesión como una card
vertical con toda la información y las mismas acciones. Desde `768px`, conserva
la tabla. Ambas presentaciones usan el mismo contexto de servidor y los filtros
de texto, disciplina, profesor y fecha se sincronizan mediante DataTables.

Las cards muestran un estado vacío cuando no hay coincidencias. No incorporan
paginación móvil: muestran todas las sesiones que cumplen el filtro activo.

## Consecuencias asumidas

El HTML representa cada sesión dos veces para composiciones distintas, pero no
duplica consultas ni reglas de negocio. Las acciones mantienen CSRF, período y
organización. La tabla oculta en mobile actúa como motor de filtrado y orden.

## Condiciones de revisión

Revisar si el volumen habitual vuelve lenta la secuencia, si se incorpora
paginación de servidor o si otra tabla justifica extraer un componente reusable.

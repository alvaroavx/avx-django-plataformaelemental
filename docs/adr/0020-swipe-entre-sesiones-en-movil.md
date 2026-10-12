# ADR 0020: navegación móvil por swipe entre sesiones adyacentes

- Estado: aceptada
- Fecha: 2026-10-12
- Decisor: Álvaro

## Contexto

En el detalle de una sesión, recorrer varias clases desde un teléfono exige volver al calendario y abrir cada registro. La operación mensual se beneficia de una navegación consecutiva sin perder el período ni la organización seleccionados.

## Alternativas descartadas

- Reemplazar el gesto por botones anterior/siguiente: es más visible, pero agrega controles permanentes a una cabecera que se acaba de simplificar.
- Navegar por identificador correlativo: no representa el orden del calendario y puede cruzar períodos, organizaciones o sesiones sin acceso.
- Permitir el gesto sobre cualquier elemento: interfiere con controles, enlaces y desplazamiento vertical.

## Decisión

En pantallas móviles, un swipe horizontal sobre una zona no interactiva del detalle navega entre sesiones accesibles del período y organización actuales: izquierda avanza y derecha retrocede. El gesto exige predominio horizontal y conserva los filtros en la URL.

## Consecuencias asumidas

El gesto acelera el recorrido repetitivo, pero es poco descubrible y no sustituye la navegación visible mediante Calendario y Atrás. En los extremos del conjunto no produce navegación. Controles interactivos y desplazamiento vertical quedan excluidos del reconocimiento.

## Condiciones de revisión

Revisar si en uso real se producen activaciones accidentales, si el umbral de 72 px resulta incómodo o si las personas necesitan indicadores visibles de sesión anterior y siguiente.

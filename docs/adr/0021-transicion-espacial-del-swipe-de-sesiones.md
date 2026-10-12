# ADR 0021: transición espacial para el swipe entre sesiones

- Estado: aceptada
- Fecha: 2026-10-12
- Decisor: Álvaro

## Contexto

El swipe definido en ADR 0020 cambia correctamente de sesión, pero la navegación inmediata se percibe como un clic porque cada detalle es una página distinta. Se busca comunicar continuidad lateral sin convertir el detalle en un carrusel ni cargar sesiones vecinas dentro de la página actual.

## Alternativas descartadas

- Construir un carrusel con sesiones adyacentes embebidas: ofrece continuidad física real, pero duplica contenido, formularios y estado, y aumenta el riesgo operacional.
- Usar una transición larga que cubra la carga: añade demora percibida y no garantiza continuidad si la red tarda.
- Animar siempre: ignora la preferencia de movimiento reducido del sistema.

## Decisión

La sesión actual sale brevemente en la dirección del gesto antes de navegar. La página siguiente conserva esa dirección en `sessionStorage` y entra desde el lado opuesto. La transición sólo se aplica en móvil, dura menos de un cuarto de segundo y se omite con `prefers-reduced-motion: reduce`.

## Consecuencias asumidas

La continuidad es perceptual, no un carrusel real: una carga lenta aún puede interrumpirla. La URL, el renderizado del servidor, los permisos y los formularios mantienen su comportamiento actual.

## Condiciones de revisión

Revisar si la animación se siente lenta, si produce parpadeos en dispositivos reales o si una futura navegación nativa entre documentos ofrece una transición más consistente con menor código propio.

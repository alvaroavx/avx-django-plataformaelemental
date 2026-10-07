# ADR 0012: botones con icono y texto usan separación estructural

- Estado: Aceptada
- Fecha: 2026-10-06
- Decidió: Álvaro

## Contexto

Los botones que combinan icono y texto dependían de espacios escritos en el
HTML o de márgenes particulares. Eso permite resultados visuales inconsistentes
y vuelve fácil que icono y etiqueta aparezcan pegados.

En el borrador mensual, los botones de copia además quedaron deshabilitados al
faltar datos. La advertencia era correcta, pero impedía revisar y copiar un
borrador parcial.

## Alternativas descartadas

- Confiar en un espacio de texto después del icono: no es una regla visual
  verificable y puede desaparecer al reformatear el HTML.
- Añadir `margin` manual a cada icono: repite implementación y produce medidas
  distintas entre pantallas.
- Deshabilitar la copia ante datos incompletos: impide una acción reversible que
  igualmente puede ser útil para revisar el resultado.

## Decisión

Todo botón o enlace con icono y texto debe envolver ambos en
`.elemental-button-content`, que usa `inline-flex` y `gap: 0.375rem`; su anatomía
visible siempre es `[icono] [texto]`.

Los botones de copia permanecen operables aunque el borrador tenga datos
pendientes. La interfaz conserva la advertencia explícita y copia los valores
visibles, incluidos los marcadores `Sin informar` o `Sin calcular`.

## Consecuencias asumidas

Los componentes existentes pueden migrarse gradualmente cuando sean tocados; no
se hace una reescritura visual masiva. La clase es global y reutilizable. Copiar
un borrador incompleto exige que la persona atienda la advertencia antes de
enviarlo.

## Condiciones de revisión

Revisar la regla si el sistema adopta un componente único de botones que aplique
espaciado automáticamente o si pruebas de accesibilidad muestran que la
estructura interfiere con el nombre accesible.

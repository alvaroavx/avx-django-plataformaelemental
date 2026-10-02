# ADR 0008: tabla móvil de asistencia con información esencial

- Estado: en revisión
- Fecha: 2026-10-02
- Decisor: Álvaro

## Contexto

La tabla de asistentes exige desplazamiento horizontal en móvil. En la operación
real declarada, una persona incluida representa asistencia presente; los estados
Ausente y Justificada no se usan, y la hora de incorporación no ayuda a operar.
La liberación de clases sí debe permanecer disponible.

## Alternativas descartadas

- Eliminar inmediatamente estados y campos del dominio: cambia datos, servicios e
  historial antes de comprobar la nueva presentación.
- Convertir ahora cada fila en una tarjeta: amplía el cambio antes de observar si
  basta con reducir columnas.

## Decisión

Como primera prueba, en responsive se ocultan Hora y la columna Estado completa,
incluidos el selector y Guardar. Se mantienen Persona, Estado de pago y Acciones.
Escritorio conserva temporalmente todos los controles actuales.

## Consecuencias asumidas

La tabla móvil pierde edición de estado y detalle horario, pero gana espacio para
las acciones que sí se usan. Los estados históricos continúan intactos y siguen
visibles en escritorio.

## Condiciones de revisión

Revisar visualmente antes del siguiente cambio. Si todavía existe desplazamiento
horizontal o las acciones dominan la fila, reconsiderar únicamente su composición.
La eliminación real de Ausente y Justificada requiere una decisión posterior sobre
modelo, datos históricos, servicios y pruebas.

# ADR 0006: menú operativo plano y seguimiento en el Panel

- Estado: aceptada
- Fecha: 2026-10-02
- Decisor: Álvaro

## Contexto

Los encabezados `Sesiones` y `Finanzas` agregaban una jerarquía innecesaria al
sidebar para destinos de uso frecuente. Además, el panel propio de Sesiones
duplicaba información que corresponde al Panel transversal de inicio.

## Decisión

- Retirar los encabezados `Sesiones` y `Finanzas` del sidebar.
- Mostrar Calendario, Asistencias, Estudiantes, Profesores, Resumen financiero,
  Pagos, Documentos y Transacciones como enlaces directos del mismo nivel que
  Personas.
- Retirar el panel propio de Sesiones y mantener su URL como redirección
  compatible al Calendario, conservando los filtros del querystring.
- Mover al final del Panel principal los bloques Estudiantes con deuda,
  Estudiantes con más asistencia y Alumnos con clases disponibles.
- Mantener Configuración como el único grupo colapsable y final.
- Iniciar cerrados los filtros locales de Sesiones registradas y Personas en
  todos los tamaños de pantalla.

## Alternativas consideradas

- Mantener los grupos y solo ocultar sus títulos: conserva una jerarquía visual
  que ya no representa el uso esperado.
- Crear otro panel de inicio: se descarta porque la ruta `/` ya es el Panel
  transversal y debe concentrar esta lectura.
- Eliminar la URL histórica de Sesiones: se descarta para no romper marcadores o
  enlaces existentes.

## Consecuencias

- El menú tiene más enlaces visibles, pero elimina aperturas y niveles
  intermedios.
- `Resumen financiero` conserva la página financiera sin competir con el nombre
  del Panel principal.
- El cálculo del seguimiento estudiantil queda en
  `plataformaelemental.dashboard` y respeta sus alcances por organización.
- La decisión debe revisarse si el número de destinos directos vuelve difícil
  recorrer el menú o si aparecen dominios con muchas páginas operativas.

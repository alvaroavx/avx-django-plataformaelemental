# ADR 0017: Presentar el feedback transitorio como notificaciones flotantes

Fecha: 2026-10-12
Estado: Aceptada
Decisor: Álvaro

## Contexto

Los mensajes posteriores a una acción se renderizaban inline antes del contenido
principal. Al aparecer desplazaban toda la página y alteraban la posición de los
controles que la persona estaba usando.

## Alternativas descartadas

- Mantener los mensajes inline: conserva el salto de contenido que origina el cambio.
- Usar un modal: bloquea la tarea y exige una interacción desproporcionada para feedback breve.
- Convertir todos los avisos Bootstrap en notificaciones: haría desaparecer errores de formulario e instrucciones que deben permanecer visibles.

## Decisión

Los mensajes transitorios de Django se presentan apilados en la esquina inferior
derecha, entran y salen por el borde derecho, permiten cierre manual y no ocupan
espacio dentro del flujo de la página. Éxito e información duran diez segundos;
advertencias y errores, veinte. El temporizador se pausa con puntero o foco.

Los avisos contextuales, estados vacíos, conflictos y errores de formulario
permanecen inline.

## Consecuencias asumidas

- El feedback deja de desplazar el contenido y mantiene las variantes visuales existentes.
- Las notificaciones necesitan JavaScript para desaparecer automáticamente; sin él permanecen visibles y cerrables solo cuando el script está disponible.
- Varias notificaciones pueden ocupar temporalmente parte de la esquina inferior derecha.

## Condiciones de revisión

Revisar duración o ubicación si pruebas de uso muestran que las notificaciones se
pierden, ocultan acciones persistentes o interfieren con tecnologías de asistencia.

# ADR 0010: seguimiento del Panel plegable en móvil

- Estado: vigente
- Fecha: 2026-10-02
- Decisor: Álvaro

## Contexto

Los tres bloques de seguimiento estudiantil ubicados al final del Panel producen
un recorrido vertical largo en pantallas pequeñas. Su información sigue siendo
útil, pero no requiere permanecer expandida durante toda visita al inicio.

## Alternativas descartadas

- Ocultar los bloques en responsive: reduce el desplazamiento a costa de quitar
  información operacional disponible actualmente.
- Mantener las tablas siempre abiertas: conserva acceso inmediato, pero mantiene
  el exceso de desplazamiento que originó la decisión.

## Decisión

Estudiantes con deuda, Estudiantes con más asistencia y Alumnos con clases
disponibles se muestran como superficies plegables cerradas inicialmente en
responsive y abiertas en escritorio. El encabezado completo opera como control
y utiliza la jerarquía tipográfica, superficie y espaciado del Panel.

## Consecuencias asumidas

En móvil hace falta una acción adicional para consultar cada tabla. El contenido,
los enlaces, el orden y los permisos no cambian. El control nativo conserva
operación con teclado y comunica su estado expandido o contraído.

## Condiciones de revisión

Revisar si el uso frecuente demuestra que alguno de los tres bloques debe iniciar
abierto o si conviene recordar el estado elegido durante la navegación.

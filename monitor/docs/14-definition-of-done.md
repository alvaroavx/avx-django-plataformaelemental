# Definition of Done

Una tarea de `monitor` esta terminada cuando:

- Cumple el criterio de aceptacion acordado.
- No modifica archivos fuera de `monitor/` salvo aprobacion explicita.
- Tiene tests proporcionales al riesgo.
- Ejecuta `python manage.py check` sin errores.
- Ejecuta `python manage.py test monitor` si aplica.
- Actualiza documentacion local si cambio comportamiento, modelo o UI.
- Funciona en mobile y desktop para la necesidad afectada.
- Maneja estados vacios y errores esperados.
- No duplica responsabilidades de otras apps.

Para UI:
- Sin textos cortados.
- Sin controles inaccesibles en mobile.
- Sin tablas obligatorias para tareas principales en pantallas pequenas.

Para backend:
- Sin red externa real en tests.
- Timeouts explicitos en llamadas externas.
- Errores controlados y visibles para el usuario.

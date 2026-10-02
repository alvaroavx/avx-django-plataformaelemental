# ADR 0009: acciones de asistencia según el espacio disponible

- Estado: en revisión
- Fecha: 2026-10-02
- Decisor: Álvaro
- Reemplaza: ADR 0008

## Contexto

La primera reducción móvil confirmó que Estado, Guardar y Hora no aportan a la
operación real de esta tabla. Aun así, mostrar Motivo, Liberar y Eliminar dentro
de cada fila ocupa demasiado ancho y compite con el nombre de la persona.

## Decisión

La tabla administrativa muestra únicamente Persona, Estado de pago y Acciones
en escritorio y móvil. No ofrece desde esta vista el selector de estado, Guardar
ni la hora de registro.

En móvil, Acciones se representa con un botón de tres puntos verticales que abre
un modal reutilizable. El modal contiene Liberar, con icono y captura de motivo,
y Eliminar, con icono y texto. Si la clase ya está liberada, la acción equivalente
es Revertir liberación.

En escritorio, Motivo, Liberar o Revertir liberación y Eliminar permanecen en
línea, con la misma nomenclatura e iconografía del modal.

## Consecuencias asumidas

La edición de estados de asistencia deja de exponerse en la tabla administrativa,
pero el modelo, los estados históricos y los servicios existentes no se eliminan.
Las acciones conservan sus permisos y los mismos nombres de operación enviados
al servidor.

## Condiciones de revisión

La composición debe probarse visualmente con nombres largos y ambos estados de
pago. Una decisión posterior podrá evaluar la eliminación de Ausente y
Justificada del dominio solo después de revisar datos históricos y consumidores.

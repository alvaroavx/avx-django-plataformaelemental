# Ronda funcional Profesor sobre desarrollo

Fecha: 2026-08-16  
Entorno: base PostgreSQL de desarrollo configurada en `.env.dev`  
Alcance: navegación móvil y mutaciones reales con dos cuentas Profesor, sin crear
una base adicional y sin intervenir producción.

## Método

Se extendió y reutilizó `scripts/e2e/profesor_operacion.js`. Cada recorrido usó
una sesión Django efímera creada para la cuenta existente y eliminada al terminar;
no se cambiaron contraseñas ni se conservaron cookies o perfiles de navegador.
Las capturas se deshabilitaron porque las pantallas contienen datos personales de
la base de desarrollo. La evidencia durable son los JSON sanitizados y este
informe.

Se ejecutaron dos contextos de 390 x 844 px:

- Profesor A: Espacio Elementos, disciplina circense asignada.
- Profesora B: Latin Rengo, disciplina asignada. Su rol administrativo se
  desactivó solo durante las verificaciones de Profesor puro y quedó restaurado.

La autenticación Google real no se completó: se abrió el flujo para login manual,
pero no llegó un callback al servidor local. Por ello esta ronda prueba la
operación y autorización posterior a autenticación, no OAuth de punta a punta.

## Resultado funcional

| Flujo | Elementos | Latin Rengo | Resultado |
| --- | ---: | ---: | --- |
| Inicio, sesiones, alumnos y pagos con organización explícita | 200 | 200 | Pasa |
| Sesión asignada visible | Sí | Sí | Pasa |
| Búsqueda y alta de asistente del roster operativo | 0 → 1 | 1 → 2 | Pasa |
| Estado de asistencia guardado y persistente | Sí | Sí | Pasa |
| Crear persona desde el panel y matricularla en la organización/disciplina | Sí | Sí | Pasa desde `Alumnos` |
| Registrar pago individual | Pago 102 | Pagos 103 y 104 | Pasa |
| Transacción única, mismo monto y organización | Sí | Sí | Pasa, 3 de 3 |
| Mantener alumnos sin pago durante agosto | 12 | 13 | Pasa |
| Crear una sesión futura y liberar la sesión completa | Sí | Sí | Pasa |
| Cerrar y volver a abrir una sesión asignada | Sí | Sí | Pasa; queda auditado |
| Quitar un asistente como Profesor puro | 403 | 403 | No implementado |
| Crear una persona directamente dentro de la sesión | 403 | 403 | No implementado |
| Liberar la clase individual de un alumno | 403 | 403 | No implementado |
| Editar un pago como Profesor puro | 403 | 403 | No implementado |
| Eliminar/revertir un pago como Profesor puro | 403 | 403 | No implementado |

La eliminación contable existente es una reversa, no un borrado físico. Esa ruta
y la edición siguen restringidas a administración; el espacio Profesor no muestra
los controles. No se intentó ampliar permisos durante una tarea de prueba.

## Autorización e aislamiento

- Las superficies globales de Finanzas y Organizaciones respondieron `403`.
- Un identificador de sesión o pago perteneciente a la otra organización
  respondió `404` indistinguible.
- Los POST manipulados para quitar asistencia, liberar una clase individual,
  editar o revertir un pago respondieron `403` y no escribieron datos.
- Cambiar el estado de una sesión propia sí fue aceptado; ambas sesiones usadas
  terminaron nuevamente `abierta`.
- El rol `ADMIN` de la profesora Latin Rengo fue verificado activo al finalizar.

## Datos de prueba que quedaron en desarrollo

Por instrucción se conservaron las mutaciones:

- 2 personas creadas por los recorridos principales, cada una con rol Estudiante
  y matrícula operativa únicamente en su organización y disciplina objetivo.
- 1 persona adicional creada durante un diagnóstico inicial que se ejecutó con
  el rol administrativo todavía activo. Ese intento no se usa como evidencia de
  autorización Profesor y se deja identificado como dato de diagnóstico.
- 3 asistencias en las dos sesiones inspeccionadas.
- 3 pagos de prueba, cada uno enlazado a una transacción distinta, del mismo monto
  y organización.
- 3 sesiones futuras creadas y luego canceladas con `LiberacionSesion`; una
  proviene del primer intento de recorrido Latin Rengo.
- Relaciones operativas activadas de forma explícita y auditada para hacer el
  piloto: 2 asignaciones docentes históricas revisadas y 24 matrículas históricas
  revisadas. Permanecen inactivas 5 asignaciones docentes y 58 matrículas
  históricas que no se necesitaron.

## Incidencia de esquema encontrada

La base de desarrollo había aplicado una versión precommit de
`asistencias.0004`: el historial la mostraba aplicada, pero faltaban los campos
que distinguen relaciones históricas y revisadas. Se añadió y ejecutó
`asistencias.0005_reparar_schema_0004_aplicada_precommit`. La reparación dejó
inactivas las relaciones sin actor explícito y es un no-op cuando `0004` correcta
ya creó el esquema. No se reconstruyó la base ni se creó otra.

## Archivos de evidencia

- `profesor-elementos/resultado.json`: recorrido completo Elementos.
- `profesora-latin/resultado.json`: recorrido completo Latin Rengo.
- `profesora-latin-pago/resultado.json`: pago dirigido a una asistente agregada.
- `verificacion.json`: matriz sanitizada de autorización e invariantes finales.

## Conclusión

La ronda es parcialmente satisfactoria. El flujo existente cubre creación y
liberación de sesiones completas, asistentes, estados, alta de alumnos y pagos
con transacción, manteniendo aislamiento organizacional. No cumple aún las cuatro
capacidades solicitadas para Profesor puro: quitar asistentes, liberar una clase
individual, editar pagos y revertir pagos. El alta de persona tampoco está
integrada en la pantalla de sesión, aunque sí funciona desde el módulo Alumnos.


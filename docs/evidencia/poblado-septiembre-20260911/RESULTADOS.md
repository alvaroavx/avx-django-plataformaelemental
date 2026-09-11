# Poblado sintético de septiembre de 2026

Fecha de ejecución: 2026-09-11  
Entorno: desarrollo local (`DEBUG=True`)  
Marcador: `poblado_mes_pruebas`

## Alcance

Se pobló septiembre de 2026 con información sintética para visualizar el dashboard y los flujos operacionales sin incorporar datos personales en esta evidencia. El comando trabaja dentro de una transacción, exige entorno de desarrollo y reconoce exclusivamente sus propios registros mediante un marcador estable.

## Vista previa

- 12 sesiones.
- 25 registros de asistencia.
- 18 pagos previstos.

## Resultado aplicado

- 12 sesiones.
- 25 asistencias: 19 presentes, 2 ausentes y 4 justificadas.
- 7 matrículas vinculadas a los escenarios.
- 2 planes de pago sintéticos.
- 18 pagos por 72 clases y un total de $811.200 CLP.
- 18 transacciones de ingreso vinculadas por el servicio operacional de pagos.
- 19 asistencias consumidas y 6 con deuda, sin asistencias pendientes.

El contador explícito `deudas_imputadas` del comando fue 0 porque las señales del dominio realizaron la imputación durante la creación de cada pago. La verificación posterior de la base confirmó el estado consumido/deuda indicado arriba.

## Seguridad y límites

- Ejecución limitada a la base de desarrollo local.
- Sin migraciones de esquema.
- Sin commit, push ni despliegue.
- Los registros creados se identifican por el marcador del comando y la clave de idempotencia de cada pago.

## Idempotencia

Una segunda ejecución del comando actualizó las 12 sesiones y las 25 asistencias administradas por el marcador, sin crear registros nuevos: 0 sesiones, 0 asistencias, 0 matrículas, 0 bloques, 0 planes y 0 pagos adicionales. Los 18 pagos existentes fueron reconocidos por sus claves de idempotencia.

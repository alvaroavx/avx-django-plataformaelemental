# Observabilidad

Fecha de actualizacion: 2026-05-11

## Proposito
Este documento define como debe crecer la observabilidad interna de Plataforma Elemental.

La app `monitor` puede crecer, pero no debe transformarse en una segunda fuente de verdad.

## Estado Actual
- Existe app `monitor`.
- Ruta base: `/monitor/`.
- Vista inicial protegida por autenticacion.
- No tiene modelos propios.
- Consume navegacion compartida y filtros globales cuando aplique.

## Principio
`monitor` observa datos de apps duenias.

No debe:
- duplicar modelos,
- recalcular reglas complejas de negocio si ya existen selectors/services,
- escribir datos operativos,
- reemplazar dashboards propios de apps cuando el indicador es local.

## Fuentes De Datos
Fuentes duenias:
- `personas`: personas, organizaciones, roles.
- `asistencias`: sesiones, asistencias, disciplinas.
- `finanzas`: pagos, deuda, documentos, transacciones.
- `api`: uso externo, autenticacion y salud de endpoints cuando exista instrumentacion.

Regla:
- Si un indicador cruza apps, su criterio de calculo debe quedar documentado.

## Indicadores Candidatos

### Operacion academica
- sesiones programadas del periodo,
- sesiones completadas,
- sesiones canceladas,
- estudiantes activos con asistencia,
- profesores con carga del periodo.

### Cobranza operacional
- estudiantes con deuda,
- clases disponibles,
- pagos del periodo,
- asistencias pendientes de imputacion.

### Finanzas / contabilidad
- documentos tributarios sin contraparte,
- documentos sin transaccion asociada,
- transacciones sin documento cuando corresponda,
- egresos/ingresos por categoria.

### Sistema
- resultado del ultimo deploy, si se persiste o consulta externamente,
- estado de checks internos,
- sesiones expiradas/activas si se decide exponer ese dato de forma segura.

## Reglas Para Nuevos Indicadores
- Preferir selectors existentes.
- Si el indicador necesita calculo nuevo, crear selector/service en la app duena.
- `monitor` solo orquesta lectura y render.
- No crear tablas espejo.
- No cachear indicadores sin definir invalidacion.
- Mantener filtros globales `periodo_mes`, `periodo_anio` y `organizacion`.

## Alertas
No hay sistema formal de alertas en el proyecto.

Antes de agregar alertas:
- definir evento,
- definir severidad,
- definir canal,
- evitar ruido,
- registrar responsable operativo.

## Logging
Estado actual:
- No hay estrategia documentada de logging estructurado.

Regla futura:
- Logs de errores tecnicos deben ir a infraestructura.
- Eventos de negocio criticos no deben depender solo de logs; deben quedar persistidos en modelos duenos cuando sean parte del dominio.

## Relacion Con Seguridad
No exponer en `monitor`:
- secretos,
- tokens,
- API keys,
- detalles sensibles de usuarios,
- archivos tributarios completos sin control de acceso.

## Deuda
- Falta definir indicadores minimos de produccion.
- Falta decidir si se usara logging estructurado.
- Falta definir si `monitor` tendra endpoints API propios o solo HTML interno.
- Falta criterio de retencion si algun dia se persisten metricas.

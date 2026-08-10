# Evidencia local — Operación Profesor

Fecha: 2026-08-09
Entorno: checkout y PostgreSQL local de desarrollo autorizados.
Viewport navegador: 390 × 844 px.

## Navegador

Recorrido Chrome headless/Puppeteer con usuario y datos marcados `E2E Profesor
20260809`. OAuth estuvo desactivado únicamente en el proceso local del servidor
para permitir login con contraseña. No se modificaron settings versionados ni el
flujo Google.

| Pantalla/control | Resultado |
| --- | --- |
| `/profesor/` | 200; tablero, próxima sesión y cuatro acciones rápidas |
| `/profesor/sesiones/` | 200; hoy, futuras, históricas, estados y liberación |
| `/profesor/alumnos/` | 200; solo roster de clase propia |
| `/profesor/pagos/` | 200; pago, transacción y glosa mensual |
| Selector masivo | 10 alumnos agregados por búsqueda + `Enter`; foco vuelve al buscador |
| Asistencia | Se agregó un quinto asistente, se corrigió a justificada y persistió tras recargar |
| Alta de alumno | Alumno creado con correo válido y visible en el roster propio |
| Pago individual | Pago creado desde móvil y detalle confirmó su transacción asociada |
| Sesión futura | Sesión creada y luego liberada con motivo desde móvil |
| Barra inferior | 4 destinos de 64 px de alto |
| Acciones rápidas | 4 acciones de 62 px de alto |
| `/finanzas/` | 403 |
| `/personas/organizaciones/` | 403 |
| `/admin/` | redirige a `/admin/login/`; profesor no entra al admin |

Capturas:

- [Inicio móvil](01-inicio-mobile.png)
- [Sesiones móvil](02-sesiones-mobile.png)
- [Alumnos móvil](03-alumnos-mobile.png)
- [Pagos móvil](04-pagos-mobile.png)
- [Selector de lote móvil](05-pago-masivo-selector-mobile.png)
- [Asistencia persistida](06-asistencia-persistida-mobile.png)
- [Pago y transacción](07-pago-transaccion-mobile.png)
- [Sesión liberada](08-sesion-liberada-mobile.png)

Durante el segundo recorrido se detectó que las fechas e identificadores
idempotentes iniciales no llegaban al HTML de los formularios GET. Se corrigió
el uso de `Form.initial` y se agregó cobertura de regresión focalizada.

El navegador registró como errores de consola únicamente las respuestas
intencionales 403 del gate y el favicon raíz inexistente (404). No hubo error de
JavaScript en las pantallas operativas recorridas.

## Pruebas automatizadas focalizadas

- Matriz nueva `asistencias.test_operacion_profesor`: alta de alumno, asignación,
  creación/liberación de sesión, autorización directa, asistencia, pago individual,
  vínculo contable, lotes 10/15/20, idempotencia y rollback controlado.
- Regresión `finanzas.tests.PagoMasivoDominioTests`: 7/7.
- Regresión móvil `asistencias.tests.SprintTresJornadaMovilTests`: actualizada a
  matrícula explícita y navegación `/profesor/`.

- Suite completa: 404 tests OK, 12 omitidos, 517,437 s, PostgreSQL local de
  desarrollo reutilizado (`--keepdb`).

Logs conservados:

- [Suite completa aprobada](logs/suite-completa-ok.log)
- [Pruebas focalizadas aprobadas](logs/tests-focalizados-ok.log)
- [Suite inicial con regresiones detectadas](logs/suite-inicial-fallos.log)

Los recorridos ad hoc usados en este corte se generalizaron sin credenciales en
`scripts/e2e/profesor_operacion.js`. Su contrato y variables están inventariados
en [Artefactos de trabajo](../../proceso/ARTEFACTOS.md).

## Evidencia pendiente externa

No ejecutado: login real Google con cuenta QA, traza OAuth y recorrido en un QA
desplegado. Esa evidencia no puede sustituirse con `force_login` ni login local.

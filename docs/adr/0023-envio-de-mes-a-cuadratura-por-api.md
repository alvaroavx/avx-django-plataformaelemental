# ADR 0023: envío de un mes a Cuadratura por su API y bloqueo del mes enviado

- Estado: aceptada
- Fecha: 2026-10-12
- Decisor: Álvaro

## Contexto

Para pasar un mes a Cuadratura había que descargar el JSON `elemental-cuadratura-v1`
y que alguien lo cargara a mano. Cuadratura ahora ofrece una API v1 genérica (ADR 0005
de Cuadratura) con su propio contrato `cuadratura-operations-v1`. Esa API es de
Cuadratura y está pensada para cualquier sistema, así que es Elemental quien se adapta
a ella. Además, si un mes se sigue editando después de enviarlo, Elemental y
Cuadratura quedan con datos distintos.

## Decisión

- **Botón «Enviar a Cuadratura»** en `/finanzas/preparar-mes/` (permiso
  `exportar_datos`), con una casilla obligatoria que confirma el bloqueo del mes.
- **El envío (`finanzas/services/cuadratura_api.py`):**
  1. reutiliza `prepare_month` y traduce el resultado al contrato genérico;
  2. consulta `GET /api/v1/` y elige la organización destino por RUT;
  3. hace `POST` del lote.
- **`batch_id` sale del contenido:** es el SHA-256 del documento sin `generated_at`.
  Reenviar el mismo mes sin cambios es reconocido por Cuadratura como el mismo lote.
- **Sin confirmación automática:** el lote queda en revisión en Cuadratura y una
  persona lo confirma allá. Elemental guarda el acuse (id, estado y enlace de revisión).
- **Condiciones para enviar:**
  - el mes terminó;
  - la integración está configurada;
  - la URL usa `https://` (salvo con `DEBUG`);
  - el mes tiene operaciones;
  - no hay pendientes, salvo pagos revertidos.

  Un pendiente bloquea porque, una vez enviado, el mes ya no se puede corregir.
- **Registro de intentos:** cada intento queda en `EnvioCuadratura` y en `AuditLog`.
  Se agregó tras la revisión de la mesa BPO, por el hallazgo H1: una edición durante
  el envío podía divergir de lo enviado.

  | Estado | Cuándo | ¿Bloquea el mes? |
  |---|---|---|
  | `en_curso` | Se crea **antes** de leer los datos y llamar a la API | Sí |
  | `enviado` | Cuadratura respondió `VALIDATED` o `COMMITTED` | Sí, definitivo |
  | `incierto` | El POST salió y no hubo respuesta válida (timeout, 5xx, 429) | Sí, hasta que un reintento termine |
  | `rechazado` | 4xx definitivo o lote `BLOCKED` (incluye 409 `period_already_submitted`) | No |
  | `fallido` | No se transmitieron datos: falló el descubrimiento, la conexión o la organización no está habilitada | No |

  - El bloqueo se evalúa con el **último** intento del mes.
  - Un reintento después de `incierto` manda el mismo contenido (mismo `batch_id`), y
    Cuadratura devuelve el lote existente si ya lo tenía.
  - Un `en_curso` interrumpido pasa a `incierto` tras `2 × timeout + 60 s`.
  - Hay una sola fila `en_curso` o `enviado` por organización y mes (restricción
    única condicional).
- **Seguridad del envío (ADR 0006 de Cuadratura):**
  - cada request lleva el token y una firma Ed25519 hecha con la llave privada de
    `CUADRATURA_API_PRIVATE_KEY_FILE`, generada con `generar_llave_cuadratura` fuera
    del repo y con permisos 600;
  - sin llave, fuera de DEBUG no se puede enviar;
  - no se siguen redirecciones (`allow_redirects=False`);
  - el enlace de revisión solo se guarda si apunta por HTTPS al mismo host de
    Cuadratura (H6).
- **Bloqueo del mes:** un mes `enviado` queda bloqueado.
  - No se pueden crear, editar, revertir ni eliminar pagos con `fecha_pago` en ese
    mes, ni mover un pago desde o hacia él.
  - Tampoco se pueden editar ni eliminar las transacciones enlazadas a esos pagos.
  - Se aplica en `Payment.save/delete` y `Transaction.save/delete`
    (`validar_meses_no_enviados`), con mensajes legibles en los formularios.
  - No hay reenvío ni corrección: si se necesita, se decidirá entonces.
- **Configuración por entorno:** `CUADRATURA_API_URL` (URL base, sin `/api/v1/`),
  `CUADRATURA_API_TOKEN`, `CUADRATURA_API_PRIVATE_KEY_FILE` y
  `CUADRATURA_API_TIMEOUT` (30 s por defecto). El token lo
  emite Cuadratura con `create_api_client --origin-system ELEMENTAL`.

## Alternativas descartadas

- **Enviar el contrato `elemental-cuadratura-v1` por HTTP:** obligaría a Cuadratura a
  aceptar un formato propio de Elemental en su API.
- **Permitir reenvíos y correcciones:** requiere reversas y anulaciones en ambos
  lados, y hoy no hay un caso que lo justifique.
- **Bloquear todo el módulo financiero del mes:** egresos y movimientos no enlazados
  no viajan a Cuadratura, así que bloquearlos no protege nada.

## Consecuencias asumidas

- Desbloquear un mes es un procedimiento de emergencia: un superusuario elimina el
  envío `enviado` desde la base o el shell, coordinado con Cuadratura, y queda en la
  auditoría de base de datos. El admin de Django lo muestra solo en lectura.
- Un pago con `fecha_pago` en un mes enviado no puede registrarse tarde. Habrá que
  registrarlo con fecha del mes en curso.
- La descarga manual del JSON v1 sigue disponible.
- No verificado en producción: falta emitir el token en Cuadratura, configurar las
  variables y comprobar que Elemental llega por red y HTTPS a Cuadratura.

## Verificación

- `finanzas/test_envio_cuadratura.py` (14 pruebas) cubre, además de la firma
  verificada en cada llamada, el bloqueo durante el envío, el estado incierto con
  reintento idéntico, el fallo de conexión que no bloquea, la URL ajena descartada y
  la llave obligatoria. También cubre:
  - el contrato genérico y la estabilidad de `batch_id`;
  - el envío aceptado y el bloqueo en modelo, formularios, reversas y movimientos;
  - el lote bloqueado en Cuadratura;
  - la falta de conexión;
  - la organización no habilitada;
  - las condiciones previas;
  - el pago revertido;
  - la vista con confirmación.
- Validado de punta a punta por HTTP contra Cuadratura local con la organización
  ficticia «Taller Ficticio SpA»: el lote llega `VALIDATED` y un reenvío devuelve el
  mismo lote.

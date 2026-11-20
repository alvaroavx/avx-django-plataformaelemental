# ADR-0025: Profesor registra pagos desde su propio perfil

**Fecha:** 2026-11-16 | **Decidió:** Álvaro | **Estado:** vigente

**Contexto:** La profesora necesita registrar pagos de estudiantes de su
organización desde su perfil. Darle el permiso financiero general también
expondría listados, transacciones, exportaciones, edición, reversas y pagos de
otras organizaciones, capacidades que esta necesidad no requiere.

**Alternativas descartadas:**

- Conceder `operar_pagos` al rol Profesor — también habilitaría el flujo general
  de pagos y sus capacidades asociadas.
- Permitir pagos desde cualquier perfil visible — no garantiza que la profesora
  opere solo su propia organización.

**Decisión:** Una persona autenticada con rol `PROFESOR` activo puede abrir su
propio perfil si selecciona esa organización. Desde allí puede registrar un pago
individual solo para personas activas con rol `ESTUDIANTE` activo y planes
activos de esa misma organización. El servidor fija y valida la organización;
el flujo usa `crear_pago_operacional`, que crea pago, transacción y auditoría
atómicamente. La profesora conserva acceso al flujo acotado de su perfil.

**Ampliación del 19 de noviembre de 2026:** El menú docente incluye **Mis cobros**.
En la organización seleccionada, el profesor puede listar, editar y revertir
los pagos individuales registrados por su cuenta. La edición conserva al
estudiante original y sincroniza la transacción. La reversa conserva el historial
y requiere motivo. Rige el bloqueo de meses enviados a Cuadratura. Los permisos
generales de Finanzas, exportación y pago masivo siguen siendo independientes.

**Consecuencias asumidas:** El profesor puede consultar el padrón activo de
estudiantes de su organización en el selector de pago. El pago aparece en los
flujos financieros autorizados y conserva la cuenta del profesor como actor de
auditoría.

**Condiciones de revisión:** Revisar si la organización requiere limitar la
visibilidad del padrón entre talleres o asignar esta capacidad a profesores
específicos en vez de habilitarla a todo el rol activo.

**Separación de navegación:** **Mis cobros** abre una página dedicada al
registro y gestión de cobros propios. **Mi perfil** reúne la información de
la cuenta autenticada, tanto docente como administrativa. La ficha CRM conserva
las operaciones de administración de personas y roles.

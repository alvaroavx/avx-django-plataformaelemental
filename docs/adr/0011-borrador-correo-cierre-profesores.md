# ADR 0011: borrador individual de correo de cierre para profesores

- Estado: Aceptada
- Fecha: 2026-10-06

## Contexto

Al finalizar el mes, la administración transfiere manualmente el pago a cada
profesor y le envía por correo el comprobante, la asistencia que sustenta el
cálculo y los datos necesarios para emitir su boleta de honorarios. Elemental ya
calcula la remuneración desde asistencias y la tarifa configurada en
`PersonaRol`, pero el texto se componía manualmente.

## Decisión

La lista administrativa `/asistencias/profesores/` ofrece `Preparar correo` en
cada fila para un mes, año y organización concretos.

- Se genera un borrador por profesor, organización y período.
- El sistema no envía correos, no adjunta comprobantes, no registra la
  transferencia y no emite documentos tributarios.
- La remuneración mantiene la regla vigente: asistencias registradas del período
  multiplicadas por `PersonaRol.valor_clase`; retención y líquido se calculan con
  `PersonaRol.retencion_sii`.
- Las sesiones compartidas se incluyen de forma independiente en el borrador de
  cada profesor asignado. No se divide el pago entre profesores.
- Si hay varias disciplinas, cada una se presenta en un bloque separado y
  ordenado. Las sesiones sin registros dicen literalmente `Sin asistentes` y
  las sesiones canceladas permanecen visibles con su estado.
- El asunto contiene una sola disciplina. Se prioriza la que tenga más sesiones
  completadas; en empate, la de más asistencias. Un empate restante se resuelve
  alfabéticamente para que el resultado sea estable. Si no hay sesiones
  completadas, se consideran los bloques disponibles con el mismo desempate.
- El destinatario tributario se obtiene de `Organizacion`: razón social, RUT,
  dirección, comuna y región. Los dos últimos campos se incorporan como datos
  opcionales y aditivos al modelo. El borrador bloquea sus botones de copia si
  faltan datos tributarios o la configuración económica del profesor.
- El nombre usado en el saludo es `Persona.nombres`; no se crea un dato de
  sobrenombre para este alcance.

## Consecuencias

La vista solo prepara contenido copiable en texto enriquecido y texto plano. La
acción humana conserva la revisión final, el envío, la transferencia y la
incorporación del comprobante. La regla vive en un servicio de `asistencias`, de
modo que la lista y la plantilla no recalculan montos ni eligen disciplinas por
su cuenta.

Una futura automatización de envío, comprobantes o cierre contable requiere una
decisión separada y no puede interpretar este borrador como evidencia de pago o
de documento emitido.

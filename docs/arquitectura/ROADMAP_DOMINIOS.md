# Roadmap De Dominios

Fecha de actualizacion: 2026-05-11

## Proposito
Este documento ordena crecimiento futuro por dominio sin convertir el monolito Django en microservicios.

No es backlog detallado. Es una guia para decidir donde deberia vivir una funcionalidad nueva.

## Principio
La plataforma debe seguir creciendo como monolito modular.

Antes de crear una app nueva:
- confirmar que la responsabilidad no pertenece claramente a una app existente,
- evitar duplicar modelos,
- definir app duena de datos,
- definir dependencias permitidas,
- agregar tests de reglas criticas.

## Dominios Vigentes

### Personas / CRM Base
Estado:
- Vigente.

App duena:
- `personas`.

Responsabilidad:
- personas,
- organizaciones,
- roles,
- perfiles administrativos consolidados.

No debe absorber:
- imputacion de pagos,
- contabilidad,
- operacion diaria de asistencia.

### Operacion Academica
Estado:
- Vigente.

App duena:
- `asistencias`.

Responsabilidad:
- disciplinas,
- sesiones,
- asistencia,
- vista operativa diaria.

No debe absorber:
- calculo contable,
- parsing tributario,
- reglas de cobranza implementadas directamente en views/templates.

### Cobranza Operacional
Estado:
- Vigente como subdominio dentro de `finanzas/services/`.

App duena actual:
- `finanzas`.

Responsabilidad:
- planes de pago,
- pagos,
- deuda de clases,
- saldo de clases,
- imputacion contra asistencias.

Criterio futuro:
- Puede seguir dentro de `finanzas` mientras se mantenga separado por services/selectors.
- Evaluar app propia solo si cobranza empieza a tener ciclo de vida claramente independiente de contabilidad.

### Finanzas / Contabilidad
Estado:
- Vigente.

App duena:
- `finanzas`.

Responsabilidad:
- documentos tributarios,
- transacciones,
- categorias,
- reportes para contadora,
- respaldos financieros.

No debe absorber:
- reglas academicas,
- CRM avanzado,
- entrenamiento.

### API Externa
Estado:
- Vigente.

App duena:
- `api`.

Responsabilidad:
- endpoints REST,
- autenticacion API,
- throttling,
- contratos externos.

No debe contener:
- reglas de negocio nuevas que no existan en apps/services duenos.

### Monitor / Observabilidad Interna
Estado:
- Inicial.

App duena:
- `monitor`.

Responsabilidad:
- dashboards internos,
- indicadores operativos,
- salud funcional de la plataforma.

No debe duplicar:
- modelos,
- reglas financieras,
- reglas academicas.

Detalle:
- [docs/arquitectura/OBSERVABILIDAD.md](OBSERVABILIDAD.md)

## Dominios Futuros

### Entrenamiento
Estado:
- Futuro.

Posible responsabilidad:
- planes de entrenamiento,
- rutinas,
- progresiones,
- evaluaciones fisicas,
- objetivos por estudiante.

Relacion probable:
- consume `personas` para estudiantes/profesores,
- puede consumir `asistencias` para continuidad,
- no debe vivir dentro de `finanzas`.

Criterio de app:
- Crear app propia solo cuando existan modelos persistentes de entrenamiento.

### Contabilidad Avanzada
Estado:
- Futuro.

Posible responsabilidad:
- conciliacion formal,
- libro de compras/ventas,
- reglas contables mas estrictas,
- exportaciones para contadora,
- cierres mensuales.

Relacion probable:
- evoluciona desde `finanzas`,
- puede requerir separar cobranza operacional de contabilidad,
- no debe mezclarse con parsing tributario dentro de views.

Criterio de app:
- Mantener dentro de `finanzas` hasta que existan reglas contables propias y estables.

### CRM Avanzado
Estado:
- Futuro.

Posible responsabilidad:
- seguimiento comercial,
- leads,
- comunicaciones,
- historial de contactos,
- segmentacion.

Relacion probable:
- extiende `personas`,
- no debe alterar `Persona` para cada necesidad comercial menor,
- podria requerir entidades propias como `Contacto`, `Interaccion` o `Campania`.

Criterio de app:
- Crear app propia si aparecen flujos comerciales que no sean simples atributos de persona.

## Orden Recomendado
1. Estabilizar PostgreSQL en produccion.
2. Reducir deuda legacy de `database`.
3. Completar separacion interna de `finanzas`.
4. Formalizar permisos/roles antes de exponer mas escrituras.
5. Hacer crecer `monitor` con indicadores sin duplicar modelos.
6. Evaluar nuevas apps solo cuando haya modelos persistentes claros.

## Anti-Patrones
- Crear app nueva solo para una vista.
- Agregar campos a `Persona` para resolver cada flujo futuro.
- Mezclar cobranza, contabilidad y documentos tributarios en una misma view.
- Hacer que `monitor` tenga modelos espejo.
- Implementar reglas de negocio directamente en templates.

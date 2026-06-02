# Deuda Tecnica Activa

Fecha de actualizacion: 2026-05-11

## Proposito
Este documento mantiene visible la deuda tecnica activa del proyecto.

No es backlog de features. Es inventario de riesgos tecnicos conocidos que afectan mantenibilidad, migraciones, datos, seguridad operativa o velocidad de cambio.

## Criterio De Uso
- Registrar deuda cuando se decide no resolverla en el cambio actual.
- Mantener descripcion concreta, impacto y accion recomendada.
- Eliminar o actualizar una deuda cuando se resuelve.
- No usar este documento para justificar deuda nueva sin test ni plan.

## Deuda Alta

### Retiro De `database` Legacy
Estado:
- Resuelta en Sprint 14B.

Impacto:
- La app legacy fue retirada de `INSTALLED_APPS`.
- Las migraciones vigentes de `personas`, `asistencias` y `finanzas` ya no dependen de nodos `database`.
- La carpeta `database/` fue eliminada del codigo versionado.

Accion recomendada:
- Mantener tests de instalacion limpia y `migrate --plan` antes de tocar migraciones futuras.
- No reintroducir imports o modelos bajo `database`.

Documentos relacionados:
- [docs/arquitectura/MODELO_DATOS.md](MODELO_DATOS.md)
- [docs/operacion/AUDITORIA_SQLITE_POSTGRESQL.md](../operacion/AUDITORIA_SQLITE_POSTGRESQL.md)

### Inventario De Reglas Con Referencias Obsoletas
Estado:
- Mitigada.

Impacto:
- [docs/arquitectura/INVENTARIO_REGLAS_NEGOCIO.md](INVENTARIO_REGLAS_NEGOCIO.md) fue reducido a marcador pendiente de regeneracion para no mantener enlaces obsoletos.
- Falta reconstruir el inventario desde codigo vigente.

Accion recomendada:
- Regenerar el inventario desde codigo vigente.
- Mantener referencias a services/selectors actuales.

### Produccion PostgreSQL Pendiente De Estabilizacion
Estado:
- Mitigada.

Impacto:
- Desarrollo y produccion operan con PostgreSQL.
- Los cambios de migracion profundos siguen requiriendo respaldo y validacion en copia de datos antes de deploy.

Accion recomendada:
- Confirmar restauracion de backup con `pg_restore` en entorno controlado.
- Mantener backups previos a migraciones productivas.

## Deuda Media

### Logica De Negocio Todavia En Views
Estado:
- Activa.

Impacto:
- Aumenta acoplamiento HTTP/dominio.
- Hace mas dificil testear reglas sin renderizar vistas.
- En `finanzas` ya hubo una primera extraccion, pero quedan flujos complejos, especialmente documentos tributarios/importacion.

Accion recomendada:
- Continuar extraccion incremental hacia selectors y services.
- Siguiente candidato natural: helpers puros y flujo de documentos tributarios en `finanzas/services/documentos.py`.
- No mover todo de golpe.

### Frontera Interna De `finanzas`
Estado:
- Activa.

Impacto:
- `finanzas` contiene cobranza operacional y finanzas/contabilidad.
- Si crece sin separacion interna, pagos, documentos, parsing e imputacion pueden volver a mezclarse en views.

Accion recomendada:
- Mantener subdominios documentados en [docs/apps/FINANZAS.md](../apps/FINANZAS.md).
- Usar `finanzas/services/imputacion.py`, `pagos.py`, `reportes.py` y futuros `documentos.py`.
- Evitar app nueva hasta que el monolito modular lo justifique claramente.

### Constraints De Integridad Pendientes
Estado:
- Activa.

Impacto:
- Algunas reglas viven en formularios/services y no en base de datos.
- Ejemplo: un `DocumentoTributario` no deberia asociar simultaneamente `persona_relacionada` y `organizacion_relacionada`, pero la regla debe mantenerse desde capa de aplicacion.

Accion recomendada:
- Evaluar constraints con PostgreSQL cuando las reglas esten estables.
- Agregar tests antes de promover reglas a constraints.

### CI Y Deploy En Un Flujo Unico
Estado:
- Activa controlada.

Impacto:
- El workflow prueba y despliega desde el mismo archivo.
- Para la escala actual es aceptable, pero mezcla responsabilidades cuando produccion tenga datos mas criticos.

Accion recomendada:
- Mantenerlo simple mientras el riesgo sea bajo.
- Separar CI de deploy productivo cuando PostgreSQL en produccion sea la fuente critica y haya mas ramas/ambientes.

## Deuda Baja

### Documentacion Operativa Larga
Estado:
- Activa controlada.

Impacto:
- Algunos documentos operativos son extensos porque capturan auditorias completas.
- Pueden ser utiles como evidencia, pero no siempre como guia rapida.

Accion recomendada:
- Mantener auditorias completas en `docs/operacion/`.
- Mantener `PLATAFORMA.md` como resumen ejecutivo.
- Crear documentos especializados cuando una regla transversal crezca demasiado.

## Regla De Cierre
Una deuda puede eliminarse de este documento solo si:
- el codigo fue corregido,
- los tests relevantes pasan,
- la documentacion duenia quedo actualizada,
- y el cambio no dejo una deuda equivalente con otro nombre.

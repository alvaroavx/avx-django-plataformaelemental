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

### `database` Como Namespace Legacy
Estado:
- Activa.

Impacto:
- Ensucia el modelo mental del dominio.
- `database/models.py` reexporta modelos reales desde apps duenias.
- Las migraciones historicas de `personas`, `asistencias` y `finanzas` dependen de nodos `database`.
- Borrar la carpeta sin limpiar el grafo puede romper `migrate` en bases nuevas.

Accion recomendada:
- Primero eliminar imports runtime hacia `database`.
- Luego dejar `database` como app solo de compatibilidad de migraciones.
- Despues de estabilizar PostgreSQL en produccion, evaluar squash/refactor de migraciones para eliminarla completamente.

Documentos relacionados:
- [docs/arquitectura/MODELO_DATOS.md](MODELO_DATOS.md)
- [docs/operacion/AUDITORIA_SQLITE_POSTGRESQL.md](../operacion/AUDITORIA_SQLITE_POSTGRESQL.md)

### Inventario De Reglas Con Referencias Obsoletas
Estado:
- Activa.

Impacto:
- [docs/arquitectura/INVENTARIO_REGLAS_NEGOCIO.md](INVENTARIO_REGLAS_NEGOCIO.md) contiene referencias historicas a `database/models.py` con lineas que ya no representan el codigo actual.
- Puede confundir a Codex o a un humano antes de tocar reglas de negocio.

Accion recomendada:
- Regenerar el inventario desde codigo vigente.
- Reemplazar referencias a `database/models.py` por modelos reales en `personas`, `asistencias` y `finanzas`.
- Mantener referencias a services/selectors actuales.

### Produccion PostgreSQL Pendiente De Estabilizacion
Estado:
- Activa.

Impacto:
- Desarrollo ya opera con PostgreSQL, pero la decision de eliminar legacy de migraciones debe esperar validacion productiva.
- Cambios de migracion profundos antes de estabilizar produccion aumentan riesgo de deploy y recuperacion.

Accion recomendada:
- Publicar y validar PostgreSQL en produccion con backups previos a migraciones.
- Confirmar restauracion de backup con `pg_restore` en entorno controlado.
- Recien despues evaluar limpieza fuerte de migraciones legacy.

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

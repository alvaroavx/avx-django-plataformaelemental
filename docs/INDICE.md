# INDICE

Fecha de actualizacion: 2026-08-10

Este archivo es el mapa de la documentacion viva del repo.

Para una ruta de lectura antes de tocar codigo, usar [docs/ONBOARDING_CODEX.md](https://github.com/alvaroavx/avx-django-plataformaelemental/blob/main/docs/ONBOARDING_CODEX.md).

## Raiz
- [AGENTS.md](https://github.com/alvaroavx/avx-django-plataformaelemental/blob/main/AGENTS.md): reglas operativas del repo.
- [README.md](https://github.com/alvaroavx/avx-django-plataformaelemental/blob/main/README.md): resumen humano y puesta en marcha.

## Docs
- [docs/ESTADO_ACTUAL.md](ESTADO_ACTUAL.md): fotografia verificable del producto, validaciones, riesgos y asuntos por resolver.
- [docs/ONBOARDING_CODEX.md](https://github.com/alvaroavx/avx-django-plataformaelemental/blob/main/docs/ONBOARDING_CODEX.md): ruta de lectura y trabajo para Codex.
- [docs/SECURITY.md](https://github.com/alvaroavx/avx-django-plataformaelemental/blob/main/docs/SECURITY.md): higiene de secretos y reglas de seguridad del repositorio.

## Arquitectura
- [docs/arquitectura/PLATAFORMA.md](https://github.com/alvaroavx/avx-django-plataformaelemental/blob/main/docs/arquitectura/PLATAFORMA.md): fotografia ejecutiva de arquitectura.
- [docs/arquitectura/ROADMAP_DOMINIOS.md](https://github.com/alvaroavx/avx-django-plataformaelemental/blob/main/docs/arquitectura/ROADMAP_DOMINIOS.md): crecimiento futuro por dominio.
- [docs/arquitectura/DEUDA_TECNICA.md](https://github.com/alvaroavx/avx-django-plataformaelemental/blob/main/docs/arquitectura/DEUDA_TECNICA.md): deuda tecnica activa.
- [docs/arquitectura/INVENTARIO_REGLAS_NEGOCIO.md](https://github.com/alvaroavx/avx-django-plataformaelemental/blob/main/docs/arquitectura/INVENTARIO_REGLAS_NEGOCIO.md): inventario de reglas de negocio.
- [docs/arquitectura/MODELO_DATOS.md](https://github.com/alvaroavx/avx-django-plataformaelemental/blob/main/docs/arquitectura/MODELO_DATOS.md): modelo relacional e integridad.
- [docs/arquitectura/NAVEGACION_Y_CONTEXTO.md](https://github.com/alvaroavx/avx-django-plataformaelemental/blob/main/docs/arquitectura/NAVEGACION_Y_CONTEXTO.md): filtros globales y contexto compartido.
- [docs/arquitectura/PERMISOS_Y_ROLES.md](https://github.com/alvaroavx/avx-django-plataformaelemental/blob/main/docs/arquitectura/PERMISOS_Y_ROLES.md): permisos y roles.
- [docs/arquitectura/OBSERVABILIDAD.md](https://github.com/alvaroavx/avx-django-plataformaelemental/blob/main/docs/arquitectura/OBSERVABILIDAD.md): observabilidad futura y estado archivado de `monitor`.

## ADR
- [docs/adr/0001-autenticacion-google-y-solicitudes-acceso.md](https://github.com/alvaroavx/avx-django-plataformaelemental/blob/main/docs/adr/0001-autenticacion-google-y-solicitudes-acceso.md): decision y gates de seguridad para autenticacion Google y solicitudes de acceso.
- [docs/adr/0002-release-defensivo-asistencias-0005.md](adr/0002-release-defensivo-asistencias-0005.md): rutas, preflight y recuperación forward-only de la reparación defensiva `asistencias.0005`.

## Apps
- [docs/apps/ASISTENCIAS.md](https://github.com/alvaroavx/avx-django-plataformaelemental/blob/main/docs/apps/ASISTENCIAS.md): decisiones de `asistencias`.
- [docs/apps/OPERACION_PROFESOR.md](apps/OPERACION_PROFESOR.md): panel, autorización, pagos y evidencia del espacio profesor.
- [docs/apps/PERSONAS.md](https://github.com/alvaroavx/avx-django-plataformaelemental/blob/main/docs/apps/PERSONAS.md): decisiones de `personas`.
- [docs/apps/FINANZAS.md](https://github.com/alvaroavx/avx-django-plataformaelemental/blob/main/docs/apps/FINANZAS.md): decisiones de `finanzas`.
- [docs/apps/UX.md](https://github.com/alvaroavx/avx-django-plataformaelemental/blob/main/docs/apps/UX.md): navegacion, login y UX responsive de `Elemental Apps`.
- [docs/apps/GRAMATICA_MOVIL_SPRINT2.md](apps/GRAMATICA_MOVIL_SPRINT2.md): especificacion y evidencia del prototipo movil aislado de Sprint 2.
- [docs/apps/PERMISOS_Y_ROLES.md](https://github.com/alvaroavx/avx-django-plataformaelemental/blob/main/docs/apps/PERMISOS_Y_ROLES.md): matriz minima de permisos HTML v1.0.
- [docs/apps/AUDITORIA.md](https://github.com/alvaroavx/avx-django-plataformaelemental/blob/main/docs/apps/AUDITORIA.md): trazabilidad operativa minima de acciones sensibles.
- [docs/apps/ADMIN.md](https://github.com/alvaroavx/avx-django-plataformaelemental/blob/main/docs/apps/ADMIN.md): uso del Django Admin como soporte y diagnostico.
- [docs/apps/API.md](https://github.com/alvaroavx/avx-django-plataformaelemental/blob/main/docs/apps/API.md): decisiones de `api`.
- [docs/apps/MONITOR.md](https://github.com/alvaroavx/avx-django-plataformaelemental/blob/main/docs/apps/MONITOR.md): estado archivado de `monitor`.

## Proceso
- [docs/proceso/DECISIONES.md](https://github.com/alvaroavx/avx-django-plataformaelemental/blob/main/docs/proceso/DECISIONES.md): gobernanza documental y jerarquia de autoridad.
- [docs/proceso/CHECKLIST_CAMBIOS.md](https://github.com/alvaroavx/avx-django-plataformaelemental/blob/main/docs/proceso/CHECKLIST_CAMBIOS.md): checklist de cierre de cambios.
- [docs/proceso/TESTING.md](https://github.com/alvaroavx/avx-django-plataformaelemental/blob/main/docs/proceso/TESTING.md): estrategia de pruebas.
- [docs/proceso/ARTEFACTOS.md](proceso/ARTEFACTOS.md): política, inventario y reglas de reutilización de herramientas y evidencias de trabajo.

## Operacion
- [docs/operacion/DEPLOY.md](https://github.com/alvaroavx/avx-django-plataformaelemental/blob/main/docs/operacion/DEPLOY.md): CI/CD, deploy y rollback.
- [docs/operacion/MIGRACIONES_OPERACION_PROFESOR.md](operacion/MIGRACIONES_OPERACION_PROFESOR.md): semántica histórica, ensayo PostgreSQL, backup/restore, runbook y gate productivo.
- [docs/operacion/AUDITORIA_SQLITE_POSTGRESQL.md](https://github.com/alvaroavx/avx-django-plataformaelemental/blob/main/docs/operacion/AUDITORIA_SQLITE_POSTGRESQL.md): evidencia historica de la migracion; no describe el modelo ni la configuracion actuales.
- [docs/operacion/SEGURIDAD_PRODUCCION.md](https://github.com/alvaroavx/avx-django-plataformaelemental/blob/main/docs/operacion/SEGURIDAD_PRODUCCION.md): seguridad productiva.

## Evidencia vigente

- [Migraciones Operación Profesor 2026-08-10](evidencia/migraciones-operacion-profesor-20260810/RESULTADOS.md): SQL, medición sintética de locks, reporte histórico y restauración probada.
- [Ensayo QA y transición de permisos](evidencia/migraciones-operacion-profesor-20260810/ENSAYO_QA_Y_TRANSICION.md): estado representativo, procedimiento de activación, pruebas omitidas, higiene y veredicto no-go.

## Archivo
- [docs/archivo/MONITOR.md](https://github.com/alvaroavx/avx-django-plataformaelemental/blob/main/docs/archivo/MONITOR.md): inventario y decision de archivo de `monitor`.

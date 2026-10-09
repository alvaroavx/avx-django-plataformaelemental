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
- [docs/arquitectura/OBSERVABILIDAD.md](https://github.com/alvaroavx/avx-django-plataformaelemental/blob/main/docs/arquitectura/OBSERVABILIDAD.md): observabilidad futura.

## ADR
- [docs/adr/0001-autenticacion-google-y-solicitudes-acceso.md](https://github.com/alvaroavx/avx-django-plataformaelemental/blob/main/docs/adr/0001-autenticacion-google-y-solicitudes-acceso.md): decision y gates de seguridad para autenticacion Google y solicitudes de acceso.
- [docs/adr/0002-release-defensivo-asistencias-0005.md](adr/0002-release-defensivo-asistencias-0005.md): rutas, preflight y recuperación forward-only de la reparación defensiva `asistencias.0005`.
- [docs/adr/0003-origen-local-canonico-oauth.md](adr/0003-origen-local-canonico-oauth.md): fija `127.0.0.1:8000` como origen local canónico para evitar callbacks Google obsoletos o no autorizados.
- [docs/adr/0004-mantenedores-en-configuracion.md](adr/0004-mantenedores-en-configuracion.md): separa la operación frecuente de los mantenedores y renombra Django Admin como Administración avanzada.
- [docs/adr/0005-panel-transversal-y-personas.md](adr/0005-panel-transversal-y-personas.md): convierte la portada existente en Panel común por capacidades y retira el Panel separado de Personas.
- [docs/adr/0006-menu-operativo-plano.md](adr/0006-menu-operativo-plano.md): aplana los accesos operativos, retira el panel de Sesiones y concentra su seguimiento estudiantil en el Panel principal.
- [docs/adr/0007-botonera-iconos-detalle-sesion.md](adr/0007-botonera-iconos-detalle-sesion.md): prueba una botonera móvil de una fila, controles equivalentes e iconos accesibles en el detalle de sesión.
- [docs/adr/0008-tabla-asistencia-movil-esencial.md](adr/0008-tabla-asistencia-movil-esencial.md): reduce provisionalmente la tabla móvil a persona, pago y acciones sin alterar todavía los estados del dominio.
- [docs/adr/0009-acciones-asistencia-segun-viewport.md](adr/0009-acciones-asistencia-segun-viewport.md): reemplaza la prueba anterior, simplifica la tabla administrativa en todos los tamaños y concentra las acciones móviles en un modal.
- [docs/adr/0010-seguimiento-panel-plegable-en-movil.md](adr/0010-seguimiento-panel-plegable-en-movil.md): mantiene visible el seguimiento estudiantil en escritorio y lo presenta plegado por defecto en responsive.
- [docs/adr/0011-borrador-correo-cierre-profesores.md](adr/0011-borrador-correo-cierre-profesores.md): define el borrador individual de cierre, su cálculo, agrupación por disciplina y límites operativos.
- [docs/adr/0012-botones-con-icono-y-texto.md](adr/0012-botones-con-icono-y-texto.md): fija la anatomía `[icono] [texto]`, su separación estructural y la copia operable de borradores incompletos.
- [docs/adr/0013-lenguaje-visual-panel-en-vistas-operativas.md](adr/0013-lenguaje-visual-panel-en-vistas-operativas.md): extiende la gramática visual del Panel a Calendario, Asistencias, Estudiantes y Profesores sin reducir su densidad operacional.
- [docs/adr/0014-asistencias-cards-en-mobile.md](adr/0014-asistencias-cards-en-mobile.md): reemplaza el scroll horizontal de sesiones registradas por cards completas y filtrables en mobile.
- [docs/adr/0015-cuadratura-duena-documentacion-fiscal.md](adr/0015-cuadratura-duena-documentacion-fiscal.md): retira de Elemental la documentación fiscal y fija su propiedad en Cuadratura.

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

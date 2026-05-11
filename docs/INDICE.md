# INDICE

Fecha de actualizacion: 2026-05-11

Esta carpeta ordena la documentacion que Codex y el equipo deben tomar en cuenta al trabajar sobre el repo.

## Orden recomendado de lectura
1. [AGENTS.md](https://github.com/alvaroavx/avx-django-plataformaelemental/blob/main/AGENTS.md)
   Reglas operativas del repo y criterios generales de desarrollo.
2. [docs/proceso/DECISIONES.md](https://github.com/alvaroavx/avx-django-plataformaelemental/blob/main/docs/proceso/DECISIONES.md)
   Regla de mantenimiento documental y jerarquia de archivos.
3. [docs/proceso/CHECKLIST_CAMBIOS.md](https://github.com/alvaroavx/avx-django-plataformaelemental/blob/main/docs/proceso/CHECKLIST_CAMBIOS.md)
   Checklist para cerrar cambios sin dejar documentacion falsa o validaciones pendientes.
4. [docs/arquitectura/PLATAFORMA.md](https://github.com/alvaroavx/avx-django-plataformaelemental/blob/main/docs/arquitectura/PLATAFORMA.md)
   Estado tecnico transversal y arquitectura vigente.
5. [docs/arquitectura/ROADMAP_DOMINIOS.md](https://github.com/alvaroavx/avx-django-plataformaelemental/blob/main/docs/arquitectura/ROADMAP_DOMINIOS.md)
   Roadmap por dominio para ordenar crecimiento futuro sin romper el monolito modular.
6. [docs/arquitectura/DEUDA_TECNICA.md](https://github.com/alvaroavx/avx-django-plataformaelemental/blob/main/docs/arquitectura/DEUDA_TECNICA.md)
   Deuda tecnica activa, impacto y accion recomendada.
7. [docs/arquitectura/INVENTARIO_REGLAS_NEGOCIO.md](https://github.com/alvaroavx/avx-django-plataformaelemental/blob/main/docs/arquitectura/INVENTARIO_REGLAS_NEGOCIO.md)
   Inventario de reglas de negocio y referencias de codigo.
8. [docs/arquitectura/MODELO_DATOS.md](https://github.com/alvaroavx/avx-django-plataformaelemental/blob/main/docs/arquitectura/MODELO_DATOS.md)
   Mapa relacional simplificado, tablas legacy, relaciones criticas, integridad y deuda tecnica de modelo.
9. [docs/arquitectura/NAVEGACION_Y_CONTEXTO.md](https://github.com/alvaroavx/avx-django-plataformaelemental/blob/main/docs/arquitectura/NAVEGACION_Y_CONTEXTO.md)
   Reglas transversales de filtros globales, periodo, organizacion activa y navegacion.
10. [docs/arquitectura/PERMISOS_Y_ROLES.md](https://github.com/alvaroavx/avx-django-plataformaelemental/blob/main/docs/arquitectura/PERMISOS_Y_ROLES.md)
   Criterio transversal de roles, permisos y riesgos de acceso.
11. [docs/arquitectura/OBSERVABILIDAD.md](https://github.com/alvaroavx/avx-django-plataformaelemental/blob/main/docs/arquitectura/OBSERVABILIDAD.md)
   Criterios para crecimiento de `monitor`, indicadores y observabilidad interna.
12. [docs/proceso/TESTING.md](https://github.com/alvaroavx/avx-django-plataformaelemental/blob/main/docs/proceso/TESTING.md)
   Estrategia de pruebas por tipo de cambio y comando principal de CI.
13. Documento local de la app que vayas a tocar:
   - [docs/apps/ASISTENCIAS.md](https://github.com/alvaroavx/avx-django-plataformaelemental/blob/main/docs/apps/ASISTENCIAS.md)
   - [docs/apps/PERSONAS.md](https://github.com/alvaroavx/avx-django-plataformaelemental/blob/main/docs/apps/PERSONAS.md)
   - [docs/apps/FINANZAS.md](https://github.com/alvaroavx/avx-django-plataformaelemental/blob/main/docs/apps/FINANZAS.md)
   - [docs/apps/API.md](https://github.com/alvaroavx/avx-django-plataformaelemental/blob/main/docs/apps/API.md)
   - [docs/apps/MONITOR.md](https://github.com/alvaroavx/avx-django-plataformaelemental/blob/main/docs/apps/MONITOR.md)
14. [README.md](https://github.com/alvaroavx/avx-django-plataformaelemental/blob/main/README.md)
   Resumen humano y puesta en marcha.
15. [docs/operacion/DEPLOY.md](https://github.com/alvaroavx/avx-django-plataformaelemental/blob/main/docs/operacion/DEPLOY.md)
   Guia operativa de CI/CD y despliegue.
16. [docs/operacion/AUDITORIA_SQLITE_POSTGRESQL.md](https://github.com/alvaroavx/avx-django-plataformaelemental/blob/main/docs/operacion/AUDITORIA_SQLITE_POSTGRESQL.md)
   Informacion real del proyecto para planificar migracion de SQLite a PostgreSQL.
17. [docs/operacion/SEGURIDAD_PRODUCCION.md](https://github.com/alvaroavx/avx-django-plataformaelemental/blob/main/docs/operacion/SEGURIDAD_PRODUCCION.md)
   Reglas vigentes de sesiones, cookies, HTTPS y headers para produccion.

## Como mantenerla
- Cada decision concreta debe quedar documentada en el mismo cambio de codigo.
- Si el cambio es local, actualiza el `.md` de la app.
- Si el cambio es transversal, actualiza tambien `docs/arquitectura/PLATAFORMA.md`.
- Si cambia la forma de trabajar sobre el repo, actualiza `AGENTS.md` y `docs/proceso/DECISIONES.md`.
- Si cambia la explicacion general para humanos, actualiza `README.md`.

## Estructura
- `docs/arquitectura/`: fotografia tecnica transversal.
- `docs/arquitectura/DEUDA_TECNICA.md`: deuda tecnica activa, impacto y accion recomendada.
- `docs/arquitectura/MODELO_DATOS.md`: mapa relacional, integridad, tablas legacy y deuda tecnica de modelo.
- `docs/arquitectura/NAVEGACION_Y_CONTEXTO.md`: filtros globales, periodo, organizacion activa y navegacion compartida.
- `docs/arquitectura/OBSERVABILIDAD.md`: criterios para `monitor`, indicadores y observabilidad interna.
- `docs/arquitectura/PERMISOS_Y_ROLES.md`: roles, permisos y riesgos de acceso.
- `docs/arquitectura/ROADMAP_DOMINIOS.md`: crecimiento futuro por dominio.
- `docs/apps/`: decisiones y criterios por app.
- `docs/proceso/`: reglas de mantenimiento y documentacion.
- `docs/proceso/CHECKLIST_CAMBIOS.md`: checklist para cambios funcionales, visuales, de modelo, deploy y documentacion.
- `docs/proceso/TESTING.md`: estrategia de pruebas y validaciones por tipo de cambio.
- `docs/operacion/`: guias operativas del proyecto.
- `docs/operacion/AUDITORIA_SQLITE_POSTGRESQL.md`: auditoria de settings, modelos, migraciones, datos y entorno para migracion a PostgreSQL.
- `docs/operacion/SEGURIDAD_PRODUCCION.md`: configuracion operativa de seguridad para produccion.
- `docs/apps/ASISTENCIAS.md`: decisiones de la app `asistencias`.
- `docs/apps/PERSONAS.md`: decisiones de la app `personas`.
- `docs/apps/FINANZAS.md`: decisiones de la app `finanzas`.
- `docs/apps/API.md`: decisiones de la app `api`.
- `docs/apps/MONITOR.md`: decisiones de la app `monitor`.

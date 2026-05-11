# INDICE

Fecha de actualizacion: 2026-04-29

Esta carpeta ordena la documentacion que Codex y el equipo deben tomar en cuenta al trabajar sobre el repo.

## Orden recomendado de lectura
1. [AGENTS.md](https://github.com/alvaroavx/avx-django-plataformaelemental/blob/main/AGENTS.md)
   Reglas operativas del repo y criterios generales de desarrollo.
2. [docs/proceso/DECISIONES.md](https://github.com/alvaroavx/avx-django-plataformaelemental/blob/main/docs/proceso/DECISIONES.md)
   Regla de mantenimiento documental y jerarquia de archivos.
3. [docs/arquitectura/PLATAFORMA.md](https://github.com/alvaroavx/avx-django-plataformaelemental/blob/main/docs/arquitectura/PLATAFORMA.md)
   Estado tecnico transversal y arquitectura vigente.
4. [docs/arquitectura/INVENTARIO_REGLAS_NEGOCIO.md](https://github.com/alvaroavx/avx-django-plataformaelemental/blob/main/docs/arquitectura/INVENTARIO_REGLAS_NEGOCIO.md)
   Inventario de reglas de negocio y referencias de codigo.
5. Documento local de la app que vayas a tocar:
   - [docs/apps/ASISTENCIAS.md](https://github.com/alvaroavx/avx-django-plataformaelemental/blob/main/docs/apps/ASISTENCIAS.md)
   - [docs/apps/PERSONAS.md](https://github.com/alvaroavx/avx-django-plataformaelemental/blob/main/docs/apps/PERSONAS.md)
   - [docs/apps/FINANZAS.md](https://github.com/alvaroavx/avx-django-plataformaelemental/blob/main/docs/apps/FINANZAS.md)
   - [docs/apps/API.md](https://github.com/alvaroavx/avx-django-plataformaelemental/blob/main/docs/apps/API.md)
   - [docs/apps/MONITOR.md](https://github.com/alvaroavx/avx-django-plataformaelemental/blob/main/docs/apps/MONITOR.md)
6. [README.md](https://github.com/alvaroavx/avx-django-plataformaelemental/blob/main/README.md)
   Resumen humano y puesta en marcha.
7. [docs/operacion/DEPLOY.md](https://github.com/alvaroavx/avx-django-plataformaelemental/blob/main/docs/operacion/DEPLOY.md)
   Guia operativa de CI/CD y despliegue.
8. [docs/operacion/AUDITORIA_SQLITE_POSTGRESQL.md](https://github.com/alvaroavx/avx-django-plataformaelemental/blob/main/docs/operacion/AUDITORIA_SQLITE_POSTGRESQL.md)
   Informacion real del proyecto para planificar migracion de SQLite a PostgreSQL.
9. [docs/operacion/SEGURIDAD_PRODUCCION.md](https://github.com/alvaroavx/avx-django-plataformaelemental/blob/main/docs/operacion/SEGURIDAD_PRODUCCION.md)
   Reglas vigentes de sesiones, cookies, HTTPS y headers para produccion.

## Como mantenerla
- Cada decision concreta debe quedar documentada en el mismo cambio de codigo.
- Si el cambio es local, actualiza el `.md` de la app.
- Si el cambio es transversal, actualiza tambien `docs/arquitectura/PLATAFORMA.md`.
- Si cambia la forma de trabajar sobre el repo, actualiza `AGENTS.md` y `docs/proceso/DECISIONES.md`.
- Si cambia la explicacion general para humanos, actualiza `README.md`.

## Estructura
- `docs/arquitectura/`: fotografia tecnica transversal.
- `docs/apps/`: decisiones y criterios por app.
- `docs/proceso/`: reglas de mantenimiento y documentacion.
- `docs/operacion/`: guias operativas del proyecto.
- `docs/operacion/AUDITORIA_SQLITE_POSTGRESQL.md`: auditoria de settings, modelos, migraciones, datos y entorno para migracion a PostgreSQL.
- `docs/operacion/SEGURIDAD_PRODUCCION.md`: configuracion operativa de seguridad para produccion.
- `docs/apps/ASISTENCIAS.md`: decisiones de la app `asistencias`.
- `docs/apps/PERSONAS.md`: decisiones de la app `personas`.
- `docs/apps/FINANZAS.md`: decisiones de la app `finanzas`.
- `docs/apps/API.md`: decisiones de la app `api`.
- `docs/apps/MONITOR.md`: decisiones de la app `monitor`.

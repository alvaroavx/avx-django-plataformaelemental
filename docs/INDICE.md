# INDICE

Fecha de actualizacion: 2026-04-01

Esta carpeta ordena la documentacion que Codex y el equipo deben tomar en cuenta al trabajar sobre el repo.

## Orden recomendado de lectura
1. [AGENTS.md](/home/alvax/Code/platforms/avx-django-plataformaelemental/AGENTS.md)
   Reglas operativas del repo y criterios generales de desarrollo.
2. [docs/proceso/DECISIONES.md](/home/alvax/Code/platforms/avx-django-plataformaelemental/docs/proceso/DECISIONES.md)
   Regla de mantenimiento documental y jerarquia de archivos.
3. [docs/arquitectura/PLATAFORMA.md](/home/alvax/Code/platforms/avx-django-plataformaelemental/docs/arquitectura/PLATAFORMA.md)
   Estado tecnico transversal y arquitectura vigente.
4. Documento local de la app que vayas a tocar:
   - [docs/apps/ASISTENCIAS.md](/home/alvax/Code/platforms/avx-django-plataformaelemental/docs/apps/ASISTENCIAS.md)
   - [docs/apps/PERSONAS.md](/home/alvax/Code/platforms/avx-django-plataformaelemental/docs/apps/PERSONAS.md)
   - [docs/apps/FINANZAS.md](/home/alvax/Code/platforms/avx-django-plataformaelemental/docs/apps/FINANZAS.md)
   - [docs/apps/API.md](/home/alvax/Code/platforms/avx-django-plataformaelemental/docs/apps/API.md)
5. [README.md](/home/alvax/Code/platforms/avx-django-plataformaelemental/README.md)
   Resumen humano y puesta en marcha.
6. [docs/operacion/DEPLOY.md](/home/alvax/Code/platforms/avx-django-plataformaelemental/docs/operacion/DEPLOY.md)
   Guia operativa de CI/CD y despliegue.

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
- `docs/apps/ASISTENCIAS.md`: decisiones de la app `asistencias`.
- `docs/apps/PERSONAS.md`: decisiones de la app `personas`.
- `docs/apps/FINANZAS.md`: decisiones de la app `finanzas`.
- `docs/apps/API.md`: decisiones de la app `api`.

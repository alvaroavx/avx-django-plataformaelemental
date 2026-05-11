# Onboarding Codex

Fecha de actualizacion: 2026-05-11

## Proposito
Este documento explica como leer el repo antes de tocarlo.

`docs/INDICE.md` es el mapa documental. Este archivo es la ruta operativa recomendada para Codex y para cambios asistidos.

## Orden Recomendado De Lectura
1. [AGENTS.md](https://github.com/alvaroavx/avx-django-plataformaelemental/blob/main/AGENTS.md)
   Reglas operativas del repo y criterios generales de desarrollo.
2. [docs/proceso/DECISIONES.md](https://github.com/alvaroavx/avx-django-plataformaelemental/blob/main/docs/proceso/DECISIONES.md)
   Gobernanza documental y jerarquia de autoridad.
3. [docs/proceso/CHECKLIST_CAMBIOS.md](https://github.com/alvaroavx/avx-django-plataformaelemental/blob/main/docs/proceso/CHECKLIST_CAMBIOS.md)
   Checklist para cerrar cambios sin dejar documentacion falsa o validaciones pendientes.
4. [docs/arquitectura/PLATAFORMA.md](https://github.com/alvaroavx/avx-django-plataformaelemental/blob/main/docs/arquitectura/PLATAFORMA.md)
   Fotografia ejecutiva de arquitectura.
5. [docs/arquitectura/ROADMAP_DOMINIOS.md](https://github.com/alvaroavx/avx-django-plataformaelemental/blob/main/docs/arquitectura/ROADMAP_DOMINIOS.md)
   Roadmap por dominio para ordenar crecimiento futuro.
6. [docs/arquitectura/DEUDA_TECNICA.md](https://github.com/alvaroavx/avx-django-plataformaelemental/blob/main/docs/arquitectura/DEUDA_TECNICA.md)
   Deuda tecnica activa, impacto y accion recomendada.
7. [docs/arquitectura/INVENTARIO_REGLAS_NEGOCIO.md](https://github.com/alvaroavx/avx-django-plataformaelemental/blob/main/docs/arquitectura/INVENTARIO_REGLAS_NEGOCIO.md)
   Inventario de reglas de negocio y referencias de codigo.
8. [docs/arquitectura/MODELO_DATOS.md](https://github.com/alvaroavx/avx-django-plataformaelemental/blob/main/docs/arquitectura/MODELO_DATOS.md)
   Mapa relacional, integridad, tablas legacy y deuda tecnica de modelo.
9. [docs/arquitectura/NAVEGACION_Y_CONTEXTO.md](https://github.com/alvaroavx/avx-django-plataformaelemental/blob/main/docs/arquitectura/NAVEGACION_Y_CONTEXTO.md)
   Filtros globales, periodo, organizacion activa y navegacion.
10. [docs/arquitectura/PERMISOS_Y_ROLES.md](https://github.com/alvaroavx/avx-django-plataformaelemental/blob/main/docs/arquitectura/PERMISOS_Y_ROLES.md)
    Roles, permisos y riesgos de acceso.
11. [docs/arquitectura/OBSERVABILIDAD.md](https://github.com/alvaroavx/avx-django-plataformaelemental/blob/main/docs/arquitectura/OBSERVABILIDAD.md)
    Criterios para `monitor`, indicadores y observabilidad interna.
12. [docs/proceso/TESTING.md](https://github.com/alvaroavx/avx-django-plataformaelemental/blob/main/docs/proceso/TESTING.md)
    Estrategia de pruebas por tipo de cambio.
13. Documento local de la app que vayas a tocar:
    - [docs/apps/ASISTENCIAS.md](https://github.com/alvaroavx/avx-django-plataformaelemental/blob/main/docs/apps/ASISTENCIAS.md)
    - [docs/apps/PERSONAS.md](https://github.com/alvaroavx/avx-django-plataformaelemental/blob/main/docs/apps/PERSONAS.md)
    - [docs/apps/FINANZAS.md](https://github.com/alvaroavx/avx-django-plataformaelemental/blob/main/docs/apps/FINANZAS.md)
    - [docs/apps/API.md](https://github.com/alvaroavx/avx-django-plataformaelemental/blob/main/docs/apps/API.md)
    - [docs/apps/MONITOR.md](https://github.com/alvaroavx/avx-django-plataformaelemental/blob/main/docs/apps/MONITOR.md)
14. [README.md](https://github.com/alvaroavx/avx-django-plataformaelemental/blob/main/README.md)
    Resumen humano y puesta en marcha.
15. Documentos operativos si aplica:
    - [docs/operacion/DEPLOY.md](https://github.com/alvaroavx/avx-django-plataformaelemental/blob/main/docs/operacion/DEPLOY.md)
    - [docs/operacion/AUDITORIA_SQLITE_POSTGRESQL.md](https://github.com/alvaroavx/avx-django-plataformaelemental/blob/main/docs/operacion/AUDITORIA_SQLITE_POSTGRESQL.md)
    - [docs/operacion/SEGURIDAD_PRODUCCION.md](https://github.com/alvaroavx/avx-django-plataformaelemental/blob/main/docs/operacion/SEGURIDAD_PRODUCCION.md)

## Como Mantener Documentacion Viva
- Cada decision concreta debe quedar documentada en el mismo cambio de codigo.
- Si el cambio es local, actualizar el `.md` de la app.
- Si el cambio es transversal, actualizar el documento especializado correspondiente y, si aplica, `docs/arquitectura/PLATAFORMA.md`.
- Si cambia la forma de trabajar sobre el repo, actualizar `AGENTS.md`, `docs/proceso/DECISIONES.md` y este archivo.
- Si cambia la explicacion general para humanos, actualizar `README.md`.
- Si se acepta deuda tecnica consciente, registrarla en `docs/arquitectura/DEUDA_TECNICA.md`.

## Regla De Cierre
Antes de responder que un cambio esta terminado:
- revisar el diff,
- confirmar que no se tocaron archivos fuera del alcance,
- ejecutar checks/tests relevantes o explicar por que no aplican,
- actualizar documentacion duenia,
- mencionar cualquier ambiguedad o riesgo residual.

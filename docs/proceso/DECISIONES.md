# DECISIONES

Fecha de actualizacion: 2026-04-01

## Proposito
Este documento define como se mantiene la documentacion viva del repo.

## Regla principal
Toda decision concreta de producto, modelo, navegacion, integracion o flujo operativo debe persistirse en Markdown dentro del mismo cambio de codigo que la implementa.

## Jerarquia documental
1. `README.md`
   Uso humano. Debe explicar rapidamente que es la plataforma, como levantarla y donde esta la documentacion relevante.
2. `AGENTS.md`
   Reglas operativas del agente sobre este repo.
3. `docs/INDICE.md`
   Indice y orden de lectura de la documentacion viva.
4. `docs/arquitectura/PLATAFORMA.md`
   Estado tecnico transversal y arquitectura vigente.
5. `docs/apps/FINANZAS.md`
   Decisiones y criterios locales de `finanzas`.
6. `docs/apps/ASISTENCIAS.md`
   Decisiones y criterios locales de `asistencias`.
7. `docs/apps/PERSONAS.md`
   Decisiones y criterios locales de `personas`.
8. `docs/apps/API.md`
   Decisiones y criterios locales de `api`.
9. `docs/operacion/DEPLOY.md`
   Guia operativa de despliegue y CI/CD.

## Convencion de mantenimiento
- Si una decision afecta solo una app, actualizar el `.md` de esa app.
- Si afecta varias apps o la arquitectura general, actualizar tambien `docs/arquitectura/PLATAFORMA.md`.
- Si cambia la forma de trabajar del agente o la gobernanza documental, actualizar `AGENTS.md` y este archivo.
- Si cambia la explicacion general para humanos, actualizar `README.md`.
- Si cambia la operacion del proyecto en servidor o CI/CD, actualizar `docs/operacion/`.

## Criterios de calidad
- Evitar duplicar texto largo entre archivos.
- Mantener la documentacion viva dentro de `docs/`, salvo `README.md` y `AGENTS.md` en la raiz.
- Mantener fechas de actualizacion visibles.
- Escribir reglas concretas, no declaraciones ambiguas.

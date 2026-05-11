# DECISIONES

Fecha de actualizacion: 2026-05-11

## Proposito
Este documento define como se mantiene la documentacion viva del repo.

## Regla principal
Toda decision concreta de producto, modelo, navegacion, integracion o flujo operativo debe persistirse en Markdown dentro del mismo cambio de codigo que la implementa.

Antes de cerrar un cambio, aplicar [docs/proceso/CHECKLIST_CAMBIOS.md](CHECKLIST_CAMBIOS.md).

## Jerarquia de autoridad documental
Si hay conflicto entre documentos, aplicar este orden de autoridad:

1. Codigo y tests vigentes.
2. `AGENTS.md` para reglas operativas del agente.
3. `docs/proceso/DECISIONES.md` para gobernanza documental.
4. `docs/arquitectura/PLATAFORMA.md` para arquitectura transversal.
5. `docs/apps/*.md` para decisiones locales de app.
6. `docs/operacion/*.md` para operacion y despliegue.
7. `README.md` para resumen humano.

## Convencion de mantenimiento
- Si una decision afecta solo una app, actualizar el `.md` de esa app.
- Si afecta varias apps o la arquitectura general, actualizar tambien `docs/arquitectura/PLATAFORMA.md`.
- Si cambia la forma de trabajar del agente o la gobernanza documental, actualizar `AGENTS.md` y este archivo.
- Si cambia la explicacion general para humanos, actualizar `README.md`.
- Si cambia la operacion del proyecto en servidor o CI/CD, actualizar `docs/operacion/`.
- Si se acepta deuda tecnica consciente, registrarla en `docs/arquitectura/DEUDA_TECNICA.md`.
- Todo cambio de UI debe considerar comportamiento responsive especifico; mobile no debe ser una copia reducida de desktop, sino una resolucion adecuada de la misma necesidad.

## Criterios de calidad
- Evitar duplicar texto largo entre archivos.
- Mantener la documentacion viva dentro de `docs/`, salvo `README.md` y `AGENTS.md` en la raiz.
- Mantener fechas de actualizacion visibles.
- Escribir reglas concretas, no declaraciones ambiguas.

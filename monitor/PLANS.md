# PLANS.md - monitor

Fecha de actualizacion: 2026-04-29

## Foco actual
Fase 1: primera version implementada, pendiente validacion cruzada y feedback de producto.

## Fase 1
- Django base: implementado
- Auth Django: implementado
- Organizaciones, personas, proyectos y sitios: implementado con proyectos y relacion opcional a organizaciones
- Agregar sitio por URL: implementado
- Discovery inicial: implementado sin worker externo
- Configuracion global y por sitio: implementado
- Dashboard general: implementado
- Vista detalle por sitio: implementado
- Tests base: implementado
- UI responsive inicial: implementado

No entra en fase 1:
- Alertas reales multicanal
- IA generativa o recomendaciones automaticas
- Reportes PDF completos
- Monitoreo en segundo plano con workers
- Integraciones externas pagadas

## Fase 2
- Monitoreo programado
- Alertas internas
- Historial de checks
- Reportes exportables basicos
- Auditoria SEO y tecnica mas profunda

## Fase 3
- Pagina publica de estado o resumen
- Reportes PDF completos
- Tendencias historicas
- Roles avanzados
- Integraciones externas

## Regla de avance
Una fase no se considera cerrada si faltan tests base, documentacion local o comportamiento responsive minimo.

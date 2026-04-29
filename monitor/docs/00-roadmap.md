# Roadmap monitor

## Vision
`monitor` debe ser el centro de control operativo de Plataforma Elemental para sitios, proyectos, auditorias tecnicas y salud general.

## Principios
- Primero estructura; despues automatizacion.
- Primero datos confiables; despues visualizaciones complejas.
- Primero flujos manuales claros; despues alertas e IA.
- Cada indicador debe tener fuente, frecuencia y criterio documentado.

## Fase 1: base operativa
- Crear modelos base para proyectos y sitios.
- Permitir agregar sitio por URL.
- Ejecutar discovery inicial sin procesos en segundo plano.
- Mostrar dashboard general.
- Mostrar detalle por sitio.
- Exponer configuracion global y por sitio.
- Cubrir rutas principales con tests.
- Resolver UI responsive inicial.

## Fase 2: monitoreo real
- Registrar checks historicos.
- Evaluar disponibilidad, SSL, respuesta HTTP y metadatos tecnicos.
- Crear alertas internas dentro de la app.
- Construir reporte exportable simple.

## Fase 3: producto avanzado
- Pagina publica opcional.
- Reportes PDF completos.
- Tendencias historicas.
- Integraciones externas.
- Asistencia inteligente para diagnostico.

## Riesgos
- Duplicar modelos que pertenecen a `personas`.
- Convertir `monitor` en una app de reportes sin datos confiables.
- Mezclar auditoria SEO, alertas y dashboard antes de cerrar el modelo base.

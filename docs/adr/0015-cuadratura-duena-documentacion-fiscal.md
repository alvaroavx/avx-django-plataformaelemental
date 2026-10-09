# ADR 0015 — Cuadratura es dueña de la documentación fiscal

- **Fecha:** 2026-10-08
- **Estado:** aceptada
- **Decisor:** Álvaro

## Contexto

Plataforma Elemental incorporó un modelo y flujos para administrar comprobantes
fiscales, pero nunca se usaron en producción. Cuadratura ya es el producto dueño
de esa responsabilidad. Mantenerla duplicada en Elemental agrega superficie de
datos, permisos, formularios e importación sin valor operativo.

## Decisión

Eliminar de Elemental el modelo, relaciones desde pagos y transacciones,
formularios, vistas, rutas, plantillas, importadores, permisos y pruebas
exclusivos de esa capacidad. Los pagos, consumos de clases y transacciones de
caja permanecen.

La migración elimina las estructuras antiguas. Esta decisión se apoya en la
confirmación de que producción no contiene información de esa capacidad.

## Alternativas consideradas

- Mantener la capacidad oculta: descartada porque conserva deuda y superficie de riesgo.
- Mantener solo el modelo como respaldo: descartada porque duplica la propiedad de Cuadratura.
- Migrar registros a Cuadratura: innecesaria porque no existen registros productivos.

## Consecuencias

- Elemental deja de aceptar, guardar, mostrar o asociar archivos y datos fiscales.
- Desaparecen sus endpoints, permisos y acciones del panel.
- La migración es destructiva para esas tablas y relaciones; exige respaldo y
  verificación de ausencia de datos antes de aplicarla en cada ambiente.
- El contrato Elemental → Cuadratura sigue transfiriendo hechos operacionales;
  no acredita la emisión de comprobantes fiscales.

## Revisión

Reconsiderar solo si aparece un requisito operacional verificable que no pueda
resolverse en Cuadratura ni mediante un contrato versionado entre productos.

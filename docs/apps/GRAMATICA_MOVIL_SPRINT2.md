# Gramática móvil mínima · Sprint 2

Fecha de actualización: 2026-07-26

## Estado

Especificación y prototipo técnico aislado. No está conectado a rutas activas ni constituye la jornada móvil completa.

La validación con Beisics y dos profesoras está pendiente. Este documento no representa validación usuaria.

## Superficies

### Hoy de profesora

- Contexto persistente: organización y fecha.
- Acción principal: abrir la próxima sesión.
- Estados: carga mediante esqueleto estable; vacío con explicación; error con reintento; pérdida de conexión conservando datos ya cargados; éxito identificable por texto e icono.

### Detalle de sesión

- Acción principal: guardar asistencia.
- Búsqueda incremental desde dos caracteres y agregado consecutivo.
- Estados `P`, `A` y `J` usan nombre accesible y no dependen solo de color.
- Objetivos táctiles mínimos de 44 × 44 px.
- El orden de teclado sigue título, búsqueda, resultados, estados y guardado.
- En la implementación activa, el éxito se anuncia mediante texto y región `aria-live`.

### Resumen administrativo

- Organización y periodo permanecen visibles en el resumen de filtros colapsados.
- La apertura de filtros no desplaza ni oculta la acción operativa principal.
- Métricas muestran etiqueta, valor y unidad o interpretación.
- Vacío y error no presentan valores parciales como si fueran definitivos.

## Reflow

- Diseño base: 390 × 844 px.
- A 320 px las filas de persona pasan a una columna y los controles de estado usan el ancho disponible.
- No existen anchos fijos superiores al viewport.
- Las métricas y estados auxiliares pasan de dos columnas a una.

## Accesibilidad mínima

- Contraste de texto y controles mediante combinaciones oscuras sobre fondos claros.
- `:focus-visible` de 3 px con separación.
- Controles nativos de botón, enlace, búsqueda, selector y `details/summary`.
- Objetivos táctiles de 44 px.
- Estados con texto e iconografía, no solo color.
- Navegación utilizable por teclado.

## Evidencia

Fuente: `docs/prototipos/sprint2-mobile.html`.

Capturas técnicas:

- `docs/prototipos/capturas/sprint2-hoy-390x844.png`
- `docs/prototipos/capturas/sprint2-sesion-390x844.png`
- `docs/prototipos/capturas/sprint2-admin-390x844.png`
- `docs/prototipos/capturas/sprint2-hoy-320x844.png`
- `docs/prototipos/capturas/sprint2-sesion-320x844.png`
- `docs/prototipos/capturas/sprint2-admin-320x844.png`

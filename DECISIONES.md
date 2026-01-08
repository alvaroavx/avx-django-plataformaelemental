# Decisiones de arquitectura y supuestos

1. **Autenticación**: Se mantiene `rest_framework.authtoken` como mecanismo principal para la API. Para la app web se usará sesión Django tradicional con `LoginRequiredMixin` y verificación de roles (staff/profesor) mediante `PersonaRol`.
2. **UI**: Se utilizará **Bootstrap 5** (via CDN) para las pantallas `/app/` por simplicidad y soporte responsive inmediato. El código HTML estará en plantillas dentro de una nueva app `webapp`.
3. **Archivos adjuntos**: Los comprobantes se almacenan en `MEDIA_ROOT/comprobantes/`. Se configurará `MEDIA_URL=/media/` y se servirá en desarrollo mediante `django.conf.urls.static`.
4. **Importaciones Excel**: Los comandos buscarán archivos en `BASE_DIR / "data"`. Si no existen se notificará y se abortará la ejecución. Se usarán `pandas` sólo si ya existe en el entorno; de lo contrario se usará `openpyxl`.
5. **Planes**: Un plan define número de clases semanales. Las suscripciones calculan clases asignadas = `plan.clases_semanales * semanas_del_periodo`. El sobreconsumo se calcula comparando asistencias registradas vs asignadas.
6. **Liquidación profesores**: Se asume tarifa única vigente (monto por asistente) y retención fija 14.5%. Si existen múltiples tarifas para la misma disciplina, se toma la más reciente cuya vigencia cubra la fecha de la sesión.
7. **Finanzas**: `MovimientoCaja` servirá como libro único para ingresos y egresos. Los reportes mensuales se agrupan por mes calendario usando zona horaria `America/Santiago`.

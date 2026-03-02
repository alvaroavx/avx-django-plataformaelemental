# Decisiones de arquitectura y supuestos

1. **AutenticaciÃ³n**: Se mantiene `rest_framework.authtoken` como mecanismo principal para la API. Para la app web se usarÃ¡ sesiÃ³n Django tradicional con `LoginRequiredMixin` y verificaciÃ³n de roles (staff/profesor) mediante `PersonaRol`.
2. **UI**: Se utilizarÃ¡ **Bootstrap 5** (via CDN) para las pantallas `/asistencias/` por simplicidad y soporte responsive inmediato. El cÃ³digo HTML estarÃ¡ en plantillas dentro de la app `asistencias`.
3. **Archivos adjuntos**: Los comprobantes se almacenan en `MEDIA_ROOT/comprobantes/`. Se configurarÃ¡ `MEDIA_URL=/media/` y se servirÃ¡ en desarrollo mediante `django.conf.urls.static`.
4. **Importaciones Excel**: Los comandos buscarÃ¡n archivos en `BASE_DIR / "data"`. Si no existen se notificarÃ¡ y se abortarÃ¡ la ejecuciÃ³n. Se usarÃ¡n `pandas` sÃ³lo si ya existe en el entorno; de lo contrario se usarÃ¡ `openpyxl`.
5. **Planes**: Un plan define nÃºmero de clases semanales. Las suscripciones calculan clases asignadas = `plan.clases_semanales * semanas_del_periodo`. El sobreconsumo se calcula comparando asistencias registradas vs asignadas.
6. **LiquidaciÃ³n profesores**: Se asume tarifa Ãºnica vigente (monto por asistente) y retenciÃ³n fija 14.5%. Si existen mÃºltiples tarifas para la misma disciplina, se toma la mÃ¡s reciente cuya vigencia cubra la fecha de la sesiÃ³n.
7. **Finanzas**: `MovimientoCaja` servirÃ¡ como libro Ãºnico para ingresos y egresos. Los reportes mensuales se agrupan por mes calendario usando zona horaria `America/Santiago`.



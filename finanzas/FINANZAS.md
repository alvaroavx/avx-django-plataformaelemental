# Finanzas

Fecha de actualizacion: 2026-03-16

## Objetivo de la app
La app `finanzas` concentra cobros, documentos tributarios, transacciones de caja y reportes basicos. Debe servir para operar varias organizaciones sin asumir un solo negocio ni una sola logica tributaria.

## Decisiones vigentes
- `Pagos` representa cobros a estudiantes por clases o planes. No es el libro general de caja.
- `Transacciones` representa movimientos reales de dinero: ingresos o egresos de caja, banco o tarjeta.
- El archivo adjunto de una `Transaccion` corresponde al respaldo del movimiento, por ejemplo cartola, transferencia o comprobante.
- `Documentos tributarios` es una entidad separada de `Transacciones` y `Pagos`.
- Un documento tributario puede ser factura, boleta de venta, boleta de honorarios, nota de credito, nota de debito u otro.
- Los documentos tributarios deben poder asociarse manualmente a pagos, transacciones y otros documentos.
- La plataforma no debe duplicar archivos: el PDF/XML vive en el documento tributario; el respaldo bancario vive en la transaccion.
- La fuente tributaria principal objetivo es el SII. La plataforma debe quedar preparada para importar documentos desde ahi y luego asociarlos manualmente.
- La informacion tributaria no debe asumir solo IVA 19%. Debe soportar exentos y retenciones variables, por ejemplo honorarios.

## Modelo funcional actual
- `Payment`: cobro academico a estudiante, con plan y clases.
- `Transaction`: movimiento financiero general, con categoria y respaldo de movimiento.
- `DocumentoTributario`: repositorio de documentos fiscales con PDF/XML, tasas, montos y relaciones.
- `Category`: clasificacion de transacciones para reportes.
- `PaymentPlan`: estructura comercial de clases/precios.

## Reglas de uso
- Si ingresa dinero por una venta o prestacion, eso puede existir como `Transaccion` y como `DocumentoTributario`, pero cada uno cumple un rol distinto.
- Si sale dinero para pagar honorarios, cada pago real debe registrarse como `Transaccion` de tipo `egreso`.
- La boleta de honorarios del artista debe cargarse como `DocumentoTributario`.
- La asociacion entre una boleta de venta y un `Payment` es manual.
- La asociacion entre una boleta de honorarios y una `Transaccion` de egreso es manual.
- La asociacion entre un documento y otro documento tambien es manual mediante `documento_relacionado`.

## UI y navegacion
- Todas las vistas de `finanzas` deben mantener `periodo_mes`, `periodo_anio` y `organizacion`.
- Cada seccion principal debe incluir una explicacion breve de uso visible en la interfaz.
- Las acciones de crear/agregar usan boton verde.
- Las acciones de eliminar usan boton rojo.

## Cambios relevantes ya implementados
- Resumen superior en `pagos` con total pagos, total clases pagadas y saldo.
- Filtro de planes por organizacion en el formulario de pagos.
- Boton volver en editar pago prioriza la pagina anterior.
- Visor PDF embebido en detalle de transacciones.
- Separacion conceptual y tecnica de `Documentos tributarios` respecto de `Transacciones`.
- Carga asistida XML-first para documentos tributarios con flujo:
  - subir archivo
  - parsear
  - revisar formularios precargados
  - confirmar guardado manual
- Soporte inicial para:
  - DTE XML clasico
  - boleta de honorarios XML
  - PDF fallback basico
- Deteccion de posibles duplicados solo como advertencia, sin bloqueo automatico.

## Pendientes esperados
- Mejorar parser PDF y soportar mas formatos.
- Importacion directa desde SII, idealmente usando XML como fuente principal.
- Flujo asistido de conciliacion entre documentos tributarios, pagos y transacciones.
- Posible capa superior para agrupar ingresos/egresos/documentos por evento o presentacion.

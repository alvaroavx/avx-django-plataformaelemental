# Finanzas

Fecha de actualizacion: 2026-04-29

## Proposito
La app `finanzas` concentra cobros academicos, documentos tributarios, movimientos de caja y reportes basicos.

Debe servir para operar varias organizaciones y tambien debe poder escalar a finanzas no academicas sin asumir una sola logica de negocio.

## Regla conceptual principal
- `Payment`, `Transaction` y `DocumentoTributario` son entidades separadas.
- `DocumentoTributario` no es obligatorio para que la plataforma funcione.
- El documento tributario actua como respaldo y como ingreso asistido de informacion cuando existe.
- La plataforma debe seguir operando aunque no exista documento tributario.

## Modelo funcional vigente
- `Payment`: cobro academico a estudiante por clases o planes.
- `Transaction`: movimiento real de dinero, ingreso o egreso, con respaldo bancario o de caja.
- `DocumentoTributario`: documento fiscal opcional, con PDF/XML, montos, tasas y asociaciones.
- `Category`: clasificacion de transacciones para reportes.
- `PaymentPlan`: estructura comercial de clases y precio.
- Los modelos financieros viven en `finanzas.models`; `database` ya no concentra modelos de runtime y queda solo como compatibilidad historica de migraciones.

## Reglas de uso
- Un ingreso puede existir como `Transaction` y tambien como `DocumentoTributario`, pero cada entidad cumple un rol distinto.
- Una boleta de venta puede sugerir un `Payment`, pero no debe fusionarse con el pago.
- Una boleta de honorarios puede respaldar un egreso, pero no reemplaza la `Transaction`.
- El archivo adjunto de una `Transaction` corresponde al respaldo del movimiento, por ejemplo transferencia o cartola.
- El PDF/XML tributario vive en `DocumentoTributario`.
- Las asociaciones entre entidades deben poder hacerse manualmente.
- Un `DocumentoTributario` puede asociarse opcionalmente a una `Persona` o a una `Organizacion` como contraparte, pero no a ambas al mismo tiempo.
- Cada organizacion debe tener un solo `PaymentPlan` por defecto.
- El primer plan creado en una organizacion queda por defecto automaticamente.
- El plan por defecto se puede cambiar desde gestion de planes y es el que aparece preseleccionado al registrar un nuevo pago.
- Al registrar un nuevo pago, el checkbox `aplica IVA` debe precargarse segun `Organizacion.es_exenta_iva`: organizaciones exentas parten sin IVA, las demas con IVA activo.
- Las clases pagadas no se arrastran entre meses.
- Una asistencia solo puede consumirse contra pagos del mismo mes y anio de la clase.
- Si no existe pago del mismo mes con saldo disponible, la asistencia debe generar deuda.
- Si luego aparece un pago, solo puede imputar deudas del mismo mes y anio.

## Carga asistida de documentos
Estado actual:
- XML-first
- soporte inicial para DTE XML clasico
- soporte inicial para boleta de honorarios XML
- PDF fallback basico
- parser PDF con mejora especifica para boletas de honorarios electronicas
- parser PDF con mejora especifica para boletas de venta electronicas tipo 39 y 41 cuando vienen con `BOLETA ELECTRONICA NUMERO` o `BOLETA EXENTA ELECTRONICA NUMERO`, `Medio de pago`, glosa libre y monto total
- pantalla de revision antes del guardado
- la pantalla de revision incluye visor inline del PDF/XML temporal para contrastar el formulario contra el archivo original
- si no hay libreria Python para leer PDF, se intenta `pdftotext` del sistema
- el fallback PDF funciona sobre PDFs con texto seleccionable; no resuelve escaneos sin OCR

Reglas:
- subir un archivo no debe guardar automaticamente registros finales
- el flujo debe ser:
  - subir archivo
  - extraer datos
  - mostrar formularios precargados
- revisar/corregir
- confirmar guardado
- la UI de carga asistida usa un solo input de archivo; el backend detecta internamente si el archivo subido es XML o PDF
- la deteccion de duplicados es advertencia, no bloqueo automatico
- la unicidad operativa de un documento tributario dentro de una organizacion se define por `tipo_documento + folio + rut_emisor`; el folio por si solo no basta, porque distintos emisores pueden repetirlo
- los datos extraidos desde PDF tienen menor confianza y deben revisarse siempre
- en facturas y boletas, un monto con punto de miles como `500.000` significa `500000` sin decimales; esa normalizacion aplica tanto al parser PDF como a la confirmacion manual de la carga asistida
- en boletas de venta electronicas PDF tipo 39 y 41, el parser debe extraer al menos:
  - folio completo desde `BOLETA ELECTRONICA NUMERO`
  - fecha
  - medio de pago
  - glosa principal
  - monto bruto
- para tipo 39 afecta:
  - IVA incluido
  - neto calculado como `bruto - IVA`
- para tipo 41 exenta:
  - `exento = bruto`
  - `IVA = 0`
  - `neto = 0`
- en esas boletas, el pago sugerido debe heredar el metodo de pago desde el documento cuando venga indicado, por ejemplo `Transferencia Electronica`
- en la carga asistida, `observaciones` debe precargarse con la glosa o descripcion principal extraida del documento, antes que con warnings tecnicos
- la pantalla de revision de carga asistida debe mostrar errores generales del formulario cuando el guardado no puede confirmarse
- las vistas de crear/editar documentos tributarios deben mostrar un error legible si la base rechaza el guardado por un conflicto de unicidad, en vez de exponer un `IntegrityError`
- en la carga asistida, se debe sugerir automaticamente la contraparte del documento comparando el RUT de la contraparte real contra personas y organizaciones existentes; la sugerencia siempre debe poder cambiarse manualmente antes de guardar

## UI y navegacion
- Todas las vistas de `finanzas` deben mantener `periodo_mes`, `periodo_anio` y `organizacion`.
- Si no hay filtros explicitos en la URL, el periodo global debe partir en el mes y año actuales, y la organizacion debe partir en `Todas`.
- Los filtros globales de `mes`, `anio` y `organizacion` deben autoaplicarse al cambiar, sin boton `Aplicar filtros`.
- `periodo_mes` y `periodo_anio` deben ofrecer la opcion `Todos`, permitiendo ver todos los meses de un año, un mismo mes en todos los años o todo el historial, segun combinacion.
- El menu superior agrupa visualmente los accesos en bloques redondeados, manteniendo este orden: `dashboard`, `pagos`, `documentos tributarios`, `transacciones` | `planes`, `categorias` | `reporte categorias`.
- Cada vista principal y de detalle debe tener su ayuda breve accesible desde un icono junto al titulo; en desktop se muestra como tooltip al pasar el mouse y en mobile como popover al tocar, en vez de ocupar un cuadro adicional dentro de la vista.
- Los botones de accion en `finanzas` deben llevar icono representativo a la izquierda y `title` descriptivo; en desktop muestran icono y texto, y en mobile conservan solo el icono para ahorrar espacio.
- Botones de crear/agregar en verde.
- Botones de eliminar en rojo.

## Cambios ya implementados
- Resumen superior en `pagos` con total pagos, total clases pagadas, IVA total y saldo.
- Resumen superior en `documentos tributarios` y `transacciones` usando el mismo universo filtrado del listado; en documentos separa `ingresos` y `egresos` segun si la organizacion del documento actua como emisor o receptor, y ademas muestra `IVA` y `retencion`.
- Los cards de resumen en `pagos`, `transacciones` y dashboard deben usar colores suaves y consistentes entre vistas, evitando fondos saturados.
- Las vistas principales que crean contenido en `finanzas` deben mostrar el boton de alta al nivel del titulo y abrir el formulario en modal, para no desplazar el listado principal.
- En `pagos`, la edicion tambien debe resolverse dentro del listado mediante modal, y al guardar debe volver al mismo listado filtrado en vez de abrir una pantalla aparte.
- En `pagos`, al cerrar el modal de edicion con cancelar, equis o click fuera, la URL debe eliminar `editar_pago` del querystring para que un refresh no reabra el modal.
- En `pagos`, debe existir tambien un alta rapida de `Nueva persona` junto a `Registrar pago`, en modal, usando la organizacion filtrada arriba para asignar automaticamente el rol `ESTUDIANTE`.
- Si no hay organizacion filtrada al usar `Nueva persona` desde `pagos`, el error debe aparecer dentro del modal indicando que primero se seleccione una organizacion.
- El listado de `documentos tributarios` prioriza lectura financiera/tributaria: muestra `neto`, `exento`, `IVA`, `retencion` y `total`, y no repite `organizacion` porque ya existe filtro superior.
- `documentos tributarios` debe permitir asociar contraparte tanto en alta manual como en carga asistida y edicion posterior; el detalle y listado deben mostrar esa asociacion cuando exista.
- `reporte categorias` muestra tabla y grafico de torta sobre el mismo consolidado filtrado.
- Listado de `pagos` con badge fiscal `Afecta/Exenta`, columnas separadas de neto, IVA y bruto, y accion rapida para copiar descripcion operativa del pago.
- Los montos de neto, IVA y bruto en `pagos` son clickeables y copian el valor sin formato al portapapeles.
- La descripcion operativa del pago usa como disciplina principal aquella donde la persona registra mas asistencias `presente`.
- En transacciones, el tipo `ingreso/egreso` se deriva automaticamente desde la categoria y no se expone como selector manual.
- En transacciones, el selector de documentos tributarios muestra tipo, folio y extracto de observaciones para dar contexto antes de asociar.
- Al crear una transaccion nueva, la organizacion debe quedar precargada desde el filtro superior activo.
- Filtro de planes por organizacion en el formulario de pagos.
- Gestion de planes con marca `por defecto` por organizacion y precarga automatica en el alta de pagos.
- `finanzas/planes/<id>/editar` reutiliza el mismo listado de planes y abre una edicion inline dentro de la tabla, en vez de navegar a una pantalla separada.
- Boton volver en editar pago prioriza la pagina anterior.
- Visor embebido en detalle de transacciones para PDF e imagenes; otros archivos siguen abriendose externamente.
- Separacion clara entre `Documentos tributarios` y `Transacciones`.
- Carga asistida tributaria con parseo, revision y confirmacion.
- Integracion asistencia-pagos restringida al mismo mes de la clase y del pago.

## Pendientes
- Mejorar parser PDF para mas formatos y layouts.
- Importacion directa desde SII.
- Matching mejor de contraparte.
- Flujo de conciliacion mas asistido entre pagos, documentos y transacciones.
- Evaluar una entidad superior de evento/proyecto si el control financiero por presentacion se vuelve necesario.

## API externa base
- `finanzas` expone una base de consumo externo en:
  - `/api/v1/finanzas/planes/`
  - `/api/v1/finanzas/pagos/`
  - `/api/v1/finanzas/documentos-tributarios/`
  - `/api/v1/finanzas/transacciones/`
  - `/api/v1/finanzas/resumen/`
- En esta fase la API es principalmente de lectura; no se expone aun escritura financiera externa.
- La API key de solo lectura es valida para estos endpoints.

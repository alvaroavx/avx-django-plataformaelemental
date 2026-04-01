# INVENTARIO REGLAS DE NEGOCIO EN CODIGO

Fecha: 2026-04-01

## Objetivo
Este archivo inventaria reglas de negocio que hoy estan escritas directamente en el codigo de Plataforma Elemental.

La idea es distinguir:
- que esta duro en codigo y probablemente deberia poder configurarse
- que esta duro en codigo pero conviene mantener fijo
- donde vive cada regla exactamente

## Alcance revisado
Barrido realizado sobre:
- `database/models.py`
- `finanzas/forms.py`
- `finanzas/services.py`
- `finanzas/views.py`
- `finanzas/documentos/parsers.py`
- `asistencias/context_processors.py`
- `asistencias/utils.py`
- `personas/views.py`

No se incluyeron detalles menores de estilo visual o texto editorial salvo cuando afectan comportamiento operativo.

## Leyenda
- `Configurable alta prioridad`: conviene mover a configuracion editable o parametrizable.
- `Configurable media prioridad`: puede volverse parametrizable mas adelante.
- `Mantener en codigo`: forma parte del dominio base o infraestructura estable.

## Inventario exacto

### 1. Organizaciones y politica fiscal

#### `database/models.py`
- [database/models.py:12](/home/alvax/Code/platforms/avx-django-plataformaelemental/database/models.py#L12)
  Regla: la organizacion solo tiene un flag `es_exenta_iva`.
  Tipo: `Configurable alta prioridad`.
  Observacion: hoy no existe una configuracion fiscal mas rica por organizacion. Falta modelar tasa IVA vigente, regimen, vigencias o comportamiento por tipo documental.

- [database/models.py:255](/home/alvax/Code/platforms/avx-django-plataformaelemental/database/models.py#L255)
  Regla: `IVA_RATE = 0.19`.
  Tipo: `Configurable alta prioridad`.
  Observacion: si la plataforma debe soportar varios regimens, periodos o paises, esta tasa no deberia ser una constante global.

### 2. Roles, perfiles y acceso

#### `asistencias/utils.py`
- [asistencias/utils.py:5](/home/alvax/Code/platforms/avx-django-plataformaelemental/asistencias/utils.py#L5)
  Regla: codigos de rol fijos `admin`, `staff_asistencia`, `profesor`, `estudiante`.
  Tipo: `Mantener en codigo`.
  Observacion: esto define permisos base del sistema. No conviene volverlo editable desde UI salvo que exista una capa formal de permisos.

- [asistencias/utils.py:22](/home/alvax/Code/platforms/avx-django-plataformaelemental/asistencias/utils.py#L22)
  Regla: `superuser` y `staff` siempre pasan chequeos de rol.
  Tipo: `Mantener en codigo`.
  Observacion: es una politica de acceso tecnica, no una regla comercial.

#### `database/models.py`
- [database/models.py:102](/home/alvax/Code/platforms/avx-django-plataformaelemental/database/models.py#L102)
  Regla: una persona no puede repetir el mismo rol en la misma organizacion.
  Tipo: `Mantener en codigo`.
  Observacion: es integridad basica del dominio.

### 3. Calendario operativo global

#### `asistencias/context_processors.py`
- [asistencias/context_processors.py:9](/home/alvax/Code/platforms/avx-django-plataformaelemental/asistencias/context_processors.py#L9)
  Regla: si faltan filtros globales, el mes y anio por defecto son los actuales.
  Tipo: `Configurable media prioridad`.
  Observacion: podria existir una preferencia de usuario o una politica de apertura distinta.

- [asistencias/context_processors.py:17](/home/alvax/Code/platforms/avx-django-plataformaelemental/asistencias/context_processors.py#L17)
  Regla: meses validos `1..12`, anios validos `2000..2100`.
  Tipo: `Mantener en codigo`.
  Observacion: validacion tecnica razonable.

- [asistencias/context_processors.py:27](/home/alvax/Code/platforms/avx-django-plataformaelemental/asistencias/context_processors.py#L27)
  Regla: selector global de anios = `hoy.year - 2` hasta `hoy.year + 2`.
  Tipo: `Configurable media prioridad`.
  Observacion: esta ventana de 5 anios es una decision operativa de interfaz.

- [asistencias/context_processors.py:28](/home/alvax/Code/platforms/avx-django-plataformaelemental/asistencias/context_processors.py#L28)
  Regla: lista fija de meses en espanol.
  Tipo: `Mantener en codigo`.
  Observacion: es catalogo base, no regla comercial.

### 4. Estados academicos

#### `database/models.py`
- [database/models.py:133](/home/alvax/Code/platforms/avx-django-plataformaelemental/database/models.py#L133)
  Regla: dias de semana de bloques horarios.
  Tipo: `Mantener en codigo`.

- [database/models.py:170](/home/alvax/Code/platforms/avx-django-plataformaelemental/database/models.py#L170)
  Regla: estados de sesion `programada`, `completada`, `cancelada`.
  Tipo: `Mantener en codigo`.

- [database/models.py:221](/home/alvax/Code/platforms/avx-django-plataformaelemental/database/models.py#L221)
  Regla: estados de asistencia `presente`, `ausente`, `justificada`.
  Tipo: `Mantener en codigo`.

### 5. Planes de pago

#### `database/models.py`
- [database/models.py:277](/home/alvax/Code/platforms/avx-django-plataformaelemental/database/models.py#L277)
  Regla: un plan parte con `num_clases = 1`.
  Tipo: `Configurable media prioridad`.
  Observacion: podria existir una preferencia por organizacion o un tipo de plan base.

- [database/models.py:279](/home/alvax/Code/platforms/avx-django-plataformaelemental/database/models.py#L279)
  Regla: `precio_incluye_iva = False` por defecto.
  Tipo: `Configurable alta prioridad`.
  Observacion: depende del regimen usual de cada organizacion.

- [database/models.py:280](/home/alvax/Code/platforms/avx-django-plataformaelemental/database/models.py#L280)
  Regla: `es_por_defecto = False` a nivel de campo.
  Tipo: `Mantener en codigo`.

- [database/models.py:297](/home/alvax/Code/platforms/avx-django-plataformaelemental/database/models.py#L297)
  Regla: el primer plan de una organizacion queda por defecto automaticamente.
  Tipo: `Configurable alta prioridad`.
  Observacion: hoy es una decision operativa valida, pero es claramente una regla de negocio.

- [database/models.py:303](/home/alvax/Code/platforms/avx-django-plataformaelemental/database/models.py#L303)
  Regla: si no existe plan por defecto, el actual pasa a serlo.
  Tipo: `Configurable alta prioridad`.

- [database/models.py:306](/home/alvax/Code/platforms/avx-django-plataformaelemental/database/models.py#L306)
  Regla: solo un plan por defecto por organizacion.
  Tipo: `Mantener en codigo`.
  Observacion: conviene mantenerlo como restriccion de consistencia.

- [database/models.py:315](/home/alvax/Code/platforms/avx-django-plataformaelemental/database/models.py#L315)
  Regla: al borrar el plan por defecto, se reasigna el primero por `nombre, id`.
  Tipo: `Configurable media prioridad`.
  Observacion: la regla de reasignacion podria ser otra.

- [database/models.py:320](/home/alvax/Code/platforms/avx-django-plataformaelemental/database/models.py#L320)
  Regla: calculo de montos del plan segun IVA y `precio_incluye_iva`.
  Tipo: `Configurable alta prioridad`.
  Observacion: depende de politica fiscal de la organizacion.

### 6. Documentos tributarios

#### `database/models.py`
- [database/models.py:336](/home/alvax/Code/platforms/avx-django-plataformaelemental/database/models.py#L336)
  Regla: tipos documentales soportados.
  Tipo: `Configurable media prioridad`.
  Observacion: el catalogo base legal puede quedar en codigo, pero la habilitacion por organizacion si debiera configurarse.

- [database/models.py:346](/home/alvax/Code/platforms/avx-django-plataformaelemental/database/models.py#L346)
  Regla: fuentes `manual` y `sii`.
  Tipo: `Mantener en codigo`.

- [database/models.py:358](/home/alvax/Code/platforms/avx-django-plataformaelemental/database/models.py#L358)
  Regla: tipo documental por defecto = `factura_afecta`.
  Tipo: `Configurable alta prioridad`.

- [database/models.py:360](/home/alvax/Code/platforms/avx-django-plataformaelemental/database/models.py#L360)
  Regla: fuente por defecto = `manual`.
  Tipo: `Mantener en codigo`.

- [database/models.py:369](/home/alvax/Code/platforms/avx-django-plataformaelemental/database/models.py#L369)
  Regla: `iva_tasa` por defecto = `19.00`.
  Tipo: `Configurable alta prioridad`.

- [database/models.py:393](/home/alvax/Code/platforms/avx-django-plataformaelemental/database/models.py#L393)
  Regla: unicidad operativa del documento = `organizacion + tipo_documento + folio + rut_emisor`.
  Tipo: `Mantener en codigo`.
  Observacion: es una restriccion de integridad, no conviene dejarla libre.

#### `finanzas/forms.py`
- [finanzas/forms.py:263](/home/alvax/Code/platforms/avx-django-plataformaelemental/finanzas/forms.py#L263)
  Regla: mensaje de negocio ante conflicto de unicidad.
  Tipo: `Mantener en codigo`.

- [finanzas/forms.py:273](/home/alvax/Code/platforms/avx-django-plataformaelemental/finanzas/forms.py#L273)
  Regla: el campo `documento_relacionado` se usa para ligar, por ejemplo, boleta de honorarios con factura origen.
  Tipo: `Configurable media prioridad`.
  Observacion: hoy es solo ayuda textual, pero anticipa una regla de uso.

### 7. Pagos academicos

#### `database/models.py`
- [database/models.py:428](/home/alvax/Code/platforms/avx-django-plataformaelemental/database/models.py#L428)
  Regla: metodos de pago soportados `efectivo`, `transferencia`, `tarjeta`, `otro`.
  Tipo: `Configurable media prioridad`.
  Observacion: el catalogo puede crecer por organizacion.

- [database/models.py:438](/home/alvax/Code/platforms/avx-django-plataformaelemental/database/models.py#L438)
  Regla: un pago solo puede asociarse a personas con rol `ESTUDIANTE`.
  Tipo: `Configurable alta prioridad`.
  Observacion: si la plataforma manejara ventas no academicas o cobros a otros actores, esta restriccion puede quedar corta.

- [database/models.py:459](/home/alvax/Code/platforms/avx-django-plataformaelemental/database/models.py#L459)
  Regla: fecha de pago por defecto = hoy.
  Tipo: `Mantener en codigo`.

- [database/models.py:460](/home/alvax/Code/platforms/avx-django-plataformaelemental/database/models.py#L460)
  Regla: metodo de pago por defecto = `transferencia`.
  Tipo: `Configurable alta prioridad`.

- [database/models.py:462](/home/alvax/Code/platforms/avx-django-plataformaelemental/database/models.py#L462)
  Regla: `aplica_iva = True` por defecto.
  Tipo: `Configurable alta prioridad`.

- [database/models.py:485](/home/alvax/Code/platforms/avx-django-plataformaelemental/database/models.py#L485)
  Regla: formula de neto, IVA y total del pago.
  Tipo: `Configurable alta prioridad`.

- [database/models.py:515](/home/alvax/Code/platforms/avx-django-plataformaelemental/database/models.py#L515)
  Regla: si el pago tiene plan y no trae clases, se heredan del plan.
  Tipo: `Configurable alta prioridad`.

- [database/models.py:517](/home/alvax/Code/platforms/avx-django-plataformaelemental/database/models.py#L517)
  Regla: si la organizacion es exenta, `aplica_iva` siempre se fuerza a `False`.
  Tipo: `Configurable alta prioridad`.

#### `finanzas/forms.py`
- [finanzas/forms.py:124](/home/alvax/Code/platforms/avx-django-plataformaelemental/finanzas/forms.py#L124)
  Regla: el selector de personas del formulario de pago solo carga `ESTUDIANTE`.
  Tipo: `Configurable alta prioridad`.

- [finanzas/forms.py:168](/home/alvax/Code/platforms/avx-django-plataformaelemental/finanzas/forms.py#L168)
  Regla: al registrar un pago se precarga el plan por defecto de la organizacion.
  Tipo: `Configurable alta prioridad`.

- [finanzas/forms.py:171](/home/alvax/Code/platforms/avx-django-plataformaelemental/finanzas/forms.py#L171)
  Regla: `aplica_iva` se precarga segun `Organizacion.es_exenta_iva`.
  Tipo: `Configurable alta prioridad`.

- [finanzas/forms.py:190](/home/alvax/Code/platforms/avx-django-plataformaelemental/finanzas/forms.py#L190)
  Regla: la persona pagadora debe tener rol `ESTUDIANTE` activo en la organizacion.
  Tipo: `Configurable alta prioridad`.

- [finanzas/forms.py:203](/home/alvax/Code/platforms/avx-django-plataformaelemental/finanzas/forms.py#L203)
  Regla: para `transferencia`, el numero de comprobante es obligatorio.
  Tipo: `Configurable alta prioridad`.

- [finanzas/forms.py:212](/home/alvax/Code/platforms/avx-django-plataformaelemental/finanzas/forms.py#L212)
  Regla: el plan debe pertenecer a la misma organizacion del pago.
  Tipo: `Mantener en codigo`.

- [finanzas/forms.py:215](/home/alvax/Code/platforms/avx-django-plataformaelemental/finanzas/forms.py#L215)
  Regla: el documento tributario asociado al pago debe pertenecer a la misma organizacion.
  Tipo: `Mantener en codigo`.

### 8. Consumo de clases y deuda

#### `database/models.py`
- [database/models.py:527](/home/alvax/Code/platforms/avx-django-plataformaelemental/database/models.py#L527)
  Regla: estados del consumo financiero `consumido`, `pendiente`, `deuda`.
  Tipo: `Mantener en codigo`.

#### `finanzas/services.py`
- [finanzas/services.py:40](/home/alvax/Code/platforms/avx-django-plataformaelemental/finanzas/services.py#L40)
  Regla: si la asistencia no esta `presente`, el consumo queda `pendiente` y sin pago.
  Tipo: `Configurable alta prioridad`.
  Observacion: es una decision operativa; otras instituciones podrian querer otras reglas.

- [finanzas/services.py:49](/home/alvax/Code/platforms/avx-django-plataformaelemental/finanzas/services.py#L49)
  Regla: la asistencia solo busca pagos de la misma persona, organizacion y mismo mes/anio.
  Tipo: `Configurable alta prioridad`.

- [finanzas/services.py:61](/home/alvax/Code/platforms/avx-django-plataformaelemental/finanzas/services.py#L61)
  Regla: solo se consideran pagos con `clases_asignadas > 0`.
  Tipo: `Configurable media prioridad`.

- [finanzas/services.py:62](/home/alvax/Code/platforms/avx-django-plataformaelemental/finanzas/services.py#L62)
  Regla: orden de consumo = por `fecha_pago`, luego `id`.
  Tipo: `Configurable alta prioridad`.
  Observacion: esto define un FIFO mensual.

- [finanzas/services.py:72](/home/alvax/Code/platforms/avx-django-plataformaelemental/finanzas/services.py#L72)
  Regla: si encuentra pago disponible, estado `consumido`; si no, `deuda`.
  Tipo: `Configurable alta prioridad`.

- [finanzas/services.py:123](/home/alvax/Code/platforms/avx-django-plataformaelemental/finanzas/services.py#L123)
  Regla: solo se pueden asociar manualmente asistencias `presentes` a un pago.
  Tipo: `Configurable media prioridad`.

- [finanzas/services.py:129](/home/alvax/Code/platforms/avx-django-plataformaelemental/finanzas/services.py#L129)
  Regla: asociacion manual solo dentro del mismo mes y anio.
  Tipo: `Configurable alta prioridad`.

- [finanzas/services.py:144](/home/alvax/Code/platforms/avx-django-plataformaelemental/finanzas/services.py#L144)
  Regla: un pago nuevo imputa deudas previas del mismo periodo.
  Tipo: `Configurable alta prioridad`.

- [finanzas/services.py:154](/home/alvax/Code/platforms/avx-django-plataformaelemental/finanzas/services.py#L154)
  Regla: la imputacion de deudas tambien sigue orden `clase_fecha`, `id`.
  Tipo: `Configurable alta prioridad`.

### 9. Transacciones

#### `database/models.py`
- [database/models.py:569](/home/alvax/Code/platforms/avx-django-plataformaelemental/database/models.py#L569)
  Regla: tipos de transaccion `ingreso` y `egreso`.
  Tipo: `Mantener en codigo`.

#### `finanzas/forms.py`
- [finanzas/forms.py:372](/home/alvax/Code/platforms/avx-django-plataformaelemental/finanzas/forms.py#L372)
  Regla: el tipo de transaccion se deriva automaticamente desde la categoria.
  Tipo: `Configurable media prioridad`.
  Observacion: hoy evita inconsistencias, pero es una regla funcional importante.

- [finanzas/forms.py:377](/home/alvax/Code/platforms/avx-django-plataformaelemental/finanzas/forms.py#L377)
  Regla: todos los documentos tributarios asociados a una transaccion deben ser de la misma organizacion.
  Tipo: `Mantener en codigo`.

### 10. Reportes y clasificaciones financieras

#### `finanzas/views.py`
- [finanzas/views.py:56](/home/alvax/Code/platforms/avx-django-plataformaelemental/finanzas/views.py#L56)
  Regla: catalogo fijo de ayudas y textos explicativos por seccion.
  Tipo: `Configurable media prioridad`.
  Observacion: es contenido de negocio/UX, no infraestructura.

- [finanzas/views.py:248](/home/alvax/Code/platforms/avx-django-plataformaelemental/finanzas/views.py#L248)
  Regla: un documento se clasifica como ingreso o egreso comparando organizacion con emisor/receptor por RUT y luego por nombre.
  Tipo: `Configurable alta prioridad`.

- [finanzas/views.py:292](/home/alvax/Code/platforms/avx-django-plataformaelemental/finanzas/views.py#L292)
  Regla: la disciplina principal se calcula como la disciplina con mas asistencias `presente` de la persona dentro de la organizacion.
  Tipo: `Configurable alta prioridad`.

- [finanzas/views.py:322](/home/alvax/Code/platforms/avx-django-plataformaelemental/finanzas/views.py#L322)
  Regla: dashboard financiero mezcla pagos academicos con transacciones de caja.
  Tipo: `Configurable alta prioridad`.

- [finanzas/views.py:329](/home/alvax/Code/platforms/avx-django-plataformaelemental/finanzas/views.py#L329)
  Regla: `iva_debito` del dashboard sale solo desde pagos.
  Tipo: `Configurable media prioridad`.

- [finanzas/views.py:330](/home/alvax/Code/platforms/avx-django-plataformaelemental/finanzas/views.py#L330)
  Regla: `ingresos_exentos` se calcula como pagos con `monto_iva = 0`.
  Tipo: `Configurable media prioridad`.

- [finanzas/views.py:480](/home/alvax/Code/platforms/avx-django-plataformaelemental/finanzas/views.py#L480)
  Regla: etiqueta fiscal del pago = `Afecta` si tiene IVA, si no `Exenta`.
  Tipo: `Configurable media prioridad`.

- [finanzas/views.py:482](/home/alvax/Code/platforms/avx-django-plataformaelemental/finanzas/views.py#L482)
  Regla: texto copiable del pago = `Taller de {disciplina} - {plan} ({persona})`.
  Tipo: `Configurable alta prioridad`.

- [finanzas/views.py:590](/home/alvax/Code/platforms/avx-django-plataformaelemental/finanzas/views.py#L590)
  Regla: cards de documentos tributarios muestran IVA, retencion, pagos y transacciones asociadas.
  Tipo: `Configurable media prioridad`.

- [finanzas/views.py:599](/home/alvax/Code/platforms/avx-django-plataformaelemental/finanzas/views.py#L599)
  Regla: totales de ingresos y egresos documentales se calculan segun el rol financiero inferido del documento.
  Tipo: `Configurable alta prioridad`.

- [finanzas/views.py:949](/home/alvax/Code/platforms/avx-django-plataformaelemental/finanzas/views.py#L949)
  Regla: cards de transacciones muestran total, ingresos, egresos y balance.
  Tipo: `Configurable media prioridad`.

### 11. Carga asistida de documentos

#### `finanzas/views.py`
- [finanzas/views.py:135](/home/alvax/Code/platforms/avx-django-plataformaelemental/finanzas/views.py#L135)
  Regla: la carga asistida usa un solo input y detecta XML/PDF por nombre, MIME y firma.
  Tipo: `Configurable media prioridad`.

- [finanzas/views.py:204](/home/alvax/Code/platforms/avx-django-plataformaelemental/finanzas/views.py#L204)
  Regla: el flujo de revision exige confirmacion humana antes de guardar.
  Tipo: `Mantener en codigo`.
  Observacion: es una decision estructural sana del sistema.

- [finanzas/views.py:649](/home/alvax/Code/platforms/avx-django-plataformaelemental/finanzas/views.py#L649)
  Regla: al confirmar importacion, opcionalmente puede guardarse un pago sugerido junto al documento.
  Tipo: `Configurable alta prioridad`.

#### `finanzas/documentos/parsers.py`
- [finanzas/documentos/parsers.py:78](/home/alvax/Code/platforms/avx-django-plataformaelemental/finanzas/documentos/parsers.py#L78)
  Regla: parser de fechas en espanol con meses fijos.
  Tipo: `Mantener en codigo`.

- [finanzas/documentos/parsers.py:117](/home/alvax/Code/platforms/avx-django-plataformaelemental/finanzas/documentos/parsers.py#L117)
  Regla: mapeo DTE `33/34/39/41/61/56` hacia categorias y tipos internos.
  Tipo: `Configurable media prioridad`.
  Observacion: el catalogo legal puede quedar en codigo, pero la activacion por organizacion o por etapa del producto podria parametrizarse.

- [finanzas/documentos/parsers.py:175](/home/alvax/Code/platforms/avx-django-plataformaelemental/finanzas/documentos/parsers.py#L175)
  Regla: moneda inferida = `CLP`.
  Tipo: `Configurable media prioridad`.

- [finanzas/documentos/parsers.py:245](/home/alvax/Code/platforms/avx-django-plataformaelemental/finanzas/documentos/parsers.py#L245)
  Regla: una BHE se normaliza como `fee_receipt` y `boleta_honorarios`.
  Tipo: `Mantener en codigo`.

- [finanzas/documentos/parsers.py:272](/home/alvax/Code/platforms/avx-django-plataformaelemental/finanzas/documentos/parsers.py#L272)
  Regla: una BHE tiene IVA inferido en cero.
  Tipo: `Mantener en codigo`.

- [finanzas/documentos/parsers.py:294](/home/alvax/Code/platforms/avx-django-plataformaelemental/finanzas/documentos/parsers.py#L294)
  Regla: si una BHE XML no trae items, se crea una linea inferida `Prestacion de servicios`.
  Tipo: `Configurable media prioridad`.

- [finanzas/documentos/parsers.py:332](/home/alvax/Code/platforms/avx-django-plataformaelemental/finanzas/documentos/parsers.py#L332)
  Regla: fallback tecnico a `pdftotext` del sistema.
  Tipo: `Mantener en codigo`.

- [finanzas/documentos/parsers.py:350](/home/alvax/Code/platforms/avx-django-plataformaelemental/finanzas/documentos/parsers.py#L350)
  Regla: heuristicas especificas para extraer BHE PDF.
  Tipo: `Configurable media prioridad`.
  Observacion: no conviene exponer regex en UI, pero si conviene tratarlo como politica versionable de importacion.

- [finanzas/documentos/parsers.py:454](/home/alvax/Code/platforms/avx-django-plataformaelemental/finanzas/documentos/parsers.py#L454)
  Regla: deteccion de `Total Honorarios`, retencion y total liquido via patrones fijos.
  Tipo: `Configurable media prioridad`.

- [finanzas/documentos/parsers.py:508](/home/alvax/Code/platforms/avx-django-plataformaelemental/finanzas/documentos/parsers.py#L508)
  Regla: clasificacion PDF por presencia de palabras clave `HONORARIOS`, `FACTURA`, `BOLETA`, `EXENTA`.
  Tipo: `Configurable media prioridad`.

- [finanzas/documentos/parsers.py:658](/home/alvax/Code/platforms/avx-django-plataformaelemental/finanzas/documentos/parsers.py#L658)
  Regla: si el PDF no tiene texto seleccionable util, el parser falla con error.
  Tipo: `Mantener en codigo`.

- [finanzas/documentos/parsers.py:663](/home/alvax/Code/platforms/avx-django-plataformaelemental/finanzas/documentos/parsers.py#L663)
  Regla: todos los PDFs parseados por fallback agregan warning `Parser PDF basico aplicado`.
  Tipo: `Configurable media prioridad`.

- [finanzas/documentos/parsers.py:667](/home/alvax/Code/platforms/avx-django-plataformaelemental/finanzas/documentos/parsers.py#L667)
  Regla: familias XML reconocidas = `dte`, `bhe`, `desconocido`.
  Tipo: `Mantener en codigo`.

### 12. Personas y metricas CRM

#### `personas/views.py`
- [personas/views.py:69](/home/alvax/Code/platforms/avx-django-plataformaelemental/personas/views.py#L69)
  Regla: metricas de organizacion distinguen `ESTUDIANTE` y `PROFESOR`.
  Tipo: `Configurable media prioridad`.

- [personas/views.py:75](/home/alvax/Code/platforms/avx-django-plataformaelemental/personas/views.py#L75)
  Regla: ingresos del CRM de organizacion salen desde `Payment`, no desde `Transaction`.
  Tipo: `Configurable alta prioridad`.

- [personas/views.py:164](/home/alvax/Code/platforms/avx-django-plataformaelemental/personas/views.py#L164)
  Regla: dashboard de personas usa conteos fijos de activas, con usuario, estudiantes, profesores, deuda y pagos.
  Tipo: `Configurable media prioridad`.

- [personas/views.py:292](/home/alvax/Code/platforms/avx-django-plataformaelemental/personas/views.py#L292)
  Regla: filtro `con_deuda` se define solo por `deuda_periodo`.
  Tipo: `Configurable media prioridad`.

- [personas/views.py:429](/home/alvax/Code/platforms/avx-django-plataformaelemental/personas/views.py#L429)
  Regla: el resumen financiero de persona solo se calcula si tiene rol `ESTUDIANTE`.
  Tipo: `Configurable alta prioridad`.

## Priorizacion recomendada

### Primera capa a volver configurable
1. Politica fiscal por organizacion
   - `IVA_RATE`
   - `iva_tasa` por defecto
   - `aplica_iva` por defecto
   - `precio_incluye_iva` por defecto
   - tipo documental por defecto

2. Politica academico-financiera por organizacion
   - consumo solo mismo mes o arrastre
   - orden de consumo de pagos
   - cuando se genera deuda
   - si el pago debe ser solo para estudiantes

3. Politica operativa de pagos
   - metodo por defecto
   - que metodos requieren comprobante
   - si un pago puede existir sin plan
   - como se heredan clases desde plan

4. Politica de importacion tributaria
   - tipos documentales habilitados
   - sugerir pago o no
   - advertencia o bloqueo por duplicado
   - reglas de clasificacion de ingreso/egreso

### Segunda capa a evaluar despues
1. Textos de ayuda de la UI
2. Contenido de cards y reportes
3. Formula de disciplina principal
4. Ventana de anios del filtro superior

## Recomendacion estructural
No conviene hacer una tabla gigante de configuracion general.

Conviene separar al menos en:
- `ConfiguracionFiscalOrganizacion`
- `ConfiguracionAcademicaFinanciera`
- `ConfiguracionImportacionTributaria`

Cada una deberia pertenecer a `Organizacion` y tener valores por defecto razonables.

## Conclusiones
- Hay muchas reglas reales de negocio en codigo, especialmente en `database/models.py`, `finanzas/forms.py`, `finanzas/services.py`, `finanzas/views.py` y `finanzas/documentos/parsers.py`.
- Las mas importantes para externalizar son las fiscales, las de consumo de clases y las de importacion tributaria.
- Las entidades base, estados nucleares e integridad referencial deberian seguir en codigo.

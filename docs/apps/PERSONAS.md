# Personas

Fecha de actualizacion: 2026-06-01

## Proposito
`personas` es el CRM transversal de la plataforma.

Debe concentrar:
- personas
- roles por organizacion
- organizaciones
- vista administrativa consolidada de actividad academica y financiera

## Reglas vigentes
- La administracion de organizaciones vive en esta app y no en `asistencias`.
- Los perfiles de persona deben mantener filtros globales de periodo y organizacion.
- El contexto global de filtros, persona navegante y organizacion activa debe importarse desde `plataformaelemental.context`, no desde vistas de otra app.
- Si no hay filtros explicitos en la URL, el periodo global debe partir en el mes y año actuales, y la organizacion debe partir en `Todas`.
- Los filtros globales deben autoaplicarse al cambiar `mes`, `anio` u `organizacion`, sin boton `Aplicar filtros`.
- `periodo_mes` y `periodo_anio` deben aceptar `Todos` y reflejar esa seleccion tanto en los listados como en los resumentes de organizaciones y personas.
- Desde aqui se debe poder ver actividad academica y financiera relevante de cada persona dentro del periodo seleccionado.
- El `RUT` de una persona se edita solo desde `personas`, es opcional y debe validarse como RUT chileno.
- Para crear o editar una persona debe existir al menos un dato de identidad operacional: `RUT`, email o telefono.
- El telefono se normaliza en backend para uso operacional; no es unico porque puede compartirse entre familia, apoderados o contactos.
- Los modelos propios de personas, roles y organizaciones viven en `personas.models`.

## Decisiones funcionales vigentes
- Debe existir listado, detalle, creacion y edicion de organizaciones.
- `Persona.identificador` fue reemplazado por `Persona.rut`; el valor se normaliza y guarda formateado como RUT chileno cuando se ingresa desde formularios CRM.
- `Persona.email` mantiene una restriccion unica existente en base de datos; no se endurece ni se relaja en v1.0 sin auditoria previa.
- `Persona.rut` se valida como unico global en formularios y validacion de modelo cuando existe, pero no se agrego constraint de base de datos hasta auditar y corregir datos productivos existentes.
- Las altas rapidas desde `asistencias` y `finanzas` deben capturar telefono como identidad minima y guardarlo normalizado.
- El alta rapida desde detalle de sesion puede agregar la persona recien creada a la asistencia de esa sesion mediante switch explicito; la organizacion usada siempre es la organizacion dueña de la sesion.
- El comando `python manage.py auditar_datos_v1` revisa datos existentes sin modificar la base: personas sin identidad, duplicados de RUT/email/telefono, telefonos inconsistentes y posibles duplicados por nombre.
- En `personas/listado`, el filtro por `rol` debe considerar asignaciones activas e inactivas; el filtro `estado` controla el estado de la `Persona`, no la vigencia del rol. La tabla debe mostrar si cada rol esta activo o inactivo.
- En `personas/listado`, la tabla usa paginacion Django en servidor de 25 filas por pagina. DataTables no debe cargar todas las personas en HTML inicial.
- El listado conserva filtros `periodo_mes`, `periodo_anio`, `organizacion`, busqueda y filtros propios al cambiar de pagina.
- Las metricas por persona del listado se calculan para el periodo/organizacion activos y se evalúan solo sobre la pagina visible.
- Si la organizacion esta en `Todas`, el listado sigue siendo paginado para evitar una carga inicial masiva.
- El detalle de persona muestra pagos, consumos y documentos tributarios relacionados sin duplicar archivos.
- El detalle de persona debe separar la columna operativa derecha entre `Perfil estudiante` y `Perfil profesor`; la columna izquierda de datos personales y acceso al sistema debe ser mas compacta, y no deben mostrarse bloques de rol que no apliquen a esa persona.
- En `personas/<id>/`, el bloque `Perfil estudiante` debe permitir asociar pagos disponibles a asistencias presentes, respetando periodo, organizacion, saldo del pago y las validaciones de `finanzas`.
- La configuracion de honorarios de un profesor no debe hardcodearse ni vivir en organizacion global: `valor por clase` y `retencion SII` deben guardarse en `PersonaRol` para el rol `PROFESOR`, porque dependen de la combinacion persona + organizacion.
- En `personas/<id>/`, el bloque `Perfil profesor` debe mostrar el resumen economico del periodo con cards separadas para `pago bruto`, `retencion SII` en monto y `monto neto`; el porcentaje de retencion se configura en el rol, pero no se muestra como card principal.
- En `personas/<id>/`, la tabla de sesiones del `Perfil profesor` debe ofrecer acciones operativas de sesion para `Ver sesion`, `Agregar asistentes` y cambiar estado de sesion desde un selector autoaplicado, manteniendo los filtros globales y abriendo el modal vigente de asistentes.
- `personas` no reemplaza la operacion diaria de `asistencias`; cumple una funcion administrativa y transversal.
- Las acciones rapidas de estudiantes desde vistas operativas deben apuntar a perfiles consolidados en `personas/<id>/` y preservar filtros globales.

## Relacion con otras apps
- `asistencias` usa perfiles operativos y flujos rapidos.
- `finanzas` mantiene la logica de cobros, documentos y caja.
- `personas` conecta ambas vistas desde una perspectiva administrativa.
- El criterio transversal de roles y permisos vive en `docs/arquitectura/PERMISOS_Y_ROLES.md`.

## Rol transversal
`personas` puede consolidar informacion academica y financiera para lectura administrativa.

Permitido:
- consultar resumen academico
- consultar resumen de cobranza
- mostrar pagos, consumos y documentos relacionados

No permitido:
- implementar reglas de imputacion
- calcular deuda directamente en views/templates
- editar documentos tributarios desde perfiles
- importar helpers privados desde otras apps

## API
La API de datos de `personas` queda desactivada en v1.0.

Motivo:
- no existe consumidor real actual
- reduce superficie de exposicion de datos personales
- evita mantener endpoints "por si acaso"

Si en el futuro se reactiva, debe definirse por caso de uso concreto, con permisos, filtros por organizacion y tests especificos.

# Django Admin

Fecha de actualizacion: 2026-08-09

El Django Admin de Plataforma Elemental es una herramienta interna de soporte, revision y diagnostico.

No reemplaza la operacion diaria de `Elemental Apps`. Los flujos normales de personas, asistencias, pagos, documentos, transacciones y reportes deben seguir ocurriendo en las vistas propias de la plataforma.

## Alcance v1.0

Modelos cubiertos para soporte:

- `personas.Persona`
- `personas.PersonaRol`
- `personas.Organizacion`
- `asistencias.SesionClase`
- `asistencias.Asistencia`
- `finanzas.Payment`
- `finanzas.Transaction`
- `finanzas.DocumentoTributario`
- `auditoria.AuditLog`

Tambien existen admins auxiliares para modelos de catalogo o compatibilidad, pero no deben convertirse en operacion diaria.

## Reglas

- No usar admin para cerrar meses, recalcular saldos ni imputar pagos.
- No crear acciones masivas destructivas.
- `actions = None` deshabilita acciones masivas en Organización, Persona,
  PersonaRol, SesionClase, Asistencia, ClaseLiberada, LotePago, Payment,
  DocumentoTributario, Transaction y AuditLog.
- No está deshabilitado de forma uniforme: Rol, Disciplina, BloqueHorario,
  PaymentPlan, AttendanceConsumption, Category y ApiAccessKey conservan las
  acciones estándar del Admin según permisos Django. Esto es un riesgo operativo.
- Evitar calculos caros en `list_display`.
- Usar `select_related`, `prefetch_related` o `annotate` cuando una columna derive de relaciones.
- No listar documentos M2M completos en columnas.
- No mostrar propiedades que hagan consultas por fila, como saldo de clases.
- No editar snapshots tributarios sin una razon operativa clara.

## Campos pesados o sensibles

En documentos tributarios, los campos de archivo y metadata grande quedan como solo lectura desde admin:

- `archivo_pdf`
- `archivo_xml`
- `metadata_extra`

El objetivo es revisar, no manipular payloads tributarios desde admin.

## Auditoria

`AuditLog` es solo lectura:

- no se puede crear desde admin;
- no se puede editar;
- no se puede eliminar.

La revision de logs se hace desde `Auditoria > Registros de auditoria`.

## Monitor archivado

`monitor` esta archivado y no forma parte activa de `Elemental Apps` v1.0.

Se mantiene instalado temporalmente por compatibilidad con migraciones o datos historicos, pero sus modelos no se registran en Django Admin.

No debe operarse como parte del producto principal.

## Limites conocidos

- El admin no aplica la matriz organizacional de la UI principal.
- El admin es para staff/superuser.
- Los permisos nativos del Admin no equivalen a la matriz organizacional de
  `PersonaRol`; una cuenta staff debe revisarse separadamente.
- La asignacion masiva de roles existente en `PersonaRol` es sensible y debe usarse con criterio.
- No hay acciones de recuperacion, recalculo o conciliacion desde admin.
- `AuditLog` puede ser visto por cualquier `is_staff`; no filtra por organización.

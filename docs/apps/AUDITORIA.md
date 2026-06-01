# Auditoria

`auditoria` registra trazabilidad operativa minima para acciones sensibles de Plataforma Elemental v1.0.

No es SIEM, no es event sourcing y no reemplaza respaldos ni logs de servidor. Su objetivo es responder: quien hizo que, cuando y sobre que entidad.

## Modelo

`AuditLog` guarda:

- `usuario`: usuario Django que ejecuto la accion, si existe.
- `fecha`: fecha/hora del registro.
- `accion`: convencion textual, por ejemplo `crear`, `editar`, `eliminar`, `asociar`, `cambiar_estado`, `importar`.
- `dominio`: `personas`, `asistencias` o `finanzas`.
- `modelo`: etiqueta Django del modelo afectado.
- `objeto_id`: identificador del objeto afectado como texto.
- `organizacion`: organizacion relacionada cuando aplica.
- `resumen`: descripcion legible breve.
- `metadata`: JSON breve con ids, montos, fechas o cambios relevantes.

Indices principales:

- `dominio`, `modelo`, `objeto_id`.
- `organizacion`, `fecha`.
- `usuario`, `fecha`.

## Helper

La escritura se centraliza en `auditoria/services.py`:

- `registrar_auditoria(...)`: registra una accion puntual.
- `registrar_cambio(...)`: registra diferencias entre valores antes/despues solo para campos declarados.

Los registros se crean con `transaction.on_commit()` para evitar auditar operaciones que luego fallen o hagan rollback.

Si el logging falla por un error no critico, se registra `logger.warning` y la operacion principal no se bloquea.

## Datos sensibles

No se guardan RUT, email ni telefono completos en cambios de Persona.

Para esos campos se guarda solo:

```json
{
  "cambio": true,
  "antes_presente": true,
  "despues_presente": true
}
```

En finanzas se permiten ids, montos y fechas. No se guardan adjuntos, XML, PDFs, payloads tributarios completos ni snapshots gigantes.

## Flujos auditados

Personas:

- Creacion de persona desde vistas HTML.
- Edicion de persona.
- Agregar/reactivar/configurar/toggle de roles desde perfil o edicion.

Asistencias:

- Creacion de sesion.
- Edicion de sesion.
- Cambio de estado de sesion.
- Alta rapida desde sesion.
- Alta rapida persona + asistencia.
- Agregar asistentes con log agregado por operacion.
- Eliminar asistente.
- Eliminar sesion.

Finanzas:

- Crear, editar y eliminar pagos.
- Crear persona rapida desde pagos.
- Crear, editar, importar y eliminar documentos tributarios.
- Crear pago sugerido al confirmar importacion tributaria.
- Crear, editar y eliminar transacciones.
- Asociaciones de documento a pago/transaccion cuando ocurren por los formularios auditados.

## Fuera de alcance v1.0

No se audita:

- GET o vistas de lectura.
- Exports.
- API minima (`health`, `status`, `version`, `me`).
- Monitor archivado.
- Signals de finanzas.
- Imputacion automatica de consumos.
- Parse preview de documentos tributarios.
- Cambios derivados automaticos que no sean accion directa del usuario.

## Revision

Los logs se revisan desde Django Admin en `Auditoria > Registros de auditoria`.

El admin de `AuditLog` es solo lectura:

- no permite crear logs manualmente;
- no permite editar logs;
- no permite eliminar logs.

## Limitaciones conocidas

- No hay pantalla frontend propia de auditoria.
- No hay retencion/expurgo automatico de logs.
- No se auditan exports ni API.
- Algunas acciones compuestas pueden generar dos logs razonables, por ejemplo persona creada y asistencia creada desde alta rapida.
- Las inconsistencias historicas previas a esta migracion no quedan auditadas retroactivamente.

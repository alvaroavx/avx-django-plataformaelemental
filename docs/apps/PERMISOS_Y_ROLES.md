# Permisos Y Roles

Fecha de actualizacion: 2026-07-26

## Proposito
Este documento define la matriz minima de permisos v1.0 para vistas HTML internas.

La fuente de roles sigue siendo `PersonaRol`: una persona puede tener permisos distintos por organizacion.

## Roles v1.0
- `admin`: codigos aceptados `ADMIN`, `ADMINISTRADOR`, `SUPERADMIN`.
- `finanzas`: codigos aceptados `FINANZAS`.
- `profesor`: codigos aceptados `PROFESOR`.
- `solo_lectura`: codigos aceptados `SOLO_LECTURA`, `LECTURA`, `READ_ONLY`.

`superuser` y `staff` de Django conservan acceso total operativo.

## Matriz minima
| Accion | admin | finanzas | profesor | solo_lectura |
|---|---:|---:|---:|---:|
| Ver finanzas | si | si | no | si |
| Crear/editar pagos | si | si | no | no |
| Crear/editar transacciones | si | si | no | no |
| Crear/editar documentos tributarios | si | si | no | no |
| Exportar datos | si | si | no | no |
| Editar asistencias | si | no | no | no |
| Administrar personas | si | no | no | no |
| Administrar sesiones | si | no | no | no |

## Decisiones
- Las vistas de `finanzas` permiten lectura a `admin`, `finanzas` y `solo_lectura`.
- Cualquier `POST` financiero requiere rol operativo especifico: pagos, transacciones o documentos.
- Los exports existentes quedan protegidos por permiso de exportacion, aunque los exports v1.0 definitivos se implementen despues.
- El rol `profesor` no accede a finanzas completa.
- Si hay filtro de organizacion activo, el rol debe existir activo en esa organizacion.
- Si no hay organizacion filtrada, el chequeo permite acceso si el usuario tiene el rol activo en alguna organizacion. Esta es una limitacion conocida para mantener compatibilidad con vistas globales.

## Como asignar o revisar permisos
1. Abrir una persona en `personas/<id>/`.
2. Revisar o agregar `PersonaRol` para la organizacion correspondiente.
3. Usar codigo de rol estable: `ADMINISTRADOR`, `FINANZAS`, `PROFESOR` o `SOLO_LECTURA`.
4. Verificar que la asignacion este activa.

## Limitaciones conocidas
- La matriz no reemplaza permisos granulares de Django `auth_permission`.
- Las apps `asistencias` y `personas` aun usan decoradores historicos por rol admin para varias pantallas.

## Matriz operativa Sprint 2

| Acción | Administración autorizada | Profesora asignada | Profesora no asignada | Otra organización |
| --- | ---: | ---: | ---: | ---: |
| Ver sesión | Sí | Sí | No | No |
| Ver asistentes | Sí | Sí | No | No |
| Buscar personas elegibles | Sí | Sí, limitada a la organización de la sesión | No | No |
| Agregar asistente | Sí | Sí | No | No |
| Registrar/corregir asistencia | Sí | Sí | No | No |
| Ver estado de consumo necesario para operar | Sí | Sí, limitado a la sesión | No | No |
| Quitar asistente | Sí | No | No | No |
| Liberar clase | Sí | No | No | No |
| Revertir clase liberada | Sí | No | No | No |
| Revertir pago | Sí | No | No | No |

La asignación de profesora se comprueba contra `SesionClase.profesores` y el rol `PROFESOR` activo en la organización real de la sesión. El filtro de organización enviado por la interfaz no concede acceso.

Google continúa siendo solo autenticación detrás de sus flags. No crea roles, asignaciones ni permisos, y el acceso real para profesoras continúa sin activarse.
- `staff` conserva bypass total; si se quiere separar soporte tecnico de operacion, debe revisarse antes de abrir acceso a terceros.
- La opcion `solo_lectura` puede ver finanzas, pero no debe crear, editar, borrar ni exportar.

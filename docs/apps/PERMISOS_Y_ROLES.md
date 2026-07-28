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

En Asistencias, solo `superuser` de Django conserva acceso total operativo. `is_staff` habilita el acceso al Django Admin según los permisos nativos de Django, pero no concede por sí solo organizaciones ni capacidades operativas de asistencia.

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
- `staff` no conserva bypass operativo en Asistencias. Necesita `Persona`, `PersonaRol` activo y organización autorizada como cualquier cuenta ordinaria; el rol de dominio `STAFF_ASISTENCIA` no debe confundirse con `User.is_staff`.
- Los consumidores históricos de los helpers compartidos fuera de Asistencias conservan temporalmente su compatibilidad anterior. Su cierre multi-organización corresponde al Sprint 6 y no se declara resuelto aquí.
- La opcion `solo_lectura` puede ver finanzas, pero no debe crear, editar, borrar ni exportar.

## Matriz de superficies para piloto cerrado

`404` significa que un recurso ajeno y uno inexistente son deliberadamente indistinguibles. `403` se usa cuando el actor carece de la capacidad general para esa superficie, sin confirmar la existencia de un objeto concreto.

| Actor | HTML y URL directa de sesión | POST asistencia | JSON y búsqueda | Personas | Archivos/descargas financieras | Exports | Configuración administrativa |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Anónimo | Redirección a login | `403` sin operar | `403`, sin datos | Redirección a login | Redirección a login | Redirección a login | Redirección a login |
| Autenticado sin rol | Sin sesiones; detalle `404` | `403` | `403` | `403` | `403` | `403` | No |
| Rol inactivo | Igual que sin rol | `403` | `403` | Según otros roles activos; ninguno por el rol inactivo | Según otros roles activos | Según otros roles activos | No |
| Staff Django sin rol | Sin sesiones; detalle `404` | `403` | `403` | No | No | No | Django Admin según permisos Django |
| Profesora asignada | “Hoy” y detalle de sus sesiones | Sí, solo sesión asignada | Sí, personas elegibles de la organización | No | No | No | No |
| Profesora no asignada | Sesión ajena `404` | `404` | `404` | No | No | No | No |
| Usuario de otra organización | Recurso ajeno `404` | `404` | `404` | Queryset aislado | Recurso ajeno `404` | Organización ajena no disponible | No |
| Administración autorizada | Sí en su organización | Sí | Sí | Sí en su organización | Sí mediante ruta autorizada | Sí con permiso explícito | Operación Elemental de su organización |
| Cuenta revocada | Pierde acceso en la siguiente petición | Sin escritura | Sin resultados | Según roles aún activos; ninguno si se revocaron | Sin acceso por rol revocado | Sin acceso por rol revocado | No |
| Superusuario de emergencia | Acceso global de recuperación | Sí | Sí | Sí | Sí | Sí | Django Admin |

Superficies no aplicables:

- No existe API de datos de Personas, Asistencias o Finanzas en v1.0.
- No existe endpoint JSON específico para disciplinas.
- La jornada móvil no ofrece archivos, descargas ni exports a profesoras.

La sesión Django no constituye autorización persistente. Cada petición vuelve a consultar `User.is_active`, `PersonaRol.activo`, organización y asignación de profesora cuando corresponde.

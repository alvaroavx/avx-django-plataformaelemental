# Permisos Y Roles

Fecha de actualizacion: 2026-08-09

## Proposito
Este documento define el criterio transversal de roles y permisos.

Los roles ya afectan navegacion, filtros, operacion academica, pagos y perfiles. Por eso no deben crecer de forma implicita.

## Modelo Actual
La identidad vive en `personas`.

Modelos principales:
- `Persona`
- `Organizacion`
- `Rol`
- `PersonaRol`

Relacion central:

```text
Persona -- PersonaRol -- Rol
              |
         Organizacion
```

Regla:
- El rol se asigna por persona y organizacion.
- Una persona puede tener roles distintos en organizaciones distintas.
- No puede repetirse la misma combinacion `persona + rol + organizacion`.

## Roles Funcionales Vigentes
Los aliases normalizados por codigo son `admin`, `finanzas`, `profesor`,
`solo_lectura` y `staff_asistencia`. `ESTUDIANTE` representa pertenencia
operacional, pero no concede por si solo acciones administrativas.

## Superuser Y Staff
Regla operativa:
- La regla objetivo es que solo `superuser` pueda saltar chequeos operativos de rol y organización.
- Asistencias aplica esa regla de forma explícita: `is_staff` controla el acceso al Django Admin según permisos Django, pero no concede organizaciones ni acceso operativo de asistencia.
- Personas y Finanzas conservan temporalmente el bypass histórico de `is_staff`
  porque sus decoradores usan el valor por defecto `permitir_staff_global=True`.
  Asistencias lo desactiva en sus superficies operativas endurecidas.
- Esto no reemplaza una politica formal de permisos.
- Toda acción sensible requiere rol por organización, salvo la excepción global explícita de `superuser`.

## Reglas Por Rol

### Estudiante
Uso:
- puede tener asistencias,
- puede tener pagos,
- puede tener consumos financieros,
- puede aparecer en seguimiento de deuda/saldo.

Reglas:
- `Payment.persona` debe apuntar a personas con rol `ESTUDIANTE` activo segun organizacion cuando el flujo lo valide.
- El alta rapida desde pagos o asistencias puede crear persona con rol `ESTUDIANTE` en la organizacion filtrada.

### Profesor
Uso:
- puede dictar sesiones,
- puede aparecer como profesor en `SesionClase.profesores`,
- puede tener configuracion economica en `PersonaRol`.

Reglas:
- Para seleccion operativa, profesor vigente equivale a `Persona.activo=True` y `PersonaRol.activo=True` con rol `PROFESOR`.
- `valor_clase` y `retencion_sii` viven en `PersonaRol`, porque dependen de persona + organizacion.
- El espacio `/profesor/` exige además `AsignacionProfesorDisciplina` para cada
  clase y `SesionClase.profesores` para una sesión concreta.
- Ver/agregar alumnos y registrar pagos exige `AlumnoDisciplina` operativa en una
  disciplina asignada. Un rol profesor de la misma organización no basta.
- Operativa significa activa y explícita, o histórica con actor y fecha de
  revisión administrativa. Ninguna relación inferida desde sesiones o
  asistencias concede permisos actuales por sí sola.
- El profesor no recibe `ACCION_VER_FINANZAS`; sus pagos se resuelven en vistas
  propias con queryset por disciplina y matrícula, sin abrir finanzas globales.

## Acceso HTML
Estado actual:
- Las vistas HTML requieren autenticacion.
- Algunas vistas usan decoradores de acceso por rol.
- La politica fina todavia no esta centralizada como matriz completa.

Reglas:
- No implementar chequeos de permiso dispersos sin test.
- Si una accion modifica datos criticos, debe tener permiso explicito o al menos quedar cubierta por test de acceso.
- Las reglas de permisos deben considerar organizacion activa, no solo rol global.
- En Asistencias, todo usuario que no sea `superuser` requiere organización y rol vigentes; `Todas` no amplía el acceso y `is_staff` no altera esta regla. Personas y Finanzas todavía conservan el bypass histórico descrito arriba.
- `personas.gestionar_solicitudes_acceso` es un permiso Django global independiente. No se deriva de `staff` ni de `PersonaRol`; solo superusuarios y usuarios a quienes se asigna deliberadamente el permiso pueden administrar solicitudes.

## API
La API usa:
- token DRF para usuarios,
- API key de solo lectura para consultas.

Reglas:
- API key no permite escrituras.
- Escrituras requieren usuario autenticado.
- La API no debe inferir permisos administrativos solo por conocer una API key.

Detalle:
- [docs/apps/API.md](../apps/API.md)

## Riesgos Actuales
- Roles administrativos no estan formalizados como matriz completa.
- Hay diferencias entre rol activo de persona y estado activo de persona.
- Algunas pantallas filtran por rol para operar, pero no necesariamente eso equivale a permiso de escritura.
- Si se agregan mas apps, roles y permisos pueden volverse ambiguos rapidamente.

## Recomendacion
Antes de agregar permisos mas complejos:
- definir matriz de acciones sensibles,
- definir si permiso depende de organizacion,
- definir el rol organizacional requerido o justificar expresamente la excepción de `superuser`,
- agregar tests de acceso,
- documentar en este archivo.

## Riesgo pendiente
La matriz de acciones existe en `personas/permissions.py`, pero no constituye
todavia un cierre transversal: el bypass de `staff`, el acceso sin organizacion
activa, Django Admin, comandos y futuras vistas deben auditarse como superficies
separadas. La fotografia y prioridad viven en `docs/ESTADO_ACTUAL.md`.

# Checklist De Cambios

Fecha de actualizacion: 2026-05-11

## Proposito
Este checklist reduce documentacion falsa y cambios incompletos.

Debe usarse antes de cerrar cambios funcionales, visuales, de modelo, deploy o documentacion transversal.

## Checklist General
- Confirmar que el cambio responde al requerimiento actual y no agrega alcance innecesario.
- Revisar `AGENTS.md`.
- Revisar `docs/proceso/DECISIONES.md`.
- Revisar el documento duenio de la app o arquitectura tocada.
- Mantener el cambio pequeno y verificable.
- No duplicar logica existente.
- No mover responsabilidades sin actualizar documentacion.
- No importar helpers desde `views.py` de otra app.
- Confirmar que desktop y responsive resuelven la misma necesidad si hay cambio visual.

## Si Toca Modelos O Migraciones
- Revisar [docs/arquitectura/MODELO_DATOS.md](../arquitectura/MODELO_DATOS.md).
- Confirmar app duena del modelo.
- Revisar dependencias con `database` antes de tocar migraciones.
- Ejecutar:

```bash
python manage.py makemigrations --check --dry-run
```

- Si hay cambios de modelo esperados, crear migracion y revisarla.
- Confirmar reglas de `CASCADE`, `PROTECT`, `SET_NULL`, unicidades e indices.
- Si agrega una regla critica, agregar test.

## Si Toca Finanzas O Cobranza
- Revisar [docs/apps/FINANZAS.md](../apps/FINANZAS.md).
- Confirmar si el cambio pertenece a cobranza operacional o finanzas/contabilidad.
- No mezclar parsing tributario con imputacion de pagos.
- Si toca deuda, saldo, pagos, consumos o imputacion, agregar o ajustar test de regla.
- Mantener queries puras en selectors y reglas de negocio en services.

## Si Toca Asistencias
- Revisar [docs/apps/ASISTENCIAS.md](../apps/ASISTENCIAS.md).
- Confirmar que `asistencias` no calcula contabilidad.
- Si muestra estado financiero, debe consultar servicios/selectors financieros, no duplicar reglas.
- Si cambia sesiones, asistencia o estados, validar impacto en `AttendanceConsumption`.

## Si Toca Personas
- Revisar [docs/apps/PERSONAS.md](../apps/PERSONAS.md).
- Confirmar que perfiles consolidados no implementen reglas de imputacion ni deuda.
- Si toca `PersonaRol`, revisar impacto en profesores, pago bruto, retencion SII y monto neto.

## Si Toca API
- Revisar [docs/apps/API.md](../apps/API.md).
- Confirmar autenticacion requerida.
- Confirmar si la API key puede acceder al endpoint.
- No exponer escrituras con API key de solo lectura.
- Revisar throttling si agrega endpoint sensible.

## Si Toca Navegacion O Filtros
- Revisar [docs/arquitectura/NAVEGACION_Y_CONTEXTO.md](../arquitectura/NAVEGACION_Y_CONTEXTO.md).
- Mantener `periodo_mes`, `periodo_anio` y `organizacion` al navegar.
- Si falta filtro explicito, usar mes y anio actuales; organizacion `Todas`.
- No reintroducir boton `Aplicar filtros` para filtros globales.

## Si Toca Deploy, Seguridad O Entorno
- Revisar [docs/operacion/DEPLOY.md](../operacion/DEPLOY.md).
- Revisar [docs/operacion/SEGURIDAD_PRODUCCION.md](../operacion/SEGURIDAD_PRODUCCION.md).
- No imprimir secretos.
- Mantener compatibilidad con `DEPLOY_ENV_FILE`.
- Si cambia base de datos, backup o migraciones productivas, documentar rollback.

## Validacion Minima
- Para cambios generales:

```bash
python manage.py check
```

- Para cambios en apps principales:

```bash
python manage.py test asistencias.tests personas.tests finanzas.tests api.tests
```

- Para cambios solo documentales no se requieren tests, pero se debe revisar enlaces y rutas.

## Documentacion
- Si el cambio es local, actualizar el `.md` de la app.
- Si el cambio es transversal, actualizar `docs/arquitectura/PLATAFORMA.md` o el documento especializado correspondiente.
- Si cambia la forma de trabajar, actualizar `docs/proceso/DECISIONES.md` y este checklist.
- Si crea deuda tecnica consciente, registrarla en [docs/arquitectura/DEUDA_TECNICA.md](../arquitectura/DEUDA_TECNICA.md).
- Si resuelve deuda tecnica registrada, eliminarla o actualizar su estado.

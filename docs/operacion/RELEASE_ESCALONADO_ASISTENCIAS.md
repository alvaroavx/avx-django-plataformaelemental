# Release escalonado de asistencias

Estado: diseño implementado localmente, sin commit, tag ni producción.

Este procedimiento reemplaza la ejecución manual por SSH del release de
`asistencias.0005`. El workflow rutinario sigue siendo `deploy.yml`; este
workflow separado solo se ejecuta mediante `workflow_dispatch` desde un tag.
Los pushes a `main` no despliegan.

## Etapas independientes

### Preflight

El dispatch `etapa=preflight` requiere el environment protegido
`production-readonly`. Usa una clave SSH restringida y no detiene Gunicorn.
Verifica tag anotado, `tag^{}`, SHA, padre, worktree, dump, snapshot, espacio,
servicio y migraciones. También verifica `origen` en ambas relaciones, incluida
su nulabilidad y default.

El estado que motivó esta corrección (`0004` aplicada, `0005` pendiente,
`origen` existente sin default `explicita`) queda rechazado por el preflight
antiguo y es la ruta sintética cubierta por las pruebas del nuevo script.

El marcador JSON se guarda fuera del checkout, contiene SHA/tag/padre,
checksum del dump, timestamp, vencimiento breve y conteos agregados. No contiene
nombres, correos, IDs personales ni dumps.

### Apply

El dispatch `etapa=apply` requiere el environment `production`, aprobación
humana y un marcador vigente del mismo tag y SHA. La concurrencia
`release-asistencias-production` impide dos ejecuciones simultáneas.

Antes de detener la aplicación se vuelve a validar identidad, marcador y estado.
Luego se ejecutan exclusivamente:

```text
asistencias.0004b_reparar_precondiciones_0005
asistencias.0005_reparar_schema_0004_aplicada_precommit_v2
```

No se usa `migrate` global, `--fake`, downgrade ni SQL manual.

Si falla antes de iniciar una migración, se recuperan el checkout previo,
requirements compatibles, Gunicorn y el smoke básico. Si una migración ya
comenzó, el proceso queda forward-only en mantenimiento y no restaura ni
revierte automáticamente.

Después de éxito se ejecutan validación, reporte, `collectstatic`, reinicio y
smoke. La evidencia se conserva sanitizada fuera del repositorio y solo se
puede subir a Actions si no contiene datos productivos.

## Migraciones

`0004b_reparar_precondiciones_0005` es una reparación forward explícita para el
estado parcialmente preparado. No activa relaciones: los registros sin actor
administrativo quedan históricos e inactivos.

`0005_reparar_schema_0004_aplicada_precommit_v2` es una migración de reemplazo:
no edita el archivo `0005` publicado, pero hace que el grafo operativo dependa
de `0004b` antes de ejecutar sus operaciones equivalentes.

`0006_merge_0004b_y_0005` une las dos ramas resultantes. Toda migración futura
debe depender de `0006_merge_0004b_y_0005`; no se deben crear migraciones nuevas
que dependan directamente de `0005`.

Antes de cualquier release se debe restaurar el dump productivo en una máquina
aislada y controlada, fuera de Actions, reproducir el esquema ambiguo y ejecutar
ambas migraciones. El dump, logs crudos y datos personales nunca se suben a
GitHub.

## Pruebas

CI valida el contrato del workflow, el grafo `0004b`/`0005`/`0006`, el gate
sintético de `origen` y que el preflight no detenga Gunicorn. La reproducción
real contra el dump se ejecuta fuera de CI y se documenta solo con resultados
agregados.

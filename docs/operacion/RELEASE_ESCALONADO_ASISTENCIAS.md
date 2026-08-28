# Release escalonado de asistencias

Estado: implementado localmente; requiere publicar un tag nuevo y ejecutar CI.

Este procedimiento reemplaza la ejecución manual por SSH del release de
`asistencias.0005`. El workflow rutinario sigue siendo `deploy.yml`; este
 workflow separado se activa únicamente por un tag anotado `release/asistencias-*`.
Los pushes a `main` ejecutan CI y no despliegan.

## Etapas independientes

### Preflight

El job de preflight usa el environment protegido `production-readonly`, una clave
SSH restringida y no detiene Gunicorn.
Verifica tag anotado, `tag^{}`, SHA, padre, worktree, dump, snapshot, espacio,
servicio y migraciones. También verifica `origen` en ambas relaciones, incluida
su nulabilidad y default.

El estado esperado de producción (`0004` aplicada, `0005` pendiente, `origen`
existente NOT NULL sin default `explicita`) se identifica como Ruta A reparable.

El marcador JSON se guarda fuera del checkout, contiene SHA/tag/padre,
checksum del dump, timestamp, vencimiento breve y conteos agregados. No contiene
nombres, correos, IDs personales ni dumps.

El preflight genera un reporte prospectivo sanitizado y solo crea marcador cuando
el estado coincide exactamente con Ruta A. La reconciliación conserva las
relaciones activas y las identifica como `reconciliada`; no hay activación humana
ni desactivación automática. `apply` rechaza marcadores vencidos o con identidad,
dump, snapshot o reporte distintos.

Las conexiones SSH usan `DEPLOY_KNOWN_HOSTS` provisto por el environment
protegido; no se ejecuta `ssh-keyscan` dinámico.

### Apply

El job apply requiere el environment `production` y un marcador vigente del mismo
tag y SHA. La concurrencia
`release-asistencias-production` impide dos ejecuciones simultáneas.

Antes de detener la aplicación se vuelve a validar identidad, marcador y estado.
Luego se ejecutan exclusivamente:

```text
asistencias.0004b_reparar_precondiciones_0005
asistencias.0005_reparar_schema_0004_aplicada_precommit_v2
asistencias.0006_merge_0004b_y_0005
asistencias.0007_reconciliar_relaciones_activas
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
estado parcialmente preparado. Las relaciones activas sin actor se conservan y
se marcan `reconciliada`; las inactivas siguen `historica`.

`0005_reparar_schema_0004_aplicada_precommit_v2` es una migración de reemplazo:
no edita el archivo `0005` publicado, pero hace que el grafo operativo dependa
de `0004b` antes de ejecutar sus operaciones equivalentes.

`0006_merge_0004b_y_0005` une las dos ramas resultantes. Toda migración futura
debe depender de `0006_merge_0004b_y_0005`; `0007_reconciliar_relaciones_activas`
es la raíz actual para nuevas migraciones y no se deben crear ramas desde `0005`.

Antes de cualquier release se debe restaurar el dump productivo en una máquina
aislada y controlada, fuera de Actions, reproducir el esquema ambiguo y ejecutar
ambas migraciones. El dump, logs crudos y datos personales nunca se suben a
GitHub.

## Pruebas

CI valida el contrato del workflow, el grafo `0004b`/`0005`/`0006`, el gate
sintético de `origen` y que el preflight no detenga Gunicorn. La reproducción
real contra el dump se ejecuta fuera de CI y se documenta solo con resultados
agregados.

# Migraciones de Operación Profesor

Fecha de actualización: 2026-08-10

## Estado y decisión

**Gate actual: LISTO PARA VENTANA MANUAL, condicionado al preflight.** No existe
QA/staging separado; la persona responsable aceptó un piloto controlado con
pocos usuarios y mantenimiento. El código evita que la historia otorgue permisos
presentes y fue probado con PostgreSQL real y datos sintéticos. La medición real,
el backup y la decisión final se ejecutan en producción durante la ventana por
infraestructura. Producción no fue consultada ni modificada al preparar este
documento.

`asistencias.0004` se corrigió directamente. La decisión se apoya en evidencia
Git reproducible: después de `git fetch --prune origin`, `origin/main` permanece
en `d4a4e48` y no contiene `asistencias.0004` ni `finanzas.0012`; ambas forman
parte del release local único, todavía no publicado. No se encontró configuración
ni evidencia versionada de un QA/staging que las hubiera aplicado. Si un ambiente
compartido las recibió manualmente desde ese commit local, se debe detener el
deploy y crear una migración correctiva posterior: no se debe editar el historial
que ese ambiente ya considere aplicado.

Una base de desarrollo que hubiera aplicado la versión local anterior de `0004`
queda con un historial de migraciones incompatible con el archivo corregido. Se
debe reconstruir desde una copia/fixture de desarrollo o restaurar un backup; no
se debe marcar la migración como aplicada de nuevo ni añadir columnas a mano.

## Runbook manual de producción para el piloto

Este procedimiento reemplaza `scripts/deploy.sh` para esta versión. No hacer
push a `main` ni invocar el workflow de deploy durante la ventana. El único
artefacto desplegable es el tag anotado e inmutable
`release/operacion-profesor-20260810.1`; su SHA es el commit al que resuelve
`refs/tags/release/operacion-profesor-20260810.1^{commit}` y se entrega junto con
este runbook. El commit funcional
`c47ce8225b3221b28a00baf9a4d2909e154c3b30` es solamente el padre del release,
no el hash que se debe desplegar.

El script manual vive dentro de ese checkout y verifica que el tag apunte
exactamente a `HEAD`, que el worktree esté limpio y que su padre sea el commit
funcional anterior. No depende de copias externas ni de cambios sin versionar.

### 0. Variables de la sesión operativa

Definir rutas y nombres, nunca secretos ni una connection string:

```bash
set -euo pipefail
umask 077

export APP_DIR=/ruta/absoluta/del/checkout-productivo
export VENV_DIR=/ruta/absoluta/del/venv-productivo
export DEPLOY_ENV_FILE=/ruta/absoluta/del/environment-file-productivo
export SERVICE_UNIT=plataforma-elemental.service
export RELEASE_TAG=release/operacion-profesor-20260810.1
export BACKUP_DIR=/montaje-externo-seguro/elemental
export OPS_DIR=/ruta-protegida/actas/operacion-profesor

test -d "$APP_DIR/.git"
test -x "$VENV_DIR/bin/python"
test -f "$DEPLOY_ENV_FILE"
test -d "$BACKUP_DIR"
mkdir -p "$OPS_DIR"
cd "$APP_DIR"

set -a
# shellcheck disable=SC1090
source "$DEPLOY_ENV_FILE"
set +a
export PGPASSWORD="$POSTGRES_PASSWORD"
export PGOPTIONS="-c lock_timeout=5s -c statement_timeout=15min"
```

`BACKUP_DIR` debe estar fuera de `APP_DIR`, idealmente en almacenamiento montado
desde otro volumen/host con cifrado y retención definida. No guardar el dump en
Git, media pública ni `/tmp`.

### 1. Hash productivo y release

Registrar antes de modificar el checkout:

```bash
test -z "$(git status --porcelain)"
export PROD_PREV_COMMIT="$(git rev-parse HEAD)"
git show --no-patch --format='%H %cI %s' "$PROD_PREV_COMMIT" \
  | tee "$OPS_DIR/produccion-antes.txt"

git fetch --prune --tags origin
test "$(git cat-file -t "refs/tags/$RELEASE_TAG")" = "tag"
export RELEASE_COMMIT="$(git rev-parse "refs/tags/${RELEASE_TAG}^{commit}")"
test "$RELEASE_COMMIT" != "$PROD_PREV_COMMIT"
test "$(git rev-parse "${RELEASE_COMMIT}^")" = \
  "c47ce8225b3221b28a00baf9a4d2909e154c3b30"
git show --no-patch --format='%H %cI %s' "$RELEASE_COMMIT" \
  | tee "$OPS_DIR/release-objetivo.txt"
git for-each-ref "refs/tags/$RELEASE_TAG" \
  --format='%(refname) %(objecttype) %(objectname) %(*objectname)' \
  | tee "$OPS_DIR/release-tag.txt"

sudo systemctl show "$SERVICE_UNIT" --property=ActiveState,MainPID,FragmentPath \
  | tee "$OPS_DIR/systemd-antes.txt"
main_pid="$(sudo systemctl show "$SERVICE_UNIT" --property=MainPID --value)"
test "$main_pid" -gt 0
readlink -f "/proc/$main_pid/cwd" | tee "$OPS_DIR/proceso-cwd-antes.txt"
test "$(readlink -f "/proc/$main_pid/cwd")" = "$(readlink -f "$APP_DIR")"
```

`PROD_PREV_COMMIT`, no `origin/main`, es el hash productivo real que debe quedar
registrado antes del cambio. Un checkout sucio, un tag liviano, un padre distinto
o una discrepancia entre el SHA entregado y `RELEASE_COMMIT` obliga a abortar.

### 2. Preflight PostgreSQL de solo lectura

```bash
test "${DJANGO_ENV:-}" = "prod"
"$VENV_DIR/bin/python" --version | tee "$OPS_DIR/python-version.txt"
pg_dump --version | tee "$OPS_DIR/pg-dump-version.txt"
psql --version | tee "$OPS_DIR/psql-client-version.txt"

PGPASSWORD="$POSTGRES_PASSWORD" psql \
  --host "$POSTGRES_HOST" --port "$POSTGRES_PORT" \
  --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  --no-psqlrc --set=ON_ERROR_STOP=1 <<'SQL' | tee "$OPS_DIR/preflight-postgresql.txt"
SELECT version();
SELECT pg_size_pretty(pg_database_size(current_database())) AS database_size;
SELECT 'academia_sesionclase' AS tabla, count(*) AS filas FROM academia_sesionclase
UNION ALL SELECT 'academia_sesionclase_profesores', count(*) FROM academia_sesionclase_profesores
UNION ALL SELECT 'asistencias_asistencia', count(*) FROM asistencias_asistencia
UNION ALL SELECT 'finanzas_payment', count(*) FROM finanzas_payment
UNION ALL SELECT 'finanzas_transaction', count(*) FROM finanzas_transaction
UNION ALL SELECT 'finanzas_lotepago', count(*) FROM finanzas_lotepago;
SELECT relname,
       n_live_tup,
       pg_size_pretty(pg_total_relation_size(relid)) AS total_size
FROM pg_stat_user_tables
WHERE relname IN (
  'academia_sesionclase',
  'academia_sesionclase_profesores',
  'asistencias_asistencia',
  'finanzas_payment',
  'finanzas_transaction',
  'finanzas_lotepago'
)
ORDER BY relname;
SELECT app, name, applied
FROM django_migrations
WHERE app IN ('asistencias', 'finanzas')
ORDER BY app, applied, name;
SELECT count(*) AS conexiones_esperando_lock
FROM pg_stat_activity
WHERE datname = current_database()
  AND pid <> pg_backend_pid()
  AND wait_event_type = 'Lock';
SELECT count(*) AS transacciones_mayores_60s
FROM pg_stat_activity
WHERE datname = current_database()
  AND pid <> pg_backend_pid()
  AND xact_start IS NOT NULL
  AND clock_timestamp() - xact_start > interval '60 seconds';
SQL

base_ok="$(PGPASSWORD="$POSTGRES_PASSWORD" psql \
  --host "$POSTGRES_HOST" --port "$POSTGRES_PORT" \
  --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  --no-psqlrc --tuples-only --no-align --set=ON_ERROR_STOP=1 \
  --command="SELECT count(*) FROM django_migrations WHERE (app='asistencias' AND name='0003_claseliberada') OR (app='finanzas' AND name='0011_lotepago_payment_lote');")"
nuevas_aplicadas="$(PGPASSWORD="$POSTGRES_PASSWORD" psql \
  --host "$POSTGRES_HOST" --port "$POSTGRES_PORT" \
  --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  --no-psqlrc --tuples-only --no-align --set=ON_ERROR_STOP=1 \
  --command="SELECT count(*) FROM django_migrations WHERE (app='asistencias' AND name='0004_alter_sesionclase_estado_liberacionsesion_and_more') OR (app='finanzas' AND name='0012_payment_clave_idempotencia_payment_disciplina_and_more');")"
test "$base_ok" = "2"
test "$nuevas_aplicadas" = "0"

df -h "$APP_DIR" "$BACKUP_DIR" | tee "$OPS_DIR/espacio-filesystem.txt"
findmnt -T "$BACKUP_DIR" | tee "$OPS_DIR/montaje-backup.txt"
```

Infraestructura debe comprobar también el espacio del volumen PostgreSQL. Piso
conservador: espacio libre mayor al doble del tamaño total de las seis relaciones
reportadas y espacio externo mayor al tamaño actual de la base.

### 3. Aborto antes de migrar

Abortar sin tocar esquema si ocurre cualquiera:

- no se pudo registrar `PROD_PREV_COMMIT`, el checkout está sucio o el tag no es
  anotado/no coincide con el SHA final entregado;
- PostgreSQL servidor no es 16.x, salvo aprobación explícita de infraestructura;
- `asistencias.0003` o `finanzas.0011` no están aplicadas, o `0004` / `0012` ya
  figuran aplicadas;
- existen locks en espera o transacciones mayores a 60 segundos;
- falta espacio según el piso anterior o no existe destino externo seguro;
- no hay forma probada de detener escrituras;
- `check --deploy` falla o el plan contiene migraciones distintas de `0004` y
  `0012` sin revisión previa.

### 4. Mantenimiento y backup

Si existe página de mantenimiento en Nginx/proxy, activarla primero. El fallback
mínimo es detener Gunicorn, que evita escrituras aunque entregue indisponibilidad:

```bash
sudo systemctl stop "$SERVICE_UNIT"
! sudo systemctl is-active --quiet "$SERVICE_UNIT"

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
export BACKUP_FILE="$BACKUP_DIR/${POSTGRES_DB}_${timestamp}_${PROD_PREV_COMMIT:0:12}.dump"
PGPASSWORD="$POSTGRES_PASSWORD" pg_dump \
  --host "$POSTGRES_HOST" --port "$POSTGRES_PORT" \
  --username "$POSTGRES_USER" --format=custom \
  --no-owner --no-acl --file "$BACKUP_FILE" "$POSTGRES_DB"

test -s "$BACKUP_FILE"
pg_restore --list "$BACKUP_FILE" > "$OPS_DIR/backup-catalogo.txt"
sha256sum "$BACKUP_FILE" | tee "$OPS_DIR/backup-sha256.txt"
```

No continuar si `pg_dump`, catálogo o checksum falla.

### 5. Restauración comprobada, si infraestructura lo permite

```bash
export RESTORE_DB="elemental_restore_${timestamp}"
createdb --host "$POSTGRES_HOST" --port "$POSTGRES_PORT" \
  --username "$POSTGRES_USER" "$RESTORE_DB"
pg_restore --exit-on-error --no-owner --no-acl \
  --host "$POSTGRES_HOST" --port "$POSTGRES_PORT" \
  --username "$POSTGRES_USER" --dbname "$RESTORE_DB" "$BACKUP_FILE"

PGPASSWORD="$POSTGRES_PASSWORD" psql \
  --host "$POSTGRES_HOST" --port "$POSTGRES_PORT" \
  --username "$POSTGRES_USER" --dbname "$RESTORE_DB" \
  --no-psqlrc --set=ON_ERROR_STOP=1 \
  --command="SELECT count(*) AS migraciones FROM django_migrations;" \
  --command="SELECT count(*) AS sesiones FROM academia_sesionclase;" \
  --command="SELECT count(*) AS asistencias FROM asistencias_asistencia;" \
  --command="SELECT count(*) AS pagos FROM finanzas_payment;" \
  --command="SELECT count(*) AS transacciones FROM finanzas_transaction;" \
  | tee "$OPS_DIR/restore-verificacion.txt"

dropdb --host "$POSTGRES_HOST" --port "$POSTGRES_PORT" \
  --username "$POSTGRES_USER" "$RESTORE_DB"
```

Comparar conteos con el preflight. Si no es posible restaurar, registrar que solo
se validó el catálogo y aceptar explícitamente ese riesgo; no declarar el dump
como restauración probada.

### 6. Código, dependencias y gates previos

```bash
cd "$APP_DIR"
git checkout --detach "$RELEASE_COMMIT"
test "$(git rev-parse HEAD)" = "$RELEASE_COMMIT"
test -z "$(git status --porcelain)"

export DEPLOY_VENV_DIR="$VENV_DIR"
export RELEASE_OPS_DIR="$OPS_DIR"
export DEPLOY_SERVICE="$SERVICE_UNIT"

bash scripts/release_operacion_profesor.sh verify-release
bash scripts/release_operacion_profesor.sh install
bash scripts/release_operacion_profesor.sh plan-before
```

Esta entrega no cambia `requirements.txt`. Si `git diff "$PROD_PREV_COMMIT"
"$RELEASE_COMMIT" -- requirements.txt` muestra cambios, abortar y preparar un
virtualenv versionado antes de continuar.

`plan-before` ejecuta `showmigrations --plan`, falla si hay pendientes distintos
de `asistencias.0004` y `finanzas.0012`, y guarda la evidencia. Instalar
dependencias no ejecuta migraciones.

### 7. `asistencias.0004`, medición y reporte real

Aplicar cada migración por separado, con espera de lock acotada:

```bash
bash scripts/release_operacion_profesor.sh migrate-asistencias
bash scripts/release_operacion_profesor.sh report
```

El script vuelve a ejecutar `showmigrations --plan` antes y después de `0004`.
Después de esta etapa debe quedar pendiente únicamente `finanzas.0012`; de lo
contrario aborta y mantiene el servicio detenido. Un timeout, lock no obtenido,
error de reporte o migración adicional pendiente tiene el mismo efecto.

### 8. Activación administrativa durante mantenimiento

Revisar el último `relaciones-*-protegido.json` contra programación/contratos actuales. Una
sesión futura identifica un profesor a revisar; una asistencia reciente no basta
para declarar vigente a un alumno.

Previsualizar y luego confirmar por IDs revisados:

```bash
"$VENV_DIR/bin/python" manage.py activar_relaciones_operativas \
  --tipo profesor --ids <ID_1> <ID_2> \
  --actor-username <USUARIO_ADMIN>
"$VENV_DIR/bin/python" manage.py activar_relaciones_operativas \
  --tipo profesor --ids <ID_1> <ID_2> \
  --actor-username <USUARIO_ADMIN> \
  --confirmar ACTIVAR_RELACIONES_REVISADAS

"$VENV_DIR/bin/python" manage.py activar_relaciones_operativas \
  --tipo alumno --ids <ID_1> <ID_2> \
  --actor-username <USUARIO_ADMIN>
"$VENV_DIR/bin/python" manage.py activar_relaciones_operativas \
  --tipo alumno --ids <ID_1> <ID_2> \
  --actor-username <USUARIO_ADMIN> \
  --confirmar ACTIVAR_RELACIONES_REVISADAS
```

Cada lote es atómico, valida al actor en todas las organizaciones y audita cada
relación. También existe la acción equivalente en Django Admin. Repetir el
reporte y no abrir mientras quede una asignación futura confirmada pendiente de
activación o decisión explícita.

Guardar una segunda versión del reporte después de las activaciones:

```bash
export RELEASE_ACTIVATION_ACTOR=<USUARIO_ADMIN>
export RELEASE_CONFIRM_ACTIVACIONES=RELACIONES_VIGENTES_REVISADAS
bash scripts/release_operacion_profesor.sh confirm-activations
unset RELEASE_CONFIRM_ACTIVACIONES
```

`confirm-activations` vuelve a generar el reporte y deja un gate asociado al SHA
del release y al actor. `migrate-finanzas` rechaza avanzar si faltan el reporte o
esta confirmación. La auditoría de datos permanece en los servicios de activación;
el archivo de gate es evidencia operativa, no reemplaza esa auditoría.

### 9. `finanzas.0012`, verificación post-despliegue y arranque

Solo después de firmar la revisión administrativa:

```bash
export RELEASE_CONFIRM_FINANZAS=APLICAR_FINANZAS_0012
bash scripts/release_operacion_profesor.sh migrate-finanzas
unset RELEASE_CONFIRM_FINANZAS
bash scripts/release_operacion_profesor.sh finalize
```

`migrate-finanzas` guarda un `showmigrations --plan` inmediatamente antes y
después, exige que `0012` sea el único pendiente y no declara éxito si queda
alguna migración. `finalize` tampoco ejecuta `migrate`; solo comprueba, recopila
estáticos y ejecuta el gate de Django.

```bash
PGPASSWORD="$POSTGRES_PASSWORD" psql \
  --host "$POSTGRES_HOST" --port "$POSTGRES_PORT" \
  --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  --no-psqlrc --set=ON_ERROR_STOP=1 <<'SQL' | tee "$OPS_DIR/postdeploy-postgresql.txt"
SELECT app, name, applied
FROM django_migrations
WHERE (app='asistencias' AND name LIKE '0004%')
   OR (app='finanzas' AND name LIKE '0012%')
ORDER BY app;
SELECT count(*) AS indices_invalidos
FROM pg_index
WHERE NOT indisvalid;
SELECT count(*) AS pagos_nuevos_sin_transaccion
FROM finanzas_payment
WHERE registrado_por_id IS NOT NULL AND transaccion_id IS NULL;
SELECT count(*) AS pagos_con_transaccion_duplicada
FROM (
  SELECT transaccion_id
  FROM finanzas_payment
  WHERE transaccion_id IS NOT NULL
  GROUP BY transaccion_id
  HAVING count(*) > 1
) duplicados;
SQL

sudo systemctl start "$SERVICE_UNIT"
sudo systemctl is-active --quiet "$SERVICE_UNIT"
curl -fsS -H 'Host: apps.espacioelementos.cl' \
  http://127.0.0.1:8001/api/health/ >/dev/null
sudo journalctl -u "$SERVICE_UNIT" --since '-10 minutes' --no-pager \
  | tail -n 200 > "$OPS_DIR/systemd-postdeploy.txt"
```

Si el proxy mantiene una página de mantenimiento, no retirarla aún. Si el único
mecanismo fue detener Gunicorn, el `start` reabre el servicio: ejecutar el smoke
inmediatamente dentro de la ventana.

### 10. Smoke con cuenta solo PROFESOR

La cuenta debe tener `is_staff=False`, un único rol activo `PROFESOR`, una
organización y una asignación revisada. Probar con Google real:

1. iniciar sesión y confirmar Inicio, sesiones, alumnos y pagos propios;
2. abrir una sesión propia futura e histórica;
3. comprobar que asistentes y finanzas solo muestran alumnos asignados;
4. intentar Django Admin, branding, sesión ajena y otra organización por URL
   directa: acceso denegado/404 sin datos;
5. registrar una operación controlada acordada y comprobar persistencia y
   auditoría; si es un pago, verificar transacción e imputación una-a-una;
6. comprobar navegación en ancho móvil.

Retirar mantenimiento solo si el smoke y los queries son correctos.

### 11. Rollback de aplicación

**`d4a4e482c67a115562918bcc2f3f71e6cdb2b0c9` (`d4a4e48`) no se declara
compatible con una base que ya recibió estas
migraciones y operaciones.** Aunque PostgreSQL tolere físicamente tablas y
columnas extra nullable, ese código desconoce el estado de sesión `abierta`, las
relaciones operativas auditadas y los vínculos financieros nuevos. Arrancarlo
después de `0004`, activaciones o escrituras de esta versión puede ocultar o
interpretar incorrectamente datos.

Antes de ejecutar `asistencias.0004`, si solo falló checkout/dependencias, se
puede volver de forma manual al hash real registrado:

```bash
sudo systemctl stop "$SERVICE_UNIT"
cd "$APP_DIR"
git checkout --detach "$PROD_PREV_COMMIT"
test "$(git rev-parse HEAD)" = "$PROD_PREV_COMMIT"
source "$VENV_DIR/bin/activate"
python -m pip install --requirement requirements.txt
python manage.py collectstatic --noinput
python manage.py check --deploy
sudo systemctl start "$SERVICE_UNIT"
```

Desde que `0004` se aplica, no iniciar `d4a4e48`: mantener mantenimiento y
resolver con una corrección forward compatible. No ejecutar `migrate` hacia una
migración anterior, no usar `scripts/deploy.sh` como rollback y no restaurar
PostgreSQL automáticamente.

La restauración del dump es excepcional: únicamente con aprobación de la persona
dueña de los datos, restaurar en una base nueva aislada, verificar conteos e
invariantes y cambiar el puntero de la aplicación de forma controlada. Restaurar
el dump descarta toda escritura posterior al instante del `pg_dump`; si el sitio
se reabrió, esa pérdida potencial debe medirse y aceptarse expresamente o se debe
preferir recuperación selectiva/corrección forward.

### 12. Checklist breve

Antes:

- [ ] Ventana, responsables y comando de mantenimiento confirmados.
- [ ] Tag anotado, `RELEASE_COMMIT` exacto y `PROD_PREV_COMMIT` real registrados.
- [ ] Preflight sin locks/transacciones largas y con espacio suficiente.
- [ ] Destino externo de backup montado; criterios de aborto aceptados.
- [ ] Cuenta Google solo PROFESOR y relaciones vigentes identificadas.

Durante:

- [ ] Mantenimiento activo y escrituras detenidas.
- [ ] `pg_dump`, catálogo, checksum y, si es posible, restore aprobados.
- [ ] Código exacto, dependencias y cada `showmigrations --plan` revisados.
- [ ] `0004`, reporte real, activaciones revisadas y `0012` completados.
- [ ] Tiempos, errores y decisiones guardados en `OPS_DIR` protegido.

Después:

- [ ] Gates Django, migraciones, índices e invariantes financieras correctos.
- [ ] Servicio activo, logs limpios y healthcheck interno correcto.
- [ ] Smoke solo PROFESOR e aislamiento por URL directa aprobados.
- [ ] Mantenimiento retirado, monitoreo reforzado y backup bajo retención.
- [ ] Si se abortó tras `0004`: mantenimiento activo y corrección forward; no se
      arrancó `d4a4e48` ni se revirtieron datos automáticamente.

## Semántica de relaciones históricas

`AsignacionProfesorDisciplina` y `AlumnoDisciplina` guardan:

- `origen=explicita|historica`;
- `activa`;
- `revisada_por` y `revisada_en`.

El backfill crea toda relación inferida con `origen=historica`, `activa=False` y
sin revisión. El queryset canónico `objects.operativas()` acepta solamente una
relación activa que sea explícita o una histórica con ambos datos de revisión.
Cambiar únicamente `activa=True` en SQL, shell o un formulario incompleto no
concede alcance.

La regla se aplica a listado y detalle de sesiones, creación/edición/liberación,
asistentes, alta y consulta de alumnos, pago individual, pago masivo y consulta
de pagos/transacciones del profesor. `SesionClase.profesores` y el rol activo
siguen siendo requisitos adicionales, no reemplazos. La señal de `Asistencia`
solo crea trazabilidad histórica inactiva y nunca reactiva una matrícula.

### Revisión y activación administrativa

1. Ejecutar el reporte después de aplicar `asistencias.0004`:

   ```bash
   python manage.py reportar_relaciones_historicas \
     --fecha-corte 2026-08-10 \
     --dias-vigencia-alumno 90 \
     --formato=json --fallar-si-inseguro
   ```

2. Conservar el JSON sanitizado en el registro del despliegue. Sin la opción de
   detalle solo contiene conteos; no incluye nombres, correos, RUT ni IDs.
3. Generar el listado de trabajo con `--incluir-detalle-operativo` únicamente en
   almacenamiento protegido fuera del repositorio. Incluye nombres e IDs y se
   elimina con la copia QA al aprobar el informe.
4. Contrastar cada profesor con sesiones desde la fecha de corte y una fuente
   administrativa vigente. Una sesión futura pone el caso en la cola de
   activación, pero no lo activa. Una sesión antigua no se usa para este fin.
5. En Django Admin, filtrar asignaciones por organización, origen y estado;
   seleccionar los IDs aprobados y ejecutar “Activar relaciones seleccionadas
   tras revisión”. La acción es atómica, verifica cada organización y audita
   actor, fecha y relación.
6. Para matrículas, la asistencia dentro de la ventana solo identifica un caso
   para revisión. Activar en lote exclusivamente las matrículas cuya vigencia se
   haya confirmado administrativamente.
7. Volver a ejecutar el reporte con `--fallar-si-inseguro`. El valor
   `historicas_activas_sin_revision` debe ser cero en ambos dominios.

Una desactivación posterior conserva la relación y su origen, requiere el mismo
permiso administrativo y también queda auditada, por lo que el procedimiento es
reversible sin borrar trazabilidad.

`sin_inferencia` cuenta pares históricos que todavía no tienen relación. Los
campos `ambiguas_*` cuentan, sin identificar personas, relaciones sin rol activo
compatible o con multiplicidad que requiere revisión humana.

## SQL y locks

El SQL generado se conserva en:

- [asistencias.0004](../evidencia/migraciones-operacion-profesor-20260810/sql-asistencias-0004.sql);
- [finanzas.0012](../evidencia/migraciones-operacion-profesor-20260810/sql-finanzas-0012.sql).

`asistencias.0004` crea tres tablas, sus claves foráneas, índices y dos índices
únicos, y luego ejecuta el backfill Python dentro de la transacción de la
migración. Lee pares únicos con iterator e inserta lotes de hasta 2.000 para no
cargar todo el historial en memoria de aplicación. No actualiza sesiones,
asistencias, personas ni pagos existentes.

`finanzas.0012` es atómica. Agrega siete columnas anulables, dos unicidades y
cuatro índices explícitos; las claves foráneas se agregan y validan en los
`ALTER TABLE`. PostgreSQL toma locks fuertes durante los `ALTER TABLE` y los
`CREATE INDEX` no concurrentes bloquean escrituras incompatibles. Al estar todo
en una transacción, los locks pueden conservarse hasta `COMMIT`. Los campos
nullable no exigen un backfill y la migración no contiene `RunPython` ni
`UPDATE`, pero eso no elimina el riesgo de espera por locks o construcción de
índices.

No se convirtió preventivamente la migración a índices concurrentes: el ensayo
sintético fue aceptable, pero no es representativo de producción. Si la copia
real arroja una espera incompatible con la ventana acordada, el rediseño será en
fases y las operaciones `CREATE INDEX CONCURRENTLY` vivirán en una migración con
`atomic = False`:

1. columnas nullable;
2. backfill o validación, solo si una regla futura lo exige;
3. índices concurrentes;
4. constraints y finalización.

## Herramienta de ensayo

`scripts/migraciones/ensayar_finanzas_0012.py` exige PostgreSQL, la confirmación
literal `COPIA_NO_PRODUCTIVA`, espacio libre informado por operaciones, estado
`asistencias.0004` aplicado y `finanzas.0011` aplicado/`0012` pendiente. Exige
`DJANGO_ENV` explícitamente no productivo, rechaza nombres de base con `prod` y
aborta por defecto después de 900 segundos. Registra versión, migraciones, filas,
tamaños, duración total, cotas por sentencia con muestreo de 50 ms, locks y una
escritura representativa que siempre hace rollback. Omite nombre, host, usuario
y credenciales de la base.

Ejemplo para QA/staging después de cargar variables no versionadas:

```bash
python scripts/migraciones/ensayar_finanzas_0012.py \
  --confirmar-copia COPIA_NO_PRODUCTIVA \
  --espacio-disponible-bytes 1234567890 \
  --salida /ruta/segura/ensayo-finanzas-0012.json
```

El script modifica deliberadamente esa copia al aplicar `0012`. Debe ejecutarse
sobre una base desechable/restaurable, nunca sobre producción.

## Ensayo sintético ejecutado

El ensayo preliminar usó PostgreSQL 18.4 local, 300.000 pagos sintéticos, 100.000
transacciones, cero lotes y 15.483.297.792 bytes libres declarados. No usó una
copia ni distribuciones de datos productivos.

| Medición | Resultado |
| --- | ---: |
| `finanzas_payment` antes | 300.000 filas; 103.784.448 bytes totales |
| `finanzas_transaction` antes | 100.000 filas; 27.820.032 bytes totales |
| Duración total `0012` | 2,335 s |
| Escrituras representativas | 27 |
| Mayor latencia de escritura | 967,264 ms |
| Errores de escritura | 0 |
| Pagos históricos con campo nuevo poblado | 0 |
| Pagos con transacción inventada | 0 |
| Transacciones históricas modificadas | 0 |

Con resolución de 50 ms, las operaciones observadas quedaron entre estas cotas:

| Operación | Mínimo observado | Máximo estimado |
| --- | ---: | ---: |
| `ADD clave_idempotencia ... UNIQUE` | 158,8 ms | 258,8 ms |
| `ADD disciplina_id + FK` | 56,1 ms | 156,1 ms |
| `ADD registrado_por_id + FK` | 0 ms | 100,0 ms |
| `ADD respaldo` de pago | 56,1 ms | 156,1 ms |
| `ADD transaccion_id ... UNIQUE + FK` | 165,7 ms | 265,7 ms |
| índice `clave_idempotencia ... varchar_pattern_ops` | 51,7 ms | 151,7 ms |
| índice `disciplina_id` | 51,5 ms | 151,5 ms |
| índice `registrado_por_id` | 52,2 ms | 152,2 ms |

El `ADD respaldo` del lote y el índice `transaction.creado_por_id` no aparecen
separados: duraron menos que la resolución o quedaron entre dos muestras. La evidencia
completa está en
[ensayo-sintetico-finanzas-0012.json](../evidencia/migraciones-operacion-profesor-20260810/ensayo-sintetico-finanzas-0012.json).

## Riesgo aceptado por ausencia de QA/staging

No existe copia representativa separada. La persona responsable aceptó que la
medición real ocurra durante una ventana productiva con pocos usuarios,
mantenimiento, backup previo y `lock_timeout` acotado. La evidencia sintética
reduce incertidumbre de código, pero no predice el tiempo real.

El runbook manual anterior reemplaza el gate QA previo. Infraestructura conserva
la potestad de abortar en cualquier paso antes de abrir tráfico. El antecedente
del gate anterior permanece en
[ENSAYO_QA_Y_TRANSICION.md](../evidencia/migraciones-operacion-profesor-20260810/ENSAYO_QA_Y_TRANSICION.md).

## Prueba local de backup/restauración

Sobre la base sintética ya migrada:

- `pg_dump --format=custom`: 0,86 s; archivo de 2.785.030 bytes;
- `pg_restore --list`: catálogo legible;
- `pg_restore --exit-on-error` en una base vacía: 4,39 s;
- origen y restauración: 300.000 pagos, suma 3.000.000.000 CLP, 100.000
  transacciones, suma 1.000.000.000 CLP, 26 migraciones y `finanzas.0012`
  aplicada en ambos.

El dump y el clúster sintético usados en esa medición ya no están disponibles en
la ruta temporal que se registró originalmente. Nunca fueron respaldo operativo
ni artefactos durables. La receta y la evidencia sanitizada sí quedan en el
repositorio. Esta prueba demuestra el runbook local, no RPO/RTO productivos.

Toda copia representativa futura debe eliminarse después de que el informe sea
aprobado: detener conexiones, destruir base, dump y clúster conforme a QA y
conservar solo resultados sanitizados y el acta de eliminación. Nunca se
versionan datos productivos restaurados.

## Criterio para completar la ventana

La apertura queda aprobada solo si el preflight, backup, migraciones, reporte,
activaciones, invariantes, servicio y smoke test del runbook pasan. Un paso
omitido debe quedar aceptado explícitamente como riesgo en el acta. Antes de la
ejecución, el release está listo pero condicionado; no se declara desplegado ni
apto por la sola existencia de este documento.

Las 12 pruebas omitidas están enumeradas con motivo y riesgo en
[ENSAYO_QA_Y_TRANSICION.md](../evidencia/migraciones-operacion-profesor-20260810/ENSAYO_QA_Y_TRANSICION.md).
Pertenecen exclusivamente a vistas HTML de `monitor`, una app archivada, y no
cubren ninguna garantía crítica de estas migraciones.

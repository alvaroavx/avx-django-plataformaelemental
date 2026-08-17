# Evidencia — gate CI antes de deploy

Fecha: 2026-08-11

## Alcance

Revisión local, sin push, sin SSH productivo y sin despliegue. El patch deja el
flujo `push main -> test PostgreSQL -> deploy -> smoke` preparado, pero no puede
existir una ejecución remota de código que todavía no fue publicado.

## Evidencia remota anterior al patch

- Run `31443264950`, commit
  `4e56dea282cc374059ec0e1566e2843376ff015f`: job `test` exitoso y job `deploy`
  omitido por la condición antigua que solo aceptaba `workflow_dispatch`.
  https://github.com/alvaroavx/avx-django-plataformaelemental/actions/runs/31443264950
- Run `30238388635`: `Run test suite` falló y el job `deploy` quedó omitido.
  Demuestra el comportamiento histórico de la dependencia, no sustituye la
  ejecución pendiente del workflow modificado.
  https://github.com/alvaroavx/avx-django-plataformaelemental/actions/runs/30238388635

## Gate preparado

El job `deploy` declara `needs: test`, exige `success()` y no contiene
`always()`. Para `push` a `main`, solo puede alcanzar validación de secrets, SSH,
checkout remoto o `scripts/deploy.sh` después del éxito completo de `test`.
Además referencia el environment `production`, pero la API de GitHub respondió
`404` al consultarlo con las credenciales disponibles: no se considera confirmada
una aprobación humana hasta que infraestructura compruebe que existe y tiene
revisores obligatorios.

Comandos exactos del job `test`:

```bash
python scripts/validar_gate_ci.py
python manage.py check
ruff check .
python manage.py test asistencias finanzas personas
python manage.py test asistencias.test_operacion_profesor.ProfesorMultiOrganizacionTests
```

PostgreSQL efímero del runner:

```text
image=postgres:16
POSTGRES_DB=plataforma_elemental_ci
POSTGRES_USER=elemental_ci
POSTGRES_PASSWORD=elemental_ci_only
POSTGRES_HOST=127.0.0.1
POSTGRES_PORT=5432
```

No se carga `.env.prod`, `DEPLOY_ENV_FILE` ni un secret de base de datos en el
job. Django crea `test_plataforma_elemental_ci`, la elimina al terminar y GitHub
Actions destruye el contenedor con el runner.

## Smoke post-deploy

`scripts/smoke_produccion.sh` se ejecuta en un paso posterior y separado. Exige:

- `/` -> `302` cuyo destino contiene `/accounts/login/`;
- `/accounts/login/` -> `200`;
- `/profesor/sesiones/?organizacion=<autorizada>` -> `200`;
- la misma ruta con la organización ajena -> `404`.

La identidad y los IDs viven únicamente en el archivo de entorno del servidor.
El comando usa cookies de sesión firmadas temporales: no emite señal de login,
no actualiza `last_login` y no crea una fila persistente de sesión. Si el smoke
falla, el job queda rojo y conserva el log; no intenta downgrade ni restauración
automática de PostgreSQL.

## Validaciones locales

Resultados antes de cualquier push:

```text
Gate CI válido: push main -> test PostgreSQL completo -> deploy condicionado -> smoke post-deploy
YAML válido
bash -n: OK
ruff: All checks passed
python manage.py check: System check identified no issues (0 silenced)
python manage.py makemigrations --check --dry-run: No changes detected
git diff --check: OK
```

La invocación local de `python manage.py test asistencias finanzas personas`
descubrió 384 tests, pero no pudo iniciarlos porque el PostgreSQL de desarrollo
configurado en `127.0.0.1:5432` no estaba disponible. No se creó otro clúster ni
otra base local: se respetó la decisión de usar solamente la base actual. Esto no
se registra como una ejecución verde del patch.

La ejecución GitHub Actions del patch sigue **pendiente** por la prohibición de
hacer push. Debe considerarse un gate de publicación: no autorizar deploy hasta
que el commit sea publicado y su nuevo job `test` termine verde.

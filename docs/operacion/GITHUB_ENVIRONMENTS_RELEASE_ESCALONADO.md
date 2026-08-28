# Configuración de environments para release escalonado

Estado al 2026-08-23: GitHub devolvió `{"total_count":0,"environments":[]}`.
No existen todavía `production-readonly` ni `production`. Este documento
prepara la configuración; no crea environments ni rota secrets.

## production-readonly

Crear un environment con revisores obligatorios y definir allí, no a nivel de
repositorio, los secrets `DEPLOY_HOST`, `DEPLOY_PORT`, `DEPLOY_USER`,
`DEPLOY_PATH`, `DEPLOY_ENV_FILE`, `DEPLOY_SERVICE`, `RELEASE_BACKUP_FILE`,
`RELEASE_OPS_DIR`, `DEPLOY_SSH_KEY_B64` y `DEPLOY_KNOWN_HOSTS`.

La clave debe usar una entrada `authorized_keys` con `restrict` y un
`command=` que permita únicamente el preflight con argumentos validados y la escritura del
marcador/evidencia en `RELEASE_OPS_DIR`. Debe rechazar `sudo`,
`systemctl stop/start`, checkout, pip, migraciones, collectstatic y conexiones
de escritura a PostgreSQL. El workflow valida el tag y envía únicamente la
operación y sus argumentos; no transmite código por stdin ni ejecuta `git fetch`.

Pruebas del wrapper que deben ser rechazadas:

```bash
ssh -i clave-readonly usuario@host 'systemctl stop plataforma-elemental.service'
ssh -i clave-readonly usuario@host 'git checkout --detach SHA'
```

## production

Crear un environment distinto, también con revisores obligatorios y secrets
propios. Usa los mismos nombres operativos, pero `DEPLOY_SSH_KEY_B64` y
`DEPLOY_KNOWN_HOSTS` deben corresponder al canal de aplicación separado.

El wrapper de aplicación permite solo el procedimiento versionado de
`release_asistencias_escalonado.sh`: detener/iniciar el servicio, instalar
requirements, migraciones explícitas, collectstatic y smoke. No permite shell
interactivo, `migrate` global, SQL manual, downgrade ni restauración automática.

El usuario SSH no debe ser root. Si necesita sudo, debe existir un `sudoers`
con comandos absolutos y argumentos restringidos al wrapper aprobado.

## Secrets y comprobación

Después de validar ambos environments, quitar del nivel repositorio cualquier
secret SSH duplicado en un environment. Consultas sin mostrar valores:

```bash
gh secret list --repo alvaroavx/avx-django-plataformaelemental --app actions
gh api repos/alvaroavx/avx-django-plataformaelemental/environments
```

El workflow debe ejecutarse seleccionando un tag y comprobar:

```bash
test "$GITHUB_REF_TYPE" = tag
git cat-file -t "refs/tags/$RELEASE_TAG"
git rev-parse "refs/tags/$RELEASE_TAG^{}"  # igual a RELEASE_SHA
```

No crear environments ni mover secrets como parte del commit de código; es una
tarea separada de infraestructura con revisión y evidencia.

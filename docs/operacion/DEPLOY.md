# Deploy

Fecha de actualizacion: 2026-04-20

## Objetivo
Este documento describe el CI/CD minimo del proyecto:
- GitHub Actions ejecuta tests
- si el push entra a `main`, despliega por SSH al servidor
- el servidor actualiza codigo, instala dependencias, migra, recopila estaticos y reinicia `systemd`

## Estrategia elegida
- No se usa Docker, Compose ni self-hosted runner.
- Se usa `systemd + gunicorn + deploy por SSH`.
- Es la opcion mas simple y mantenible para este repo porque:
  - el proyecto es Django puro
  - ya existe servidor con acceso SSH
  - no hay evidencia de otro orquestador en el codigo
  - evita agregar infraestructura innecesaria

## Archivos creados
- `.github/workflows/deploy.yml`
- `scripts/deploy.sh`
- `deploy/systemd/plataformaelemental.service.example`

## Secrets de GitHub Actions

### Obligatorios
- `DEPLOY_HOST`
  - host o IP del servidor
- `DEPLOY_USER`
  - usuario SSH de despliegue
- `DEPLOY_SSH_KEY`
  - clave privada SSH exclusiva para GitHub Actions
  - debe ser una clave nueva de deploy, sin passphrase
- `DEPLOY_PATH`
  - ruta absoluta del repo en el servidor, por ejemplo `/srv/plataformaelemental`
- `DEPLOY_SERVICE`
  - nombre del servicio systemd, por ejemplo `plataformaelemental`

### Opcionales
- `DEPLOY_PORT`
  - puerto SSH, normalmente `22`
  - si no existe, el workflow usa `22`
- `DEPLOY_ENV_FILE`
  - ruta absoluta del archivo de entorno del servidor, por ejemplo `/srv/plataformaelemental/.env.prod`
  - si no existe, `scripts/deploy.sh` no carga archivo externo
- `DEPLOY_VENV_DIR`
  - ruta absoluta del virtualenv si no quieres usar `.venv` dentro del repo
  - si no existe, usa `.venv` en el repo
- `DEPLOY_PYTHON_BIN`
  - binario python a usar para crear el virtualenv, por ejemplo `python3.13`
  - si no existe, usa `python3`

## Llave SSH de deploy

No intentes adaptar tu llave actual con passphrase al pipeline.
Lo sensato es preparar una llave nueva de deploy, separada, sin passphrase, con su publica en `authorized_keys` del servidor.

### Crear la llave nueva

En tu maquina local:

```bash
ssh-keygen -t ed25519 -C "github-actions-deploy@plataforma-elemental" -f ~/.ssh/plataforma_elemental_deploy -N ""
```

Eso genera:
- privada: `~/.ssh/plataforma_elemental_deploy`
- publica: `~/.ssh/plataforma_elemental_deploy.pub`

### Instalar la publica en el servidor

Con otro acceso ya funcional al servidor:

```bash
mkdir -p ~/.ssh
chmod 700 ~/.ssh
cat ~/.ssh/plataforma_elemental_deploy.pub >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
```

Si la vas a instalar para otro usuario:

```bash
sudo -u USUARIO mkdir -p /home/USUARIO/.ssh
sudo -u USUARIO chmod 700 /home/USUARIO/.ssh
sudo -u USUARIO bash -c 'cat >> /home/USUARIO/.ssh/authorized_keys' < ~/.ssh/plataforma_elemental_deploy.pub
sudo chmod 600 /home/USUARIO/.ssh/authorized_keys
sudo chown -R USUARIO:USUARIO /home/USUARIO/.ssh
```

### Cargar la privada en GitHub

En GitHub:
1. Ir a `Settings`
2. `Secrets and variables`
3. `Actions`
4. Crear el secret `DEPLOY_SSH_KEY`
5. Pegar el contenido completo de la privada:

```text
-----BEGIN OPENSSH PRIVATE KEY-----
...
-----END OPENSSH PRIVATE KEY-----
```

### Probar antes del workflow

```bash
ssh -i ~/.ssh/plataforma_elemental_deploy -o IdentitiesOnly=yes -p 22 USUARIO@HOST
```

Si eso no funciona desde tu maquina, el workflow tampoco va a funcionar.

## Variables de servidor esperadas
En el archivo de entorno de produccion conviene definir al menos:
- `DJANGO_ENV=prod`
- `DJANGO_SECRET_KEY`
- `DJANGO_ALLOWED_HOSTS`
- `DJANGO_CSRF_TRUSTED_ORIGINS`

## Instalacion inicial en el servidor
1. Instalar dependencias base del sistema:
   - `git`
   - `python3`
   - `python3-venv`
2. Clonar el repo en la ruta final:
   - `git clone <repo> /srv/plataformaelemental`
3. Crear el archivo de entorno de produccion.
4. Asegurar que el usuario de despliegue pueda reiniciar el servicio:
   - idealmente con `sudo` sin password para `systemctl restart` y `systemctl is-active`
   - ese mismo usuario debe ser el que figura en `DEPLOY_USER`
5. Ajustar el unit file desde `deploy/systemd/plataformaelemental.service.example`:
   - reemplazar `__SERVICE_USER__`
   - reemplazar `__APP_DIR__`
   - reemplazar `__ENV_FILE__`
   - reemplazar `__VENV_DIR__`
6. Instalar el servicio:
   - copiarlo a `/etc/systemd/system/plataformaelemental.service`
   - `sudo systemctl daemon-reload`
   - `sudo systemctl enable plataformaelemental`
7. Ejecutar una primera vez:
   - `cd /srv/plataformaelemental`
   - `bash scripts/deploy.sh`

## Flujo del workflow
1. `actions/checkout`
2. instalar dependencias Python
3. levantar un servicio PostgreSQL 16 para el job `test`
4. correr `python manage.py test asistencias.tests personas.tests finanzas.tests api.tests` contra PostgreSQL
5. validar secrets obligatorios
6. escribir la llave privada en `~/.ssh/deploy_key`
7. validar que la llave sea una privada SSH correcta y sin passphrase interactiva
8. poblar `known_hosts` con `ssh-keyscan`
9. abrir SSH al servidor usando `-i ~/.ssh/deploy_key`
10. `git fetch`
11. `git reset --hard origin/main`
12. ejecutar `bash scripts/deploy.sh`

## Base De Datos En CI
- El entorno `dev` usa PostgreSQL, por lo tanto GitHub Actions debe levantar PostgreSQL para ejecutar tests.
- El job `test` usa un service container `postgres:16` con:
  - `POSTGRES_DB=plataforma_elemental_dev`
  - `POSTGRES_USER=plataforma_user`
  - `POSTGRES_PASSWORD=plataforma_password`
  - `POSTGRES_HOST=127.0.0.1`
  - `POSTGRES_PORT=5432`
- No se debe volver a SQLite solo para CI; los tests deben correr sobre el mismo motor elegido para desarrollo y produccion.

## SSH En CI
- El workflow usa exclusivamente `DEPLOY_SSH_KEY` como llave privada directa.
- No se usa `DEPLOY_SSH_KEY_B64`.
- La llave se escribe con `printf "%s"` para no agregar saltos de linea extra.
- La llave pasa por `tr -d '\r'` para remover retornos de carro pegados accidentalmente desde otros sistemas.
- El comando `ssh` usa `-i ~/.ssh/deploy_key` y `IdentitiesOnly=yes` para no depender de nombres por defecto de OpenSSH.
- No debe existir un paso de debug que imprima primera o ultima linea de la llave privada.

## Que hace `scripts/deploy.sh`
- carga variables desde `DEPLOY_ENV_FILE` si existe
- fuerza `DJANGO_ENV=prod` por defecto
- crea virtualenv si no existe
- instala dependencias
- ejecuta `python manage.py migrate --noinput`
- ejecuta `python manage.py clearsessions`
- ejecuta `python manage.py collectstatic --noinput`
- ejecuta `python manage.py check --deploy`
- reinicia el servicio systemd

## Rollback simple
En el servidor:

```bash
cd /srv/plataformaelemental
git fetch --prune origin
git reset --hard <commit_sha>
bash scripts/deploy.sh
```

Si quieres volver al ultimo `main`:

```bash
cd /srv/plataformaelemental
git reset --hard origin/main
bash scripts/deploy.sh
```

## Riesgos detectados en el proyecto
- `package.json` y `node_modules/` existen en el repo, pero no forman parte del stack real de deploy.
- `gunicorn` no estaba declarado como dependencia de produccion; se agrego a `requirements.txt`.
- No hay hasta ahora configuracion de `systemd`, `nginx` o proceso WSGI versionada; por eso se agrega el unit file ejemplo.
- El deploy usa `git reset --hard origin/main`; eso es correcto para un clon de despliegue, pero cualquier cambio manual hecho en el servidor se perdera.
- `python manage.py check --deploy` se ejecuta automaticamente y puede mostrar warnings de seguridad; bloquea el deploy solo si Django retorna error.
- Si `DEPLOY_SSH_KEY` contiene una clave con passphrase o una clave mal pegada, el workflow fallara antes de intentar el SSH remoto.

## Recomendaciones inmediatas
- usar un usuario de despliegue dedicado
- servir Django detras de Nginx o un proxy equivalente
- no hacer cambios manuales dentro del clon de produccion
- mantener `DEPLOY_ENV_FILE` apuntando a un archivo real con `DJANGO_ENV=prod`, `POSTGRES_*`, `DJANGO_SECRET_KEY`, hosts permitidos y variables de seguridad de sesion.

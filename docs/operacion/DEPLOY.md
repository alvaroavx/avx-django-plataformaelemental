# Deploy

Fecha de actualizacion: 2026-04-01

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

## Secrets requeridos en GitHub
- `DEPLOY_HOST`
  - host o IP del servidor
- `DEPLOY_PORT`
  - puerto SSH, normalmente `22`
- `DEPLOY_USER`
  - usuario SSH de despliegue
- `DEPLOY_SSH_KEY`
  - clave privada SSH usada por GitHub Actions
- `DEPLOY_PATH`
  - ruta absoluta del repo en el servidor, por ejemplo `/srv/plataformaelemental`
- `DEPLOY_SERVICE`
  - nombre del servicio systemd, por ejemplo `plataformaelemental`

Secrets opcionales:
- `DEPLOY_ENV_FILE`
  - ruta absoluta del archivo de entorno del servidor, por ejemplo `/srv/plataformaelemental/.env.prod`
- `DEPLOY_VENV_DIR`
  - ruta absoluta del virtualenv si no quieres usar `.venv` dentro del repo
- `DEPLOY_PYTHON_BIN`
  - binario python a usar para crear el virtualenv, por ejemplo `python3.13`

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
4. Ajustar el unit file desde `deploy/systemd/plataformaelemental.service.example`:
   - reemplazar `__SERVICE_USER__`
   - reemplazar `__APP_DIR__`
   - reemplazar `__ENV_FILE__`
   - reemplazar `__VENV_DIR__`
5. Instalar el servicio:
   - copiarlo a `/etc/systemd/system/plataformaelemental.service`
   - `sudo systemctl daemon-reload`
   - `sudo systemctl enable plataformaelemental`
6. Ejecutar una primera vez:
   - `cd /srv/plataformaelemental`
   - `bash scripts/deploy.sh`

## Flujo del workflow
1. `actions/checkout`
2. instalar dependencias Python
3. correr `python manage.py test asistencias.tests personas.tests finanzas.tests api.tests`
4. abrir SSH al servidor
5. `git fetch`
6. `git reset --hard origin/main`
7. ejecutar `bash scripts/deploy.sh`

## Que hace `scripts/deploy.sh`
- carga variables desde `DEPLOY_ENV_FILE` si existe
- fuerza `DJANGO_ENV=prod` por defecto
- crea virtualenv si no existe
- instala dependencias
- ejecuta `python manage.py migrate --noinput`
- ejecuta `python manage.py collectstatic --noinput`
- ejecuta `python manage.py check`
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
- `python manage.py check --deploy` no se ejecuta automaticamente porque la configuracion de produccion todavia es minima y podria bloquear deploys hasta cerrar endurecimiento de seguridad.

## Recomendaciones inmediatas
- usar un usuario de despliegue dedicado
- servir Django detras de Nginx o un proxy equivalente
- no hacer cambios manuales dentro del clon de produccion
- revisar luego endurecimiento de `prod.py` para poder pasar a `check --deploy`

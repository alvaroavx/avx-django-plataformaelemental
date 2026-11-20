# Releases y recuperación

**Estado:** implementado y probado en local el 2026-11-20. **No aplicado en el
servidor.** Producción sigue usando `scripts/deploy.sh` y `.github/workflows/deploy.yml`
hasta hacer el corte descrito abajo.


Cada release lleva el código bajo `src/`, y `manage.py` y
`gunicorn.conf.py` en la raíz. Gunicorn conserva el módulo WSGI y el
directorio de trabajo `current/`. El hook `pre_checks` verifica la
importación WSGI en la release nueva, antes de migraciones o de mover
`current`. Los alias de Nginx y el enlace a media compartido conservan
las rutas de ejecución bajo `plataformaelemental/`. Al volver a una versión
anterior, Gunicorn usa el contenido y la configuración del checkout apuntado
por `current`.

La validación local del layout simuló `current` apuntando a una release
anterior, a la reorganizada y de vuelta a la anterior. En los tres casos
pasó `gunicorn --check-config plataformaelemental.wsgi:application`.
En la nueva release también se validaron los hooks de arranque y estáticos,
el manifiesto y el enlace a media compartido. Esta prueba de rutas y carga
WSGI se ejecutó fuera del servidor.

## Idea

Cada deploy crea una carpeta nueva con su código, su entorno virtual y sus
estáticos. Un enlace `current` apunta a la versión activa. Volver atrás es mover
ese enlace. Antes de cada deploy se respalda la base.

```text
/srv/apps/elemental/
├── repo.git/                         espejo del repositorio
├── releases/
│   ├── 20261120T052620Z-b2e7c2a4d077/  código + .venv + staticfiles + REVISION
│   └── 20261121T101500Z-1b73cd1.../
├── current -> releases/20261121T...  versión activa (systemd y Nginx)
├── shared/
│   ├── .env.prod                     credenciales (600)
│   ├── release.conf                  configuración de release.sh
│   └── plataformaelemental/media/    archivos subidos (enlazado en cada release)
└── releases.log                      historial: deploy, rollback, restore-db
/var/backups/plataforma-elemental/
└── plataforma-elemental-<release>.dump (+ .sha256)
```

## Archivos

| Archivo | Para qué |
|---|---|
| `scripts/release/release.sh` | Deploy, rollback, restauración de base, listado y limpieza. **Copia idéntica** en `cuadratura-platform-django` |
| `deploy/hooks.sh` | Validaciones propias de Elemental (variables productivas, reparación histórica de asistencias, permisos de estáticos, `clearsessions`) |
| `deploy/release.conf.example` | Configuración: rutas, servicio, Python, respaldos, salud |
| `deploy/systemd/plataforma-elemental.releases.service.example` | Unidad que apunta a `current/` |
| `deploy/nginx/plataforma-elemental.releases.conf.example` | Ruta de estáticos bajo `current/` |

## Qué hace un deploy

`release.sh -c shared/release.conf deploy <sha40>`

1. Toma un lock: no puede haber dos operaciones a la vez.
2. Actualiza el espejo y verifica que el commit exista.
3. Exporta el commit a `releases/<UTC>-<sha12>/` y enlaza lo compartido.
4. Crea `.venv` con Python 3.12 e instala `requirements.txt`.
5. Corre `pre_checks`, `check --deploy`, `makemigrations --check` y `collectstatic`.
6. **Siempre respalda la base** (`pg_dump` custom, verificado con `pg_restore --list` y sha256):
   - sin migraciones pendientes: respaldo en caliente, sin cortar el servicio;
   - con migraciones: detiene el servicio, respalda, migra.
7. Cambia `current`, reinicia y prueba `HEALTH_URL`.
8. Si la salud falla, **vuelve solo** a la release anterior. Si ya había migrado,
   avisa con el comando exacto para restaurar la base.
9. Registra en `releases.log` y deja las últimas 5 releases (más la anterior a la
   activa) y los últimos 20 respaldos.

Si falla el respaldo o la migración, el servicio queda detenido y `current` no
cambia: mismo criterio que `scripts/deploy.sh`.

## Recuperación

| Problema | Qué hacer |
|---|---|
| El código nuevo falla y no hubo migraciones | `release.sh -c … rollback` (a la anterior) o `rollback <release_id>` |
| El código nuevo falla y sí migró | `rollback`; si la versión anterior no entiende la base, `restore-db /var/backups/plataforma-elemental/plataforma-elemental-<release>.dump --confirm plataforma_elemental_prod` |
| Un borrado o dato equivocado | `restore-db` con el respaldo anterior al problema |
| Se perdió el servidor | Restaurar el backup semanal del Droplet en DigitalOcean; luego revisar `releases.log` y `list` |

`restore-db` primero guarda un respaldo de seguridad del estado actual
(`…-pre-restore-<fecha>.dump`), borra los objetos del usuario de la app y
restaura **en una sola transacción**: si algo falla, la base queda como estaba.
Se deshace restaurando ese respaldo de seguridad.

`release.sh -c … list` muestra las releases, la activa y los últimos movimientos.

## Corte desde el esquema actual (pendiente, no ejecutado)

Hoy el código vive en `/srv/elementos` como checkout de Git y el deploy hace
`git checkout` ahí mismo. Pasos para cambiar, con autorización explícita:

1. Crear `/srv/apps/elemental/{shared,releases}` y `git clone --mirror <origin> /srv/apps/elemental/repo.git`
   (con la misma llave de deploy que usa hoy `/srv/elementos`).
2. Copiar `/srv/elementos/.env.prod` a `shared/.env.prod` (600) y
   `/srv/elementos/plataformaelemental/media/` a `shared/plataformaelemental/media/`.
3. Copiar `deploy/release.conf.example` a `shared/release.conf`.
4. Primer deploy del commit productivo:
   `bash <(git --git-dir=/srv/apps/elemental/repo.git show <sha>:scripts/release/release.sh) -c /srv/apps/elemental/shared/release.conf deploy <sha>`
5. Instalar la unidad y el bloque de Nginx de `deploy/`, `systemctl daemon-reload`,
   reiniciar el servicio, `nginx -t` y recargar.
6. Verificar salud y navegación. Dejar `/srv/elementos` intacto unos días como respaldo.
7. Cambiar el paso «Deploy to production» de `.github/workflows/deploy.yml` para que
   ejecute el comando del punto 4 con `RELEASE_COMMIT`.

**Mientras no se haga el punto 7**, hacer push de estos archivos no cambia nada en
producción: el workflow sigue llamando a `scripts/deploy.sh`.

## Prueba local registrada (2026-11-20)

Sobre un clon desechable de Cuadratura (mismo script), PostgreSQL 18 desechable y
Gunicorn en lugar de systemd. Se validó: primer deploy con todas las migraciones,
deploy sin migraciones (respaldo en caliente), deploy con migración (detiene,
respalda, migra), deploy con salud rota (vuelve solo), lock entre operaciones,
rollback manual, `restore-db` exacto y reversible, rechazo sin `--confirm`, listado
y limpieza. Los hooks de Elemental solo se revisaron con `bash -n`: sus
validaciones exigen variables productivas.

# Plataforma Elemental

Plataforma administrativa construida en Django para operar organizaciones, asistencias y finanzas desde una sola base.

Hoy el proyecto integra:
- operación académica diaria
- CRM de personas, roles y organizaciones
- pagos y consumo de clases
- transacciones de caja
- preparación mensual y exportación JSON versionada hacia Cuadratura (`elemental-cuadratura-v1`)
- API minima de salud/estado/version

## Estado actual

Reglas funcionales vigentes:
- `Payment` y `Transaction` son entidades separadas y pueden enlazarse uno a uno
- la documentación fiscal y contable pertenece a Cuadratura, no a Plataforma Elemental
- los filtros globales `periodo_mes`, `periodo_anio` y `organizacion` deben mantenerse en toda la navegación HTML
- los modelos viven en su app dueña; la app legacy `database/` fue retirada del producto activo y del grafo vigente de migraciones

## Apps del proyecto

### `asistencias`
- disciplinas, calendario y sesiones (individuales y masivas)
- registro de asistencia y clases liberadas
- asignaciones profesor–disciplina y matrículas alumno–disciplina
- listados operativos de estudiantes y profesores, borrador de correo mensual de cierre por profesor
- integración con consumo financiero de clases

El portal dedicado de profesores (`/profesor/`) fue retirado el 2026-10-08
([ADR 0016](docs/adr/0016-retira-portal-profesor-conserva-dominio.md)); el rol
Profesor y sus relaciones se conservan.

### `personas`
- personas
- roles por organización
- organizaciones
- login Google controlado y solicitudes de acceso
- vista administrativa consolidada

### `finanzas`
- planes
- pagos individuales y lotes de pago masivo idempotentes, con reversa histórica
- transacciones
- categorías, reportes y exportaciones CSV/XLSX
- `Preparar mes`: vista previa y descarga del contrato JSON `elemental-cuadratura-v1`

La documentación fiscal (boletas, facturas) y la conciliación pertenecen a
Cuadratura ([ADR 0015](docs/adr/0015-cuadratura-duena-documentacion-fiscal.md)).

### `api`
- endpoints minimos operativos
- health/status/version
- check minimo de usuario autenticado

### `auditoria`
- trazabilidad parcial de mutaciones sensibles
- revisión de solo lectura desde Django Admin

## Arquitectura

### Stack
- Python 3.12
- Django 5.2.9
- Django REST Framework
- PostgreSQL activo en `dev` y `prod`
- PostgreSQL es el único motor configurado; SQLite no es un fallback soportado
- Bootstrap 5
- DataTables
- Tom Select

### Estructura del repo
- `plataformaelemental/`: configuración del proyecto Django
- `asistencias/`: dominio académico
- `personas/`: personas, roles y organizaciones
- `finanzas/`: pagos, consumo de clases y caja
- `api/`: API minima de salud/estado/version
- `auditoria/`: registro best-effort de mutaciones sensibles
- `templates/`: plantillas compartidas
- `scripts/`: deploy, releases escalonados, validadores de documentación y CI
- `deploy/`: ejemplo de unit `systemd`
- `docs/`: documentación viva
- `data/`: cargas y soporte de datos

### Ownership de modelos
- `personas.models`: `Organizacion`, `Persona`, `Rol`, `PersonaRol`, `SolicitudAcceso` y, en curso (sin commitear al 2026-10-12), `ConfiguracionPermisoRol`
- `asistencias.models`: `Disciplina`, `AsignacionProfesorDisciplina`, `AlumnoDisciplina`, `BloqueHorario`, `SesionClase`, `LiberacionSesion`, `Asistencia`, `ClaseLiberada`
- `finanzas.models`: `PaymentPlan`, `Category`, `LotePago`, `Payment`, `AttendanceConsumption`, `Transaction`
- `auditoria.models`: `AuditLog`
- `api.models`: `ApiAccessKey`

## Rutas principales

### Acceso
- `/` (Panel transversal) y `/resumen/<metrica>/` (detalle de indicadores)
- `/app/` (redirige a `/`)
- `/accounts/login/`, `/accounts/emergencia/` (solo superusuarios), `/accounts/logout/`
- `/accounts/google/iniciar/` y `/accounts/google/login/callback/`
- `/admin/`

### HTML
- `/asistencias/` (redirige al calendario `/asistencias/calendario/`)
- `/personas/`
- `/finanzas/`
- `/finanzas/preparar-mes/` y `/finanzas/preparar-mes/descargar/` (contrato Cuadratura)

### API base
- `/api/health/`
- `/api/me/`
- `/api/status/`
- `/api/version/`

## Entorno local

Usar Python 3.12 para recrear el virtualenv local.

No usar `python3 -m venv` en este proyecto si Ubuntu tiene `python3` apuntando a Python 3.14. Ese alias puede crear un entorno incompatible con las dependencias actuales.

### Crear entorno virtual
```bash
python3.12 -m venv .venv
```

### Activar entorno virtual
```bash
source ./.venv/bin/activate
```

### Instalar dependencias
```bash
python -m pip install -r requirements.txt
```

### Aplicar migraciones
```bash
set -a
source .env.dev
set +a
python manage.py migrate
```

### Levantar servidor local
```bash
cd /home/alvax/Code/EspacioElementos/avx-django-plataformaelemental
source .venv/bin/activate
set -a
source .env.dev
set +a
python manage.py runserver 127.0.0.1:8000
```

`runserver` recarga automáticamente el proceso cuando detecta cambios en Python
o en las plantillas durante el desarrollo local.

Cuando se pruebe el acceso Google, `http://127.0.0.1:8000` es el origen local
canónico. Google Cloud debe autorizar exactamente
`http://127.0.0.1:8000/accounts/google/login/callback/`; cambiar host o puerto
genera `redirect_uri_mismatch`. Después de cambiar el origen hay que iniciar un
flujo OAuth nuevo: recargar una página de error conserva el callback anterior.
La decisión y el diagnóstico están registrados en
[`docs/adr/0003-origen-local-canonico-oauth.md`](docs/adr/0003-origen-local-canonico-oauth.md).

## Uso operativo básico

### Flujo académico
1. Crear organización y disciplinas.
2. Registrar personas y asignar roles.
3. Crear sesiones.
4. Registrar asistencias.
5. Revisar estado académico y financiero por persona.

### Flujo financiero
1. Crear planes si corresponde.
2. Registrar pagos.
3. Consumir clases contra asistencias del mismo mes y año.
4. Revisar saldo, deudas y resúmenes.

## API minima

Estado v1.0:
- No se exponen personas, asistencias, pagos ni transacciones por API.
- `GET /api/health/`, `GET /api/status/` y `GET /api/version/` son publicos.
- `GET /api/me/` requiere usuario autenticado y devuelve payload minimo.
- `ApiAccessKey` se conserva temporalmente por compatibilidad historica, pero no hay endpoints de datos activos que la usen.

### Consultar estado
```bash
curl http://127.0.0.1:8000/api/health/
curl http://127.0.0.1:8000/api/status/
curl http://127.0.0.1:8000/api/version/
```

### Seguridad base actual
- throttling por usuario, API key o IP
- sin endpoints de datos activos por API key
- sin endpoints API mutables de operacion en v1.0

## CI/CD y despliegue

El proyecto incluye una base mínima de CI/CD con GitHub Actions
(`.github/workflows/deploy.yml`, `test.yml` y `release-asistencias-escalonado.yml`):
- en cada push a `main` corre `check`, `makemigrations --check`, `ruff check .`
  y los tests de `asistencias finanzas personas` sobre PostgreSQL 16 y Python 3.12
  (no corre `api`, `auditoria` ni `plataformaelemental`; ver
  [docs/ESTADO_ACTUAL.md](docs/ESTADO_ACTUAL.md))
- si los tests pasan, despliega por SSH el SHA probado (checkout detached) con
  `scripts/deploy.sh`
- el servidor instala dependencias; si hay migraciones pendientes detiene el
  servicio, respalda PostgreSQL con `pg_dump` en `DEPLOY_BACKUP_DIR` y aplica
  `migrate`; luego publica estáticos, ejecuta `check --deploy` y reinicia `systemd`
- las reparaciones históricas de `asistencias` (0004b–0007) no se aplican por esta
  vía: el script aborta y deben ir por el release escalonado

La guía operativa completa está en:
- [docs/operacion/DEPLOY.md](https://github.com/alvaroavx/avx-django-plataformaelemental/blob/main/docs/operacion/DEPLOY.md)

### Secrets de GitHub Actions

Obligatorios:
- `DEPLOY_HOST`
- `DEPLOY_USER`
- `DEPLOY_SSH_KEY_B64`
- `DEPLOY_PATH`
- `DEPLOY_SERVICE`
  - acepta nombre con o sin sufijo `.service`
  - valor real de producción: `plataforma-elemental`
- `DEPLOY_ENV_FILE`
  - contiene una ruta absoluta al archivo de entorno local del servidor; no contiene ni transporta su contenido.

Opcionales:
- `DEPLOY_PORT`
  - default: `22`
- `DEPLOY_BACKUP_DIR`
  - obligatorio en la práctica cuando el release trae migraciones pendientes; ahí se escribe el `pg_dump` previo
- `DEPLOY_VENV_DIR`
  - si no se define, usa `.venv` dentro del repo
- `DEPLOY_PYTHON_BIN`
  - si no se define, usa `python3`

### Llave SSH de deploy

No intentes reutilizar una llave con passphrase para GitHub Actions.
Lo correcto es crear una llave nueva, exclusiva para deploy, sin passphrase.

Ejemplo:

```bash
ssh-keygen -t ed25519 -C "github-actions-deploy@plataforma-elemental" -f ~/.ssh/plataforma_elemental_deploy -N ""
```

Eso genera:
- privada: `~/.ssh/plataforma_elemental_deploy`
- publica: `~/.ssh/plataforma_elemental_deploy.pub`

Instalacion:
1. Copia la publica al servidor, al `authorized_keys` del usuario definido en `DEPLOY_USER`.
2. Crea el secret `DEPLOY_SSH_KEY_B64` con la clave privada codificada en Base64.
3. Prueba localmente antes del workflow:

```bash
ssh -i ~/.ssh/plataforma_elemental_deploy -o IdentitiesOnly=yes -p 22 USUARIO@HOST
```

Si esa prueba local falla, el workflow tambien fallara.

Ejemplo para generar `DEPLOY_SSH_KEY_B64`:

```bash
base64 < ~/.ssh/plataforma_elemental_deploy | tr -d '\n'
```

## Testing

### Suite completa
```bash
python manage.py test
```

Los tests necesitan una base PostgreSQL de pruebas (`test_<POSTGRES_DB>`). Si el
rol de base de datos no puede crearla en cada corrida, reutilizarla con
`python manage.py test --keepdb --noinput`.

### Por app
```bash
python manage.py test asistencias
python manage.py test personas
python manage.py test finanzas
python manage.py test api auditoria plataformaelemental
```

Última validación conocida:
- inventario al 2026-10-12: 394 métodos `test_*` en `HEAD` y 400 en el árbol de trabajo con cambios en curso
- estado y evidencia: [docs/ESTADO_ACTUAL.md](docs/ESTADO_ACTUAL.md)

### Comandos de gestión propios
- `personas`: `importar_personas`, `auditar_datos_v1`, `auditar_identidades_acceso` (solo lectura)
- `asistencias`: `import_asistencias`, `poblar_mes_pruebas` (solo desarrollo, preview por defecto),
  `reportar_relaciones_historicas`, `activar_relaciones_operativas` (preview salvo confirmación literal)
- `finanzas`: `reconciliar_integridad_dominio` (diagnóstico sin escrituras)
- `api`: `crear_api_key`

La validación de cierre debe usar `python manage.py test`; una lista manual de
apps puede omitir pruebas transversales, auditoría o módulos nuevos.

## Documentación

Orden recomendado:
1. [AGENTS.md](https://github.com/alvaroavx/avx-django-plataformaelemental/blob/main/AGENTS.md)
2. [docs/INDICE.md](https://github.com/alvaroavx/avx-django-plataformaelemental/blob/main/docs/INDICE.md)
3. [docs/arquitectura/PLATAFORMA.md](https://github.com/alvaroavx/avx-django-plataformaelemental/blob/main/docs/arquitectura/PLATAFORMA.md)
4. [docs/proceso/DECISIONES.md](https://github.com/alvaroavx/avx-django-plataformaelemental/blob/main/docs/proceso/DECISIONES.md)
5. Documentos por app:
   - [docs/apps/ASISTENCIAS.md](https://github.com/alvaroavx/avx-django-plataformaelemental/blob/main/docs/apps/ASISTENCIAS.md)
   - [docs/apps/PERSONAS.md](https://github.com/alvaroavx/avx-django-plataformaelemental/blob/main/docs/apps/PERSONAS.md)
   - [docs/apps/FINANZAS.md](https://github.com/alvaroavx/avx-django-plataformaelemental/blob/main/docs/apps/FINANZAS.md)
   - [docs/apps/API.md](https://github.com/alvaroavx/avx-django-plataformaelemental/blob/main/docs/apps/API.md)
6. Documentos operativos:
   - [docs/operacion/DEPLOY.md](https://github.com/alvaroavx/avx-django-plataformaelemental/blob/main/docs/operacion/DEPLOY.md)

## Observaciones

- `README.md` es el documento general y humano del proyecto.
- `AGENTS.md` se mantiene en la raíz porque contiene reglas operativas del agente.
- La documentación viva del proyecto debe vivir dentro de `docs/`.

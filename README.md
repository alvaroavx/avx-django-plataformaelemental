# Plataforma Elemental

Plataforma administrativa construida en Django para operar organizaciones, asistencias y finanzas desde una sola base.

Hoy el proyecto integra:
- operación académica diaria
- CRM de personas, roles y organizaciones
- pagos y consumo de clases
- documentos tributarios opcionales
- transacciones de caja
- API externa versionada para consumo desde clientes externos

## Estado actual

Reglas funcionales vigentes:
- la plataforma debe funcionar aunque no existan documentos tributarios
- `Payment`, `Transaction` y `DocumentoTributario` son entidades separadas
- los filtros globales `periodo_mes`, `periodo_anio` y `organizacion` deben mantenerse en toda la navegación HTML
- los modelos viven en su app dueña y `database/` quedó como namespace legado de migraciones y compatibilidad histórica

## Apps del proyecto

### `asistencias`
- sesiones
- registro de asistencia
- perfiles operativos de estudiantes y profesores
- integración con consumo financiero de clases

### `personas`
- personas
- roles por organización
- organizaciones
- vista administrativa consolidada

### `finanzas`
- planes
- pagos
- documentos tributarios
- carga asistida XML/PDF para documentos tributarios
- transacciones
- categorías y reportes

### `api`
- API REST externa
- endpoints base bajo `/api/v1/`
- autenticación por token para usuarios
- API key de solo lectura para consultas externas
- rate limiting por usuario, API key o IP

## Arquitectura

### Stack
- Django 5
- Django REST Framework
- SQLite activa en `dev` y `prod`
- PostgreSQL documentado como alternativa futura comentada en configuración
- Bootstrap 5
- DataTables
- Tom Select

### Estructura del repo
- `plataformaelemental/`: configuración del proyecto Django
- `asistencias/`: dominio académico
- `personas/`: personas, roles y organizaciones
- `finanzas/`: pagos, documentos tributarios y caja
- `api/`: API externa
- `docs/`: documentación viva
- `data/`: cargas y soporte de datos
- `database/`: compatibilidad histórica de migraciones

### Ownership de modelos
- `personas.models`: `Organizacion`, `Persona`, `Rol`, `PersonaRol`
- `asistencias.models`: `Disciplina`, `BloqueHorario`, `SesionClase`, `Asistencia`
- `finanzas.models`: `PaymentPlan`, `Payment`, `DocumentoTributario`, `AttendanceConsumption`, `Transaction`, `Category`

## Rutas principales

### Acceso
- `/`
- `/app/`
- `/accounts/login/`
- `/admin/`

### HTML
- `/asistencias/`
- `/personas/`
- `/finanzas/`

### API base
- `/api/health/`
- `/api/me/`
- `/api/auth/login/`
- `/api/auth/refresh/`
- `/api/auth/logout/`
- `/api/v1/personas/organizaciones/`
- `/api/v1/personas/personas/`
- `/api/v1/personas/resumen/`
- `/api/v1/asistencias/disciplinas/`
- `/api/v1/asistencias/sesiones/`
- `/api/v1/asistencias/asistencias/`
- `/api/v1/asistencias/resumen/`
- `/api/v1/finanzas/planes/`
- `/api/v1/finanzas/pagos/`
- `/api/v1/finanzas/documentos-tributarios/`
- `/api/v1/finanzas/transacciones/`
- `/api/v1/finanzas/resumen/`

## Puesta en marcha

### Activar entorno virtual
```bash
source ./.venv/bin/activate
```

### Instalar dependencias
```bash
pip install -r requirements.txt
```

### Aplicar migraciones
```bash
python manage.py migrate
```

### Levantar servidor local
```bash
python manage.py runserver
```

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

### Flujo tributario
1. Registrar un documento tributario manualmente o por carga asistida.
2. Revisar y corregir los campos precargados.
3. Confirmar el guardado final.
4. Asociarlo a pagos o transacciones si corresponde.

## Carga asistida de documentos tributarios

Estado actual:
- XML-first
- soporte base para DTE XML clásico
- soporte base para boleta de honorarios XML
- parser PDF fallback
- revisión humana antes del guardado
- visor inline del archivo cargado en la pantalla de revisión

Reglas:
- si hay XML y PDF, prevalece XML
- si hay solo PDF, el resultado depende de que el archivo tenga texto seleccionable
- subir un archivo no guarda automáticamente el registro final

## API externa

### Autenticación disponible
- token DRF para usuarios autenticados
- API key de solo lectura para consultas externas

### Crear API key
```bash
python manage.py crear_api_key integracion-externa
```

### Consultar con API key
```bash
curl -H "X-API-Key: <tu_clave>" http://127.0.0.1:8000/api/v1/personas/organizaciones/
curl -H "Authorization: ApiKey <tu_clave>" "http://127.0.0.1:8000/api/v1/finanzas/pagos/?organizacion=1&periodo_mes=4&periodo_anio=2026"
```

### Obtener token de usuario
```bash
curl -X POST http://127.0.0.1:8000/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"username":"usuario","password":"clave"}'
```

### Seguridad base actual
- throttling por usuario, API key o IP
- throttling más estricto para login
- API key solo para lectura
- escrituras requieren usuario autenticado

## CI/CD y despliegue

El proyecto incluye una base mínima de CI/CD con GitHub Actions:
- corre tests en cada push a `main`
- si los tests pasan, despliega por SSH al servidor
- el servidor actualiza código, instala dependencias, migra, recopila estáticos y reinicia `systemd`

La guía operativa completa está en:
- [docs/operacion/DEPLOY.md](/home/alvax/Code/platforms/avx-django-plataformaelemental/docs/operacion/DEPLOY.md)

### Secrets de GitHub Actions

Obligatorios:
- `DEPLOY_HOST`
- `DEPLOY_USER`
- `DEPLOY_SSH_KEY`
- `DEPLOY_SSH_KEY_B64`
- `DEPLOY_PATH`
- `DEPLOY_SERVICE`

Opcionales:
- `DEPLOY_PORT`
  - default: `22`
- `DEPLOY_ENV_FILE`
  - si no se define, `scripts/deploy.sh` no carga archivo de entorno externo
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
2. Copia la privada completa al secret `DEPLOY_SSH_KEY` en GitHub Actions.
3. Crea tambien el secret `DEPLOY_SSH_KEY_B64` con la misma clave codificada en Base64.
4. Prueba localmente antes del workflow:

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

### Por app
```bash
python manage.py test asistencias.tests
python manage.py test personas.tests
python manage.py test finanzas.tests
python manage.py test api.tests
```

Última validación conocida:
- `python manage.py test asistencias.tests personas.tests finanzas.tests api.tests`
- resultado: `99 tests OK`

## Documentación

Orden recomendado:
1. [AGENTS.md](/home/alvax/Code/platforms/avx-django-plataformaelemental/AGENTS.md)
2. [docs/INDICE.md](/home/alvax/Code/platforms/avx-django-plataformaelemental/docs/INDICE.md)
3. [docs/arquitectura/PLATAFORMA.md](/home/alvax/Code/platforms/avx-django-plataformaelemental/docs/arquitectura/PLATAFORMA.md)
4. [docs/proceso/DECISIONES.md](/home/alvax/Code/platforms/avx-django-plataformaelemental/docs/proceso/DECISIONES.md)
5. Documentos por app:
   - [docs/apps/ASISTENCIAS.md](/home/alvax/Code/platforms/avx-django-plataformaelemental/docs/apps/ASISTENCIAS.md)
   - [docs/apps/PERSONAS.md](/home/alvax/Code/platforms/avx-django-plataformaelemental/docs/apps/PERSONAS.md)
   - [docs/apps/FINANZAS.md](/home/alvax/Code/platforms/avx-django-plataformaelemental/docs/apps/FINANZAS.md)
   - [docs/apps/API.md](/home/alvax/Code/platforms/avx-django-plataformaelemental/docs/apps/API.md)
6. Documentos operativos:
   - [docs/operacion/DEPLOY.md](/home/alvax/Code/platforms/avx-django-plataformaelemental/docs/operacion/DEPLOY.md)

## Observaciones

- `README.md` es el documento general y humano del proyecto.
- `AGENTS.md` se mantiene en la raíz porque contiene reglas operativas del agente.
- La documentación viva del proyecto debe vivir dentro de `docs/`.

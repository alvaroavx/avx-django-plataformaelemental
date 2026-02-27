# avx-django-plataformaelemental
Plataforma administrativa para Espacio Elementos, construida con Django + Django REST Framework.

## Puesta en marcha
1. Activa el entorno virtual:
   ```bash
   .\.venv\Scripts\activate
   ```
2. Copia `.env.example` a `.env` y completa al menos:
   - `DJANGO_SECRET_KEY`
   - `DJANGO_ENV`
   - `DJANGO_ALLOWED_HOSTS`
   - `DJANGO_CSRF_TRUSTED_ORIGINS`
3. Instala dependencias:
   ```bash
   pip install -r requirements.txt
   ```
4. Ejecuta migraciones y crea un usuario administrador:
   ```bash
   python manage.py migrate
   python manage.py createsuperuser
   ```
5. Levanta el servidor:
   ```bash
   python manage.py runserver
   ```

Accesos:
- Admin Django: `http://127.0.0.1:8000/admin/`
- Login: `http://127.0.0.1:8000/accounts/login/`
- App Web: `http://127.0.0.1:8000/app/`

La ruta `/` redirige a `/app/`. El login redirige a `/app/` y el logout vuelve a `/accounts/login/`.

## App Web (/app/)
Enfocada en operacion administrativa y asistencia academica.

Rutas disponibles:
- Panel administrador: `/app/`
- Talleres/sesiones: `/app/sesiones/`
- Asistencias: `/app/asistencias/`
- Perfil de persona: `/app/personas/<id>/`
- Estudiantes: `/app/estudiantes/`
- Profesores: `/app/profesores/`
- Organizaciones: `/app/organizaciones/`

Flujos rapidos:
- Crear sesion y cargar asistentes desde `/app/asistencias/`.
- Alta rapida de persona en `/app/asistencias/` (se asigna rol ESTUDIANTE cuando aplica).
- Revision de asistencia por persona en `/app/personas/<id>/`.

## Variables de entorno (dev)
Si quieres un punto de partida rapido, puedes copiar `.env.dev` y ajustar `DJANGO_SECRET_KEY`.

## Comando de trabajo Codex
```bash
codex resume 019b6a94-f3a0-7cf2-98d1-fed2abe0e70c
```

## API REST
Autenticacion disponible:
- Session Authentication
- Token Authentication

| Endpoint | Metodo | Descripcion |
| --- | --- | --- |
| `/api/health/` | GET | Estado del servicio. |
| `/api/auth/login/` | POST | Credenciales -> token + datos del usuario. |
| `/api/auth/refresh/` | POST | Rota el token actual. |
| `/api/auth/logout/` | POST | Invalida el token. |
| `/api/sesiones/` | GET | Lista de sesiones (filtro `?fecha=YYYY-MM-DD`). |
| `/api/sesiones/<id>/asistencias/` | GET/POST | Consulta o registra asistencias (`persona`, `estado`). |
| `/api/estudiantes/` | GET | Personas con rol estudiante. |
| `/api/estudiantes/<id>/estado/` | GET | Totales de asistencia del estudiante. |
| `/api/reportes/resumen/` | GET | Totales generales de sesiones, asistencias y estudiantes. |

## Importar planillas Excel
Coloca los archivos en `data/` y ejecuta:
```bash
python manage.py import_asistencias --archivo "Asistencia Talleres Elementos.xlsx"
```

## Carga masiva de personas desde texto
```bash
python manage.py importar_personas <ruta_al_archivo> --dominio elementos.cl
```

Opciones:
- `--dominio`: dominio para correos generados (por defecto `example.com`).
- `--dry-run`: simula la importacion.

## Pruebas automatizadas
```bash
python manage.py test
```

## Settings por entorno
`DJANGO_ENV` define que modulo se usa:
- `dev` (por defecto) -> `plataformaelemental.config.dev`
- `prod` -> `plataformaelemental.config.prod`

Tambien puedes forzar el modulo con:
`DJANGO_SETTINGS_MODULE=plataformaelemental.config.<entorno>`.

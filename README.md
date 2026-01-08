# avx-django-plataformaelemental
Plataforma administrativa para Espacio Elementos construida con Django + Django REST Framework.

## Puesta en marcha
1. Activa el entorno virtual `.\.venv\Scripts\activate`.
2. Copia `.env.example` a `.env` y completa al menos `DJANGO_SECRET_KEY`, `DJANGO_ENV`, `DJANGO_ALLOWED_HOSTS` y `DJANGO_CSRF_TRUSTED_ORIGINS`.
3. Instala dependencias:
   ```bash
   pip install -r requirements.txt
   ```
4. Ejecuta migraciones y crea un usuario administrador:
   ```bash
   python manage.py migrate
   python manage.py createsuperuser
   ```
5. Levanta el servidor de desarrollo:
   ```bash
   python manage.py runserver
   ```
   - Django Admin: `http://127.0.0.1:8000/admin/`
   - App Web: `http://127.0.0.1:8000/app/`

El proyecto usa locale `es-cl` y zona horaria `America/Santiago`. Los comprobantes subidos se almacenan en `media/comprobantes/`.

## App Web (/app/) – Bootstrap 5 mobile-first
- **Dashboard** (`/app/`), **Notificaciones** (`/app/notificaciones/`) y **Ayuda** (`/app/ayuda/`).
- **Académico**: disciplinas (`/app/disciplinas/`), horarios (`/app/horarios/`), sesiones (`/app/sesiones/`, `/app/sesiones/<id>/`), creación rápida (`/app/sesiones/nueva/`) y checklist móvil de asistencia (`/app/sesiones/<id>/asistencia/`, `/app/asistencia/`, `/app/asistencia/historial/`).
- **Personas y roles**: listado (`/app/personas/`), ficha (`/app/personas/<id>/`), asignación de roles (`/app/personas/<id>/roles/`) y creación de usuarios (`/app/personas/<id>/usuario/`).
- **Planes y estudiantes**: catálogo de planes (`/app/planes/`), estudiantes (`/app/estudiantes/`), estado detallado (`/app/estudiantes/<id>/estado/`), suscripciones (`/app/estudiantes/<id>/suscripciones/`) y convenios (`/app/convenios/`).
- **Pagos y morosos**: pagos (`/app/pagos/`, `/app/pagos/nuevo/`, `/app/pagos/<id>/`) con comprobante opcional, además de `/app/morosos/`.
- **Liquidaciones**: listado (`/app/liquidaciones/`), generación (`/app/liquidaciones/nueva/`) y detalle (`/app/liquidaciones/<id>/`) con bruto, retención (14.5%) y neto.
- **Finanzas**: dashboard (`/app/finanzas/`), movimientos (`/app/finanzas/movimientos/`), alta de movimientos (`/app/finanzas/movimientos/nuevo/`), categorías (`/app/finanzas/categorias/`) y resumen mensual (`/app/finanzas/resumen/`).
- **Reportes**: `/app/reportes/` con ranking de asistencia, métricas y botón de exportación (placeholder en `/app/reportes/exportar/`).
- **Importaciones y configuración**: `/app/importaciones/`, `/app/importaciones/historial/`, `/app/configuracion/`, `/app/usuarios/`, `/app/auditoria/`.

Permisos (via `role_required` + roles en `PersonaRol`):
- `ADMIN`: acceso total.
- `STAFF_ASISTENCIA`: sesiones y asistencia.
- `STAFF_FINANZAS`: pagos, morosos, finanzas y liquidaciones.
- `PROFESOR`: dashboard simplificado, agenda y checklist móvil.

## API REST
Autenticación actual: Token Authentication (cabecera `Authorization: Token <token>`).

| Endpoint | Método | Descripción |
| --- | --- | --- |
| `/api/health/` | GET | Estado del servicio. |
| `/api/auth/login/` | POST | Credenciales → token + datos del usuario. |
| `/api/auth/refresh/` | POST | Rota el token actual. |
| `/api/auth/logout/` | POST | Invalida el token. |
| `/api/sesiones/` | GET | Lista de sesiones (filtro `?fecha=YYYY-MM-DD`). |
| `/api/sesiones/<id>/asistencias/` | GET/POST | Consulta o registra asistencias. POST acepta `persona`, `estado`, `convenio`. |
| `/api/estudiantes/` | GET | Personas con rol estudiante o con suscripción vigente. |
| `/api/estudiantes/<id>/estado/` | GET | Plan, clases asignadas/usadas/sobreconsumo y saldo. |
| `/api/reportes/resumen/` | GET | Totales de sesiones, asistencias, ingresos y egresos. |

## Importar planillas Excel
Coloca los archivos en `data/` y ejecuta:
```bash
python manage.py import_inscripciones --archivo "Ficha de inscripción_ Espacio Elementos. (Respuestas).xlsx"
python manage.py import_asistencias --archivo "Asistencia Talleres Elementos.xlsx"
python manage.py import_libro_caja --archivo "Libro Caja Espacio Elementos.xlsx"
```
- Se usa `openpyxl` para leer los libros.
- Los comandos normalizan los encabezados más comunes, ignoran filas incompletas y reportan duplicados en consola.

## Pruebas automatizadas
```bash
python manage.py test
```
Incluye pruebas para autenticación, cálculos de planes/liquidaciones, API REST y modelos de finanzas.

## Settings por entorno
`DJANGO_ENV` define qué módulo se emplea:
- `dev` (por defecto) → `plataformaelemental.config.dev` (`DEBUG=True`, `ALLOWED_HOSTS=["*"]`).
- `prod` → `plataformaelemental.config.prod`. Configura `DJANGO_ALLOWED_HOSTS` y `DJANGO_CSRF_TRUSTED_ORIGINS` separados por comas.

También puedes forzar el módulo directamente con `DJANGO_SETTINGS_MODULE=plataformaelemental.config.<entorno>`.

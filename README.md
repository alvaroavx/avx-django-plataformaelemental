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
   - Login: `http://127.0.0.1:8000/accounts/login/`
   - App Web: `http://127.0.0.1:8000/app/`

La ruta `/` redirige automaticamente a `/app/`. El login redirige a `/app/` y el logout vuelve a `/accounts/login/`.

El proyecto usa locale `es-cl` y zona horaria `America/Santiago`. Los comprobantes subidos se almacenan en `media/comprobantes/`.

## App Web (/app/) - Bootstrap 5 mobile-first
Esta primera version esta enfocada solo en el perfil ADMIN para carga rapida. La validacion es minima para privilegiar la operacion diaria.

Rutas disponibles:
- **Panel administrador**: `/app/` con alertas, accesos rapidos y resumen mensual.
- **Talleres / sesiones**: `/app/sesiones/` y creacion rapida en `/app/sesiones/rapida/`.
- **Asistencia**: `/app/asistencias/` (nuevo flujo de alta rapida) y `/app/sesiones/<id>/asistencia/` (checklist por sesion).
- **Personas**: perfil en `/app/personas/<id>/`.
- **Estudiantes**: `/app/estudiantes/` con filtros por organizacion, morosos y plan.
- **Profesores**: `/app/profesores/` con acceso al perfil.
- **Pagos**: `/app/pagos/` (listado). La carga rapida se hace desde `/app/asistencias/`.
- **Finanzas unificadas**: `/app/finanzas/unificadas/` con pagos alumnos, pagos a profesores y movimientos.

Flujos rapidos recomendados:
- Crear sesion + asistencia: entra a `/app/sesiones/rapida/` y registra asistentes en el mismo lugar.
- Registro masivo de asistencia: entra a `/app/asistencias/`, crea una sesion basica y agrega estudiantes con select multiple.
- Alta rapida de personas: en `/app/asistencias/` usa la seccion "Nueva persona" (nombre, apellido, telefono). Se asigna rol ESTUDIANTE.

Notas operativas:
- La asistencia puede registrarse sin suscripcion activa. Los pagos pueden registrarse despues.
- En sesiones se usa un solo campo de profesores (seleccion multiple).
- El nombre automatico de sesion se arma como `Disciplina - Fecha`.
- La UI usa Bootstrap 5, Bootstrap Icons y DataTables via CDN (no requiere dependencias extra en `requirements.txt`).

## Variables de entorno (dev)
Si quieres un punto de partida rapido, puedes copiar `.env.dev` y ajustar `DJANGO_SECRET_KEY`.

## Comando de trabajo Codex
Comando habitual:
```bash
codex resume 019b6a94-f3a0-7cf2-98d1-fed2abe0e70c
```

Permisos:
- `ADMIN`: acceso total al panel y a todas las rutas de `/app/`.

## API REST
Autenticacion actual: Token Authentication (cabecera `Authorization: Token <token>`).

| Endpoint | Metodo | Descripcion |
| --- | --- | --- |
| `/api/health/` | GET | Estado del servicio. |
| `/api/auth/login/` | POST | Credenciales -> token + datos del usuario. |
| `/api/auth/refresh/` | POST | Rota el token actual. |
| `/api/auth/logout/` | POST | Invalida el token. |
| `/api/sesiones/` | GET | Lista de sesiones (filtro `?fecha=YYYY-MM-DD`). |
| `/api/sesiones/<id>/asistencias/` | GET/POST | Consulta o registra asistencias. POST acepta `persona`, `estado`, `convenio`. |
| `/api/estudiantes/` | GET | Personas con rol estudiante o con suscripcion vigente. |
| `/api/estudiantes/<id>/estado/` | GET | Plan, clases asignadas/usadas/sobreconsumo y saldo. |
| `/api/reportes/resumen/` | GET | Totales de sesiones, asistencias, ingresos y egresos. |

## Importar planillas Excel
Coloca los archivos en `data/` y ejecuta:
```bash
python manage.py import_inscripciones --archivo "Ficha de inscripcion_ Espacio Elementos. (Respuestas).xlsx"
python manage.py import_asistencias --archivo "Asistencia Talleres Elementos.xlsx"
python manage.py import_libro_caja --archivo "Libro Caja Espacio Elementos.xlsx"
```
- Se usa `openpyxl` para leer los libros.
- Los comandos normalizan encabezados comunes, ignoran filas incompletas y reportan duplicados en consola.

## Carga masiva de Personas desde texto
Puedes importar personas desde un archivo `.txt` con 1 persona por linea usando:

```bash
python manage.py importar_personas <ruta_al_archivo> --dominio elementos.cl
```

Opciones:
- `--dominio`: define el dominio para los correos generados (por defecto `example.com`).
- `--dry-run`: simula la importacion e imprime los primeros 10 correos generados.

Ejemplo:
```bash
python manage.py importar_personas C:\\ruta\\nombres.txt --dominio elementos.cl --dry-run
```

El correo se genera con la regla `nombres.apellidos@dominio`, sin acentos ni caracteres especiales. Si el email ya existe, se agrega un sufijo numerico (`2`, `3`, etc.). Si una linea solo tiene una palabra, se toma como nombre y se deja el apellido vacio.

## Pruebas automatizadas
```bash
python manage.py test
```
Incluye pruebas para autenticacion, calculos de planes/liquidaciones, API REST y modelos de finanzas.

## Settings por entorno
`DJANGO_ENV` define que modulo se emplea:
- `dev` (por defecto) -> `plataformaelemental.config.dev` (`DEBUG=True`, `ALLOWED_HOSTS=["*"]`).
- `prod` -> `plataformaelemental.config.prod`. Configura `DJANGO_ALLOWED_HOSTS` y `DJANGO_CSRF_TRUSTED_ORIGINS` separados por comas.

Tambien puedes forzar el modulo directamente con `DJANGO_SETTINGS_MODULE=plataformaelemental.config.<entorno>`.

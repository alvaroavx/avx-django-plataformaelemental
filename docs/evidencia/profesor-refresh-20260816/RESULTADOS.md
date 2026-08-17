# Refresh Profesor — evidencia local

Fecha: 2026-08-17
Entorno: desarrollo local, PostgreSQL configurado en `.env.dev`
Alcance: sin push, deploy, migraciones ni escrituras funcionales sobre datos

## Resultado funcional

- El contexto Profesor exige `organizacion=<id|todos>` y revalida los roles
  `PROFESOR` activos en cada request.
- El período usa mes/año o `periodo=todos`; las combinaciones ambiguas responden
  `404`.
- `organizacion=todos` y `periodo=todos` son de lectura. Sesiones y pagos
  históricos se paginan de 25 en 25.
- Alumnos y autocompletado parten de matrículas operativas, rol estudiante
  activo, organización y disciplina; no exigen asistencia histórica.
- Quitar asistentes y liberar/revertir una clase individual reutilizan servicios
  atómicos con auditoría y asignación docente efectiva.
- La corrección de pagos Profesor permanece bloqueada: el modelo actual no
  relaciona un contramovimiento con la `Transaction` original y, por tanto, no
  corrige inequívocamente el libro de caja.

## Verificación sobre desarrollo

Una consulta de solo lectura confirmó que la cuenta Profesor usada para revisar
multi-organización tiene dos organizaciones autorizadas. El contexto A expuso
una disciplina operativa, cinco sesiones, trece alumnos y un pago; el contexto B
está autorizado pero actualmente no tiene asignación docente operativa, por lo
que sus colecciones quedan vacías, no muestra acciones rápidas y sus formularios
mutantes directos responden `403`. La vista agregada reunió solo el alcance
operativo, omitió acciones mutantes y reportó `contexto_mutable=False`.

No se versionan nombres de usuario, IDs, cookies ni resultados nominales.

## Comandos y resultados

| Validación | Resultado |
| --- | --- |
| `python manage.py check` | OK, 0 incidencias |
| `python manage.py makemigrations --check --dry-run` | OK, `No changes detected` |
| `ruff check asistencias` | OK |
| `node --check scripts/e2e/profesor_operacion.js` | OK |
| `node --check asistencias/static/asistencias/js/profesor_contexto.js` | OK |
| `git diff --check` | OK |
| búsqueda de palabras visuales prohibidas en plantillas Profesor | sin coincidencias |

Antes de la instrucción final de no crear bases de pruebas se obtuvieron estos
resultados PostgreSQL aislados:

- 18/18 pruebas de Operación Profesor y multi-organización;
- 50 pruebas de dominio/jornada: 49 pasaron y una detectó un fixture inválido;
- el test corregido se reejecutó de forma individual y pasó.

No se volvió a crear una base `test_*` después de esa instrucción. Las suites
integrales de `asistencias`, `finanzas` y `personas`, y los casos añadidos tras
el último ajuste de permisos, quedan pendientes. Esta entrega no se declara
completamente validada por tests automatizados.

## Navegador y capturas

El runner reutilizable `scripts/e2e/profesor_operacion.js` quedó preparado para
390×844, tema claro/oscuro, contexto por mes o historial y capturas de Inicio,
Clases, detalle, Alumnos, Pagos y formularios. Se ejecuta en modo de solo lectura
sobre la base de desarrollo y no crea bases de datos.

Se completó el login Google real local con una cuenta Profesor y callback en
`http://127.0.0.1:8000/accounts/google/login/callback/`. El primer intento en el
puerto `8010` fue rechazado por Google por `redirect_uri_mismatch`; se corrigió
reiniciando el servidor de desarrollo en el puerto autorizado, sin cambiar OAuth
ni código.

Evidencia conservada:

- `claro/`: Inicio, hoja de contexto, Clases, detalle, Alumnos, Pagos y
  formularios a 390×844;
- `oscuro/`: el mismo recorrido en tema oscuro;
- `agregado/`: `organizacion=todos&periodo=todos`, sin acciones mutantes;
- `latin-rengo/`: organización autorizada sin asignación docente; listados sin
  datos cruzados y formularios mutantes con `403`.

Los tres resultados principales confirman que el selector ofrece Espacio
Elementos y Latin Rengo. Inicio, Clases, Alumnos y Pagos devolvieron `200`; las
superficies globales de Finanzas y Organizaciones devolvieron `403`, y Django
Admin redirigió a su login. Los objetivos de navegación midieron 64 px de alto y
las acciones frecuentes entre 47 y 71 px.

Capturas y JSON se sanitizaron: nombres/contactos aparecen difuminados y los
identificadores internos se sustituyen por marcadores. No se conservaron códigos
OAuth, cookies ni credenciales.

## Higiene

El intento cancelado de crear una base visual no alcanzó a crearla. Se verificó
el catálogo PostgreSQL: no quedaron `elemental_profesor_visual_20260816` ni
`test_plataforma_elemental_dev`. El clúster fallido de `/tmp` se eliminó.

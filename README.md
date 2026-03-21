# Plataforma Elemental

Plataforma administrativa construida en Django para operar academias, organizaciones y finanzas desde una sola base. Hoy integra operacion academica, CRM, cobros, documentos tributarios y movimientos de caja, manteniendo filtros globales de `periodo_mes`, `periodo_anio` y `organizacion` en toda la navegacion.

## Descripcion

La plataforma esta pensada para centralizar:
- registro y seguimiento de sesiones y asistencias
- administracion de personas, roles y organizaciones
- pagos academicos y consumo de clases
- documentos tributarios opcionales
- transacciones de caja y reportes operativos

Regla funcional importante:
- la plataforma debe poder usarse aunque no existan documentos tributarios
- `Payment`, `Transaction` y `DocumentoTributario` son entidades separadas

## Modulos principales

### `asistencias`
- sesiones
- registro de asistentes
- perfiles operativos de estudiantes y profesores
- estado financiero rapido del estudiante

### `personas`
- CRM transversal
- personas y roles por organizacion
- organizaciones
- vista administrativa consolidada por persona

### `finanzas`
- planes
- pagos de estudiantes
- documentos tributarios
- carga asistida XML-first para documentos tributarios
- transacciones de caja
- categorias y reportes

## Endpoints y rutas principales

### Acceso
- `/accounts/login/`
- `/admin/`
- `/`
- `/app/`

### Asistencias
- `/asistencias/`
- `/asistencias/sesiones/`
- `/asistencias/sesiones/<id>/`
- `/asistencias/asistencias/`
- `/asistencias/personas/<id>/`
- `/asistencias/estudiantes/`
- `/asistencias/profesores/`
- `/asistencias/disciplinas/`

### Personas
- `/personas/`
- `/personas/listado/`
- `/personas/nuevo/`
- `/personas/<id>/`
- `/personas/<id>/editar/`
- `/personas/organizaciones/`
- `/personas/organizaciones/nueva/`
- `/personas/organizaciones/<id>/`
- `/personas/organizaciones/<id>/editar/`

### Finanzas
- `/finanzas/`
- `/finanzas/pagos/`
- `/finanzas/planes/`
- `/finanzas/documentos-tributarios/`
- `/finanzas/documentos-tributarios/importar/`
- `/finanzas/transacciones/`
- `/finanzas/categorias/`
- `/finanzas/reportes/categorias/`
- `/finanzas/export/pagos.csv`
- `/finanzas/export/transacciones.csv`

## Arquitectura

### Stack
- Django 5
- Django REST Framework
- SQLite en desarrollo
- Bootstrap 5
- DataTables
- Tom Select

### Estructura del repo
- `plataformaelemental/`: configuracion del proyecto Django
- `database/`: modelos del dominio
- `asistencias/`: operacion academica
- `personas/`: CRM, roles y organizaciones
- `finanzas/`: pagos, documentos tributarios y caja
- `api/`: endpoints externos
- `data/`: cargas masivas y soporte de datos
- `docs/`: documentacion viva

### Reglas tecnicas transversales
- Los modelos del dominio se mantienen en `database/`.
- El codigo debe estar en espanol siempre que no complique artificialmente la comprension.
- Los filtros globales `periodo_mes`, `periodo_anio` y `organizacion` deben mantenerse en toda la navegacion.

## Comandos principales

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

### Levantar servidor de desarrollo
```bash
python manage.py runserver
```

### Ejecutar pruebas
```bash
python manage.py test
```

### Ejecutar pruebas por app
```bash
python manage.py test asistencias.tests
python manage.py test personas.tests
python manage.py test finanzas.tests
```

## Formas de usar la plataforma

### Flujo academico basico
1. Crear organizacion y disciplinas.
2. Registrar personas y roles.
3. Crear sesiones.
4. Registrar asistencias.
5. Revisar estado academico y financiero de cada estudiante.

### Flujo financiero academico basico
1. Crear planes si aplica.
2. Registrar pagos de estudiantes.
3. Consumir clases contra asistencias del mismo mes y anio.
4. Revisar saldo de clases y deudas.

### Flujo tributario basico
1. Registrar un documento tributario manualmente o usar carga asistida.
2. Revisar y confirmar los formularios precargados.
3. Asociar el documento a pagos o transacciones cuando corresponda.

## Carga asistida de documentos tributarios

Estado actual:
- XML-first
- soporte inicial para DTE XML clasico
- soporte inicial para boleta de honorarios XML
- PDF fallback basico
- revision humana antes del guardado

Reglas:
- si subes XML y PDF, prevalece XML
- si subes solo PDF, el parseo depende de que el PDF tenga texto seleccionable
- subir un archivo no guarda el registro final automaticamente

## Documentacion

Orden recomendado:
1. [AGENTS.md](/home/alvax/Code/platforms/avx-django-plataformaelemental/AGENTS.md)
2. [docs/INDICE.md](/home/alvax/Code/platforms/avx-django-plataformaelemental/docs/INDICE.md)
3. [docs/arquitectura/PLATAFORMA.md](/home/alvax/Code/platforms/avx-django-plataformaelemental/docs/arquitectura/PLATAFORMA.md)
4. [docs/proceso/DECISIONES.md](/home/alvax/Code/platforms/avx-django-plataformaelemental/docs/proceso/DECISIONES.md)
5. Documentos por app:
   - [docs/apps/ASISTENCIAS.md](/home/alvax/Code/platforms/avx-django-plataformaelemental/docs/apps/ASISTENCIAS.md)
   - [docs/apps/PERSONAS.md](/home/alvax/Code/platforms/avx-django-plataformaelemental/docs/apps/PERSONAS.md)
   - [docs/apps/FINANZAS.md](/home/alvax/Code/platforms/avx-django-plataformaelemental/docs/apps/FINANZAS.md)

## Observaciones

- `README.md` es el documento humano general del proyecto.
- `AGENTS.md` se mantiene en la raiz porque es una instruccion operativa especial para el agente.
- La documentacion viva del proyecto debe vivir dentro de `docs/`.

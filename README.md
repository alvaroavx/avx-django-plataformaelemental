# Plataforma Elemental

Plataforma administrativa construida en Django para operar academias, organizaciones y finanzas desde una sola base. Hoy el proyecto ya cubre tres frentes principales:
- operacion academica diaria en `asistencias`
- CRM y organizaciones en `personas`
- cobros, documentos y caja en `finanzas`

## Idea general
La plataforma esta pensada para trabajar con varias organizaciones y mantener siempre activos tres filtros globales:
- `periodo_mes`
- `periodo_anio`
- `organizacion`

Esos filtros deben arrastrarse por toda la navegacion.

## Apps principales

### `asistencias`
Operacion academica diaria:
- sesiones
- registro de asistentes
- perfiles operativos de estudiantes y profesores
- estado financiero rapido del estudiante

### `personas`
CRM transversal:
- listado de personas
- perfiles completos
- roles por organizacion
- administracion de organizaciones

### `finanzas`
Operacion financiera:
- planes
- pagos de estudiantes
- documentos tributarios
- carga asistida XML-first para documentos tributarios
- transacciones de caja
- categorias y reportes

## Criterio actual de finanzas
- `Pagos`: cobros academicos a estudiantes.
- `Documentos tributarios`: facturas, boletas de venta, boletas de honorarios y otros documentos fiscales.
- `Transacciones`: movimientos reales de dinero con su respaldo bancario o de caja.

La fuente tributaria objetivo es el SII. La plataforma debe servir para importar, revisar y asociar documentos, no para duplicar innecesariamente la informacion.

## Documentacion del repo
- [docs/README.md](/home/alvax/Code/platforms/avx-django-plataformaelemental/docs/README.md)
- [PLATAFORMA.md](/home/alvax/Code/platforms/avx-django-plataformaelemental/PLATAFORMA.md)
- [finanzas/FINANZAS.md](/home/alvax/Code/platforms/avx-django-plataformaelemental/finanzas/FINANZAS.md)
- [asistencias/ASISTENCIAS.md](/home/alvax/Code/platforms/avx-django-plataformaelemental/asistencias/ASISTENCIAS.md)
- [personas/PERSONAS.md](/home/alvax/Code/platforms/avx-django-plataformaelemental/personas/PERSONAS.md)

## Puesta en marcha
1. Activa el entorno virtual:
   ```bash
   source ./.venv/bin/activate
   ```
2. Instala dependencias:
   ```bash
   pip install -r requirements.txt
   ```
3. Aplica migraciones:
   ```bash
   python manage.py migrate
   ```
4. Crea un usuario admin si hace falta:
   ```bash
   python manage.py createsuperuser
   ```
5. Levanta el servidor:
   ```bash
   python manage.py runserver
   ```

## Rutas utiles
- Login: `http://127.0.0.1:8000/accounts/login/`
- Asistencias: `http://127.0.0.1:8000/asistencias/`
- Personas: `http://127.0.0.1:8000/personas/`
- Finanzas: `http://127.0.0.1:8000/finanzas/`
- Admin Django: `http://127.0.0.1:8000/admin/`

## Pruebas
```bash
python manage.py test
```

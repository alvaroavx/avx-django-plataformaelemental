# PLATAFORMA - Informe tecnico

## 1. Objetivo del informe
Este documento resume la revision tecnica aplicada sobre la plataforma Django de Espacio Elementos, incluyendo:
- Diagnostico del estado actual.
- Limpieza y mejoras implementadas.
- Funcionalidades vigentes por modulo.
- Deuda tecnica detectada y recomendaciones.

Fecha de revision: 2026-02-16

## 2. Resumen ejecutivo
La plataforma se encuentra operativa, con enfoque principal en administracion (backoffice y web app propia en `/app/`), con API base funcional y pruebas pasando.

Se aplicaron mejoras de mantenibilidad y consistencia:
- Limpieza de codigo no utilizado en vistas y formularios.
- Refactor de filtros globales (periodo y organizacion).
- Eliminacion de rutas/plantillas obsoletas.
- Homogeneizacion de filtros por organizacion en dashboard, asistencias, pagos y finanzas.
- Documentacion tecnica del estado del sistema.

Validacion tecnica posterior a cambios:
- `python manage.py check`: OK.
- `python manage.py test`: OK (13 tests).
- `python manage.py makemigrations --check --dry-run`: sin cambios pendientes.

## 3. Arquitectura actual
- Framework: Django 5 + Django REST Framework.
- DB actual: SQLite local.
- Arquitectura: monolito modular por apps.
- UI: Bootstrap 5 + DataTables (CDN) en vistas administrativas.
- Idioma/locale: es-CL, America/Santiago.
- Acceso web: autenticacion Django (`/accounts/login/`), area principal en `/app/`.

### Apps principales
- `cuentas`: personas, roles, relacion persona-rol.
- `organizaciones`: organizaciones base.
- `academia`: disciplinas, bloques, sesiones de clase.
- `asistencias`: registro de asistencia por sesion/persona.
- `cobros`: planes y pagos (modelo central de cobro).
- `finanzas`: movimientos de caja y liquidaciones docentes.
- `webapp`: vistas HTML de operacion administrativa.
- `api`: endpoints DRF.

## 4. Mejoras aplicadas en esta revision

### 4.1 Limpieza y mantenibilidad
- Se removio codigo muerto/no utilizado en `webapp/views.py`:
  - imports no usados.
  - filtros GET no utilizados por UI actual.
- Se eliminaron formularios no usados en `webapp/forms.py`:
  - `SesionRapidaForm`
  - `AsistenciaRapidaForm`
  - `AsistenciaSesionForm`
  - `PagoRapidoForm`
  - `PagoPlanForm`
- Se eliminaron artefactos de flujo antiguo:
  - vista/ruta de sesion rapida (`/app/sesiones/rapida/`)
  - plantilla `webapp/templates/webapp/sesion_rapida.html`
- Se dejaron `views.py` de apps no web con contenido minimo y explicito, para evitar ruido tecnico.

### 4.2 Refactor funcional en vistas web
- Se agregaron helpers en `webapp/views.py`:
  - `_periodo(request)` para rango mensual consistente.
  - `_organizacion_desde_request(request)` para resolver organizacion seleccionada.
  - `_nav_context(request)` para contexto comun de usuario/roles.
- Se incorporaron docstrings breves en vistas clave.

### 4.3 Filtro global de periodo/organizacion
- Barra superior global en `base_app` con:
  - selector de mes
  - selector de anio
  - selector de organizacion (incluye "Todas")
- Propagacion del filtro en links de navegacion.
- Preservacion de query params al cambiar periodo.

### 4.4 Filtro por organizacion aplicado en modulos operativos
- Dashboard (`/app/`): recalcula metricas por organizacion seleccionada.
- Asistencias (`/app/asistencias/`): lista sesiones por periodo + organizacion.
- Pagos (`/app/pagos/`): lista pagos filtrada por organizacion.
- Finanzas unificadas (`/app/finanzas/unificadas/`): pagos, liquidaciones y movimientos filtrados por organizacion.
- Sesiones calendario (`/app/sesiones/`): filtro mensual con opcion por organizacion.

### 4.5 Ajustes UI y experiencia de operacion
- En `asistencias_list`:
  - secciones de alta rapida en fila superior completa.
  - tabla de sesiones a ancho completo.
  - columna de organizacion integrada como badge junto a disciplina.
  - columna de asistentes con badges enlazados a perfil persona.
  - botones de accion con icono y tooltip.
- En detalles:
  - acciones rapidas para agregar asistentes y cambiar estado de sesion.
  - ocultamiento selectivo de barra de periodo en vistas donde no aporta (`/app/sesiones/{id}`, `/app/estudiantes`, `/app/organizaciones`).

## 5. Funcionalidades actuales del sistema

### 5.1 Autenticacion y acceso
- Login en `/accounts/login/`.
- Redireccion principal a `/app/`.
- Navegacion principal protegida para usuarios autenticados.

### 5.2 Panel administrador (`/app/`)
- Indicadores del periodo:
  - asistencias del mes
  - boletas pendientes
  - sesiones recientes
  - pagos y liquidaciones recientes
- Filtro global por mes/anio/organizacion.

### 5.3 Sesiones y asistencias
- Calendario mensual de sesiones (`/app/sesiones/`).
- Detalle de sesion (`/app/sesiones/{id}/`) con:
  - estado
  - asistentes
  - pagos/no pagos
  - enlaces a perfiles.
- Operacion masiva en `/app/asistencias/`:
  - crear sesion minima
  - crear persona rapida
  - agregar asistentes en bloque
  - cambiar estado de sesion.

### 5.4 Personas
- Perfil de persona (`/app/personas/{id}/`) con enfoque estudiante/profesor.
- Listados:
  - estudiantes (`/app/estudiantes/`)
  - profesores (`/app/profesores/`)
- Datos asociados:
  - asistencias
  - pagos
  - sesiones realizadas (perfil profesor).

### 5.5 Pagos y banco de clases
- Modelo de pago unificado (plan/clase/otro).
- Pagos por plan generan banco de clases con vigencia por duracion del plan.
- Consumo de clases por asistencia.
- Registro de pagos desde perfil de persona y visualizacion en listado general.

### 5.6 Finanzas
- Vista unificada (`/app/finanzas/unificadas/`) con:
  - pagos
  - liquidaciones
  - movimientos de caja
- Filtro por periodo y organizacion.

### 5.7 Organizaciones
- Vista de organizaciones (`/app/organizaciones/`) en formato tarjetas.

### 5.8 API
- Endpoints base DRF operativos (health y entidades clave del MVP).
- Autenticacion habilitada por sesion y token DRF.

## 6. Calidad del codigo y pruebas

Estado al cierre:
- Checks Django sin errores.
- Suite de pruebas existente en verde (13 tests).
- Migraciones sincronizadas (sin cambios pendientes).

Observaciones:
- La cobertura automatica no esta reportada formalmente.
- Existen validaciones de negocio complejas que todavia descansan en logica de vista y modelo sin capa de servicios dedicada.

## 7. Deuda tecnica detectada

1. Repositorio incluye artefactos generados (`__pycache__`, archivos `.pyc`, y otros binarios) en el historial.
2. Hay acoplamiento alto entre vistas y reglas de negocio (calculos de pagos/asistencias en view layer).
3. Parte de textos UI/documentacion historica no reflejan al 100% el flujo consolidado mas reciente.
4. Falta estandar de lint/format formal (ejemplo: `ruff` + `black` + `isort`) en pipeline.
5. No hay capa de permisos granular por rol funcional en todas las vistas (hoy el foco esta en admin).

## 8. Recomendaciones priorizadas

1. Crear y aplicar `.gitignore` estricto para excluir virtualenv, caches, binarios y DB local.
2. Introducir capa de servicios de dominio para pagos/asistencias (separar logica de views).
3. Agregar lint/format y CI basico (check + test + lint) para control de calidad continuo.
4. Extender pruebas a flujos criticos:
   - consumo de banco de clases
   - deuda por periodo
   - filtros por organizacion en todas las vistas clave.
5. Consolidar documentacion operativa final en README para reflejar solo rutas/flujo vigentes.

## 9. Conclusiones
La plataforma queda en un estado funcional y mas mantenible que al inicio de la revision:
- Menos codigo muerto.
- Filtros globales consistentes.
- Vistas operativas mas limpias.
- Diagnostico tecnico formalizado.

El siguiente salto de madurez recomendado es fortalecer control de calidad automatizado (lint/CI) y mover reglas de negocio criticas a una capa de servicios dedicada.

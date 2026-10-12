# PLATAFORMA

Fecha de actualizacion: 2026-10-12

## Proposito
Este documento es la fotografia ejecutiva de Plataforma Elemental.

Debe responder rapido:
- que es el sistema
- que apps existen
- que responsabilidad tiene cada app
- donde vive el detalle especializado

No debe duplicar reglas largas de seguridad, deploy, finanzas, API ni navegacion. Para detalles, enlaza a los documentos duenios.

## Resumen ejecutivo
La plataforma opera como un monolito Django modular.

Apps funcionales visibles:
- `asistencias`: operacion academica diaria.
- `personas`: identidad, CRM, roles y organizaciones.
- `finanzas`: cobranza operacional, transacciones y reportes.
- `api`: endpoints minimos de salud, estado, version y usuario autenticado.

Componentes activos de soporte:
- `auditoria`: trazabilidad parcial y best-effort de mutaciones sensibles.

Componentes de soporte:
- `plataformaelemental`: configuracion del proyecto.

## Arquitectura vigente
- Framework: Django 5.2.9 sobre Python 3.12.
- API: Django REST Framework.
- Base de datos: PostgreSQL, unico motor configurado en `plataformaelemental/config/dev.py` y `plataformaelemental/config/prod.py`.
- UI: Bootstrap 5, DataTables y Tom Select via CDN.
- Zona horaria: `America/Santiago`.
- Deploy: GitHub Actions + SSH + `systemd` + `gunicorn`.
- Integración financiera inicial: exportación JSON versionada Elemental → Cuadratura (`elemental-cuadratura-v1`, `finanzas/services/cuadratura_v1.py`), descargada manualmente desde `Preparar mes`. Lo que existe: archivo JSON con `batch_id` determinista por organización, período y operaciones incluidas. Planificado / no implementado: transporte por API y reglas de idempotencia del lado receptor; cuando exista, debe conservar el mismo contrato. Detalle en [docs/apps/FINANZAS.md](../apps/FINANZAS.md).

Detalle operativo:
- Deploy y CI/CD: [docs/operacion/DEPLOY.md](../operacion/DEPLOY.md)
- Seguridad de produccion: [docs/operacion/SEGURIDAD_PRODUCCION.md](../operacion/SEGURIDAD_PRODUCCION.md)
- Auditoria SQLite/PostgreSQL: [docs/operacion/AUDITORIA_SQLITE_POSTGRESQL.md](../operacion/AUDITORIA_SQLITE_POSTGRESQL.md)
- Modelo de datos: [docs/arquitectura/MODELO_DATOS.md](MODELO_DATOS.md)
- Deuda tecnica activa: [docs/arquitectura/DEUDA_TECNICA.md](DEUDA_TECNICA.md)
- Roadmap de dominios: [docs/arquitectura/ROADMAP_DOMINIOS.md](ROADMAP_DOMINIOS.md)
- Testing: [docs/proceso/TESTING.md](../proceso/TESTING.md)
- Observabilidad: [docs/arquitectura/OBSERVABILIDAD.md](OBSERVABILIDAD.md)
- Permisos y roles: [docs/arquitectura/PERMISOS_Y_ROLES.md](PERMISOS_Y_ROLES.md)

## Fronteras de dominio
- `personas` define identidad: `Persona`, `Organizacion`, `Rol`, `PersonaRol` y `SolicitudAcceso`.
- `asistencias` define operacion de clases: `Disciplina`, `BloqueHorario`, `SesionClase`, `Asistencia`, `LiberacionSesion` y `ClaseLiberada`.
- `asistencias` mantiene las asignaciones profesor–disciplina y alumno–disciplina para la operación administrativa; el portal dedicado `/profesor/` fue retirado. El rol y perfil de profesor siguen vigentes.
- `finanzas` contiene cobranza operacional, planes, pagos, lotes, deuda, saldo,
  imputación contra asistencias, transacciones de caja, categorías, reportes y
  la exportación mensual hacia Cuadratura.
- `plataformaelemental` aloja configuración, Panel transversal (`/`), contexto
  global de filtros y navegación.
- Cuadratura es dueña de documentos fiscales, conciliación y cierres contables.
- `api` expone solo superficie minima operativa en v1.0; no expone datos de personas, asistencias ni finanzas.
- `auditoria` registra eventos seleccionados, pero no es una bitacora completa ni bloquea una operacion si falla el log.
- Las apps legacy `database` y `monitor` fueron retiradas; las migraciones vigentes de `personas`, `asistencias` y `finanzas` crean sus tablas directamente.

Detalle por app:
- Asistencias: [docs/apps/ASISTENCIAS.md](../apps/ASISTENCIAS.md)
- Personas: [docs/apps/PERSONAS.md](../apps/PERSONAS.md)
- Finanzas: [docs/apps/FINANZAS.md](../apps/FINANZAS.md)
- API: [docs/apps/API.md](../apps/API.md)

## Reglas transversales minimas
- Los modelos viven en su app duena.
- Ninguna app debe importar helpers desde `views.py` de otra app.
- La logica compartida de filtros globales, periodo, organizacion activa y navegacion vive en un modulo neutral.
- Las views coordinan request/response; no deben concentrar reglas de negocio complejas.
- Los templates no calculan deuda, saldo, imputacion ni estados financieros.
- Los selectors contienen consultas y agregaciones sin efectos secundarios.
- Los services contienen reglas de negocio y pueden coordinar modelos de varias apps cuando representen un caso de uso claro.
- Los signals solo deben usarse para automatismos simples y documentados; si una regla es critica, debe existir tambien como servicio explicito testeable.

Detalle de navegacion y contexto global:
- [docs/arquitectura/NAVEGACION_Y_CONTEXTO.md](NAVEGACION_Y_CONTEXTO.md)

## Estado financiero conceptual
`Payment` y `Transaction` son entidades separadas. Los
pagos confirmados desde los flujos vigentes crean y enlazan una `Transaction`
uno-a-uno; los pagos históricos anteriores pueden conservar vínculo nulo.

Regla ejecutiva:
- Un pago operacional responde si una persona pago clases.
- Una transaccion responde que movimiento de dinero existio.
- Elemental no almacena ni administra respaldos fiscales; esa capacidad pertenece a Cuadratura.

Detalle financiero:
- [docs/apps/FINANZAS.md](../apps/FINANZAS.md)

## Seguridad y acceso
La politica detallada de sesiones, cookies, HTTPS, headers, API key y throttling no vive aqui.

Documentos duenios:
- Seguridad produccion: [docs/operacion/SEGURIDAD_PRODUCCION.md](../operacion/SEGURIDAD_PRODUCCION.md)
- API auth/throttling: [docs/apps/API.md](../apps/API.md)
- Autenticacion Google y solicitudes de acceso: [docs/adr/0001-autenticacion-google-y-solicitudes-acceso.md](../adr/0001-autenticacion-google-y-solicitudes-acceso.md)

Regla de frontera:
- Google autentica una identidad, pero no concede organizaciones, roles ni permisos. La autorizacion sigue viviendo en `PersonaRol` y permisos Django.
- La aprobacion de nuevos accesos queda detras de security gates hasta corregir y probar aislamiento multi-organizacion.

## Deploy
Dominio publico vigente: `apps.espacioelementos.cl`.

El detalle de GitHub Actions, SSH, variables de entorno, backup PostgreSQL, `systemd` y rollback vive en:
- [docs/operacion/DEPLOY.md](../operacion/DEPLOY.md)

## Validacion
La fuente de verdad ejecutable es el codigo con sus tests vigentes.

Comando principal esperado:

```bash
python manage.py test
```

Al 2026-10-12 el inventario contiene 394 metodos `test_*` en `HEAD` (400 en el
arbol de trabajo con cambios en curso). Los workflows de pull request y de
deploy usan Python 3.12 y PostgreSQL 16, pero solo ejecutan
`python manage.py test asistencias finanzas personas`; `api`, `auditoria` y
`plataformaelemental` quedan fuera de CI. El resultado de una suite no confirma
por si solo el estado del servidor ni de los datos productivos.

Historico: en el corte 2026-08-09 la suite local completa pasó 404 tests, con 12
omitidos, contra PostgreSQL local. El resultado vigente se registra en
[docs/ESTADO_ACTUAL.md](../ESTADO_ACTUAL.md).

Fotografia verificable y riesgos activos:
- [docs/ESTADO_ACTUAL.md](../ESTADO_ACTUAL.md)

## Observaciones tecnicas
- Sigue siendo importante reducir logica de negocio en views cuando aparezcan cambios funcionales.
- La documentacion viva del repo vive en `docs/`, con indice central y documentos por app.
- Si una decision cambia comportamiento, modelo, operacion o responsabilidad, debe actualizarse la documentacion en el mismo cambio.

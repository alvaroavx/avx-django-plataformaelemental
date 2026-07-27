# PLATAFORMA

Fecha de actualizacion: 2026-07-26

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
- `finanzas`: cobranza operacional, documentos tributarios, transacciones y reportes.
- `api`: endpoints minimos de salud, estado, version y usuario autenticado.
- `monitor`: archivado/desactivado del producto principal; se conserva temporalmente por migraciones y posible data historica.

Componentes de soporte:
- `plataformaelemental`: configuracion del proyecto.

## Arquitectura vigente
- Framework: Django 5.
- API: Django REST Framework.
- Base de datos: PostgreSQL por entorno en `plataformaelemental/config/dev.py` y `plataformaelemental/config/prod.py`.
- UI: Bootstrap 5, DataTables y Tom Select via CDN.
- Zona horaria: `America/Santiago`.
- Deploy: GitHub Actions + SSH + `systemd` + `gunicorn`.

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
- `personas` define identidad: `Persona`, `Organizacion`, `Rol`, `PersonaRol`.
- `asistencias` define operacion de clases: `Disciplina`, `BloqueHorario`, `SesionClase`, `Asistencia`.
- `finanzas` contiene dos subdominios internos:
  - cobranza operacional: planes, pagos, deuda, saldo e imputacion contra asistencias.
  - finanzas/contabilidad: documentos tributarios, transacciones, categorias y reportes.
- `api` expone solo superficie minima operativa en v1.0; no expone datos de personas, asistencias ni finanzas.
- `monitor` no define core operacional y no forma parte de la navegacion/rutas activas de `Elemental Apps`.
- La app legacy `database` fue retirada; las migraciones vigentes de `personas`, `asistencias` y `finanzas` crean sus tablas directamente.

Detalle por app:
- Asistencias: [docs/apps/ASISTENCIAS.md](../apps/ASISTENCIAS.md)
- Personas: [docs/apps/PERSONAS.md](../apps/PERSONAS.md)
- Finanzas: [docs/apps/FINANZAS.md](../apps/FINANZAS.md)
- API: [docs/apps/API.md](../apps/API.md)
- Monitor: [docs/apps/MONITOR.md](../apps/MONITOR.md)

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
`Payment`, `Transaction` y `DocumentoTributario` son entidades separadas.

Regla ejecutiva:
- Un pago operacional responde si una persona pago clases.
- Una transaccion responde que movimiento de dinero existio.
- Un documento tributario responde que respaldo fiscal existe.
- Pueden asociarse, pero no deben colapsarse en una sola entidad.

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

## Observaciones tecnicas
- Sigue siendo importante reducir logica de negocio en views cuando aparezcan cambios funcionales.
- La documentacion viva del repo vive en `docs/`, con indice central y documentos por app.
- Si una decision cambia comportamiento, modelo, operacion o responsabilidad, debe actualizarse la documentacion en el mismo cambio.

# Validación del patch de release manual

Fecha: 2026-08-10

## Alcance

Validación local y estática del workflow futuro, los scripts de despliegue y el
runbook manual de Operación Profesor. No se accedió a producción, no se ejecutó
ninguna migración, no se inició ningún servicio, no se creó otra base de datos y
no se hizo push.

Artefacto de release definido:

- tag: `release/operacion-profesor-20260810.1`;
- commit funcional padre: `c47ce8225b3221b28a00baf9a4d2909e154c3b30`;
- base anterior: `d4a4e482c67a115562918bcc2f3f71e6cdb2b0c9`;
- el SHA final se obtiene del tag anotado después de crear el segundo commit y
  forma parte de la entrega Git;
- el hash real de producción permanece por registrar durante el preflight.

## Resultados

| Validación | Resultado |
| --- | --- |
| `bash -n scripts/deploy.sh scripts/release_operacion_profesor.sh` | OK |
| ayuda del coordinador manual sin entorno productivo | OK |
| parseo de `.github/workflows/deploy.yml` con `js-yaml` | OK |
| push a `main`: job CI presente y job deploy condicionado a dispatch | OK |
| dispatch: confirmación, environment y bloqueo `MANUAL_RELEASE_ONLY` | OK |
| script: solo `asistencias.0004`, `finanzas.0012` y `migrate --check` | OK |
| `PGOPTIONS`: `lock_timeout=5s` fijado después del EnvironmentFile | OK |
| `.venv/bin/ruff check .` | OK |
| `manage.py check` con `.env.dev` | OK, 0 issues |
| `npm run test:docs-links` | OK, 91 enlaces locales |
| `npm run test:mermaid` | OK, 12 diagramas |
| `git diff --check` | OK |

`actionlint` no está instalado en el entorno. La sintaxis YAML se validó con el
parser ya instalado y se comprobaron programáticamente los gates estructurales
requeridos. El primer intento de Mermaid fue bloqueado por el sandbox de Chrome;
la repetición con el permiso local previsto por el proyecto evaluó los 12
diagramas correctamente.

## Límites

- No se ejecutó GitHub Actions: la aprobación efectiva requiere configurar
  revisores obligatorios en el environment `production` del repositorio.
- La comprobación `verify-release` se ejecuta después de crear el segundo commit
  y su tag anotado, porque antes de ese momento el SHA final todavía no existe.
- No se ejecutó el coordinador contra PostgreSQL porque su propósito es la
  ventana manual y la solicitud prohíbe tocar producción; la base local no era
  necesaria para validar este patch.
- No se validó un hash productivo real. El runbook falla si infraestructura no lo
  registra antes del checkout.

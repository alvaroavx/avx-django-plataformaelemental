# Artefactos de trabajo

Fecha de actualización: 2026-08-16

## Propósito

Este documento registra las herramientas y evidencias creadas durante análisis,
desarrollo y validación para que una tarea futura pueda reutilizarlas antes de
crear otra solución ad hoc.

Un artefacto útil no se elimina al terminar la tarea. Se conserva en una ruta
estable, se documenta y, si queda obsoleto, se marca como reemplazado indicando
su sucesor.

## Qué se conserva

| Tipo | Ubicación | Ejemplos |
| --- | --- | --- |
| Herramienta ejecutable reutilizable | `scripts/<área>/` | validadores, runners E2E, diagnósticos parametrizados |
| Evidencia de una ejecución | `docs/evidencia/<objetivo>-<fecha>/` | capturas, resultados JSON, logs sanitizados |
| Fixture sintética estable | app dueña o `data/fixtures/` | entradas mínimas referenciadas por tests o importadores |
| Decisión o receta | `docs/` | propósito, precondiciones, comandos, límites y riesgos |

No son artefactos durables: entornos virtuales, `node_modules`, cachés, sockets,
procesos, perfiles temporales de navegador ni archivos compilados. Tampoco se
versionan secretos, datos personales reales, respaldos o dumps. En esos casos se
conserva una receta reproducible, una herramienta parametrizada o evidencia
sanitizada.

## Flujo obligatorio antes de crear uno

1. Leer este inventario.
2. Buscar por propósito, no solo por nombre:

   ```bash
   rg --files scripts docs/evidencia data
   rg -n "palabra del flujo" scripts docs/evidencia docs/proceso
   ```

3. Evaluar si un artefacto existente acepta un parámetro o modo nuevo.
4. Preferir generalizarlo con compatibilidad hacia atrás.
5. Si hace falta uno nuevo, ubicarlo según la tabla, eliminar secretos y añadirlo
   al inventario en el mismo cambio.
6. Registrar el comando ejecutado y el resultado en la evidencia de la tarea.

## Trabajo con subagentes

Antes de delegar, el agente principal revisa este documento y comunica en la
tarea las rutas aplicables. Un subagente debe inspeccionarlas antes de crear
scripts o fixtures nuevos. Al recibir su trabajo, el agente principal revisa si
el artefacto puede integrarse o generalizarse y actualiza este inventario.

Los subagentes no deben escribir simultáneamente sobre el mismo artefacto. Si se
necesitan variantes paralelas, se conservan por separado durante la tarea y se
consolidan en una versión canónica antes del cierre, manteniendo la evidencia que
explique qué variante se ejecutó.

## Inventario vigente

### Validación documental

- `scripts/validate_mermaid.py`: descubre bloques Mermaid en Markdown, los
  renderiza con Mermaid CLI y reporta errores de sintaxis.
- `scripts/mermaid-puppeteer-config.json`: configuración de Chrome usada por el
  validador Mermaid.
- `scripts/validate_markdown_links.py`: valida que los destinos locales de los
  enlaces Markdown existan; ignora enlaces externos y anclas internas.
- Uso posible: validar documentación completa después de modificar diagramas.

Comandos:

```bash
npm run test:docs-links
npm run test:mermaid
```

### Operación Profesor E2E

- `scripts/e2e/profesor_operacion.js`: sucesor parametrizado de los recorridos
  creados para el sprint Operación Profesor. Ejecuta navegación móvil, captura
  pantallas, comprueba gates y genera `resultado.json`.
- Es de solo lectura por defecto. `ELEMENTAL_E2E_MUTACIONES=1` habilita creación
  de alumno, asistencia, pago y sesión liberada sobre datos sintéticos.
- Puede autenticarse con usuario/clave no versionados o con una sesión Django
  efímera mediante `ELEMENTAL_E2E_SESSION_COOKIE`. Esta última nunca se escribe
  en el resultado ni debe persistirse fuera del proceso.
- También puede reutilizar un perfil temporal autenticado manualmente mediante
  `ELEMENTAL_E2E_USER_DATA_DIR`. El perfil vive fuera del repositorio y debe
  eliminarse al terminar; ni su ruta ni sus cookies quedan en `resultado.json`.
- Para sesiones que no deben cerrarse, `ELEMENTAL_E2E_BROWSER_URL` conecta el
  recorrido a un Chrome abierto con depuración local. El runner abre y cierra
  solo su pestaña, se desconecta al finalizar y no extrae ni serializa cookies.
- Exige `ELEMENTAL_E2E_ORGANIZACION_ID`: acepta un ID explícito o `todos`; todo
  acceso Profesor conserva el valor y permite reutilizar el runner en
  escenarios multi-organización sin fallback implícito.
- `ELEMENTAL_E2E_PERIODO_MES` y `ELEMENTAL_E2E_PERIODO_ANIO` fijan un mes;
  `ELEMENTAL_E2E_PERIODO_TODOS=1` usa el historial paginado y es mutuamente
  excluyente. `ELEMENTAL_E2E_THEME=light|dark` persiste el tema antes de cargar
  la primera página. El recorrido de lectura captura Inicio, Clases, detalle,
  Alumnos, Pagos, la hoja de contexto y formularios cuando el contexto es
  mutable.
- `ELEMENTAL_E2E_CAPTURAS=0` conserva solo JSON sanitizado cuando las pantallas
  contienen datos de desarrollo. `ELEMENTAL_E2E_PAGO_MASIVO=0` omite la selección
  masiva y `ELEMENTAL_E2E_SOLO_PAGO_PERSONA_ID` ejecuta un pago dirigido a una
  persona ya autorizada por el formulario.
- Las capturas se sanitizan por defecto difuminando nombres y datos de contacto.
  `ELEMENTAL_E2E_SANITIZAR_CAPTURAS=0` solo debe usarse para una inspección local
  que no vaya a persistirse como evidencia.
- `ELEMENTAL_E2E_INSPECCIONAR_FORMULARIO=/ruta/` reutiliza el mismo login y
  navegador para inventariar valores de controles, reemplazando el diagnóstico
  puntual de formularios.
- Evidencia original: `docs/evidencia/profesor-20260809/`.
- Puede reutilizarse para regresiones móviles, autorización directa y nuevos
  flujos del profesor. No valida OAuth Google real porque usa el acceso local del
  ambiente de prueba.

Variables requeridas:

```bash
export ELEMENTAL_E2E_USERNAME='usuario-sintetico'
export ELEMENTAL_E2E_PASSWORD='clave-no-versionada'
npm run test:e2e:profesor
```

Variables opcionales: `ELEMENTAL_E2E_BASE_URL`, `ELEMENTAL_E2E_OUTPUT_DIR`,
`ELEMENTAL_E2E_RUN_ID`, `ELEMENTAL_E2E_CHROME`,
`ELEMENTAL_E2E_BUSQUEDA_ALUMNO`, `ELEMENTAL_E2E_MONTO`,
`ELEMENTAL_E2E_MUTACIONES`, `ELEMENTAL_E2E_INSPECCIONAR_FORMULARIO`,
`ELEMENTAL_E2E_SESSION_COOKIE`, `ELEMENTAL_E2E_SESSION_COOKIE_NAME`,
`ELEMENTAL_E2E_PAGO_MASIVO`, `ELEMENTAL_E2E_CAPTURAS` y
`ELEMENTAL_E2E_SOLO_PAGO_PERSONA_ID`, `ELEMENTAL_E2E_PERIODO_MES`,
`ELEMENTAL_E2E_PERIODO_ANIO`, `ELEMENTAL_E2E_PERIODO_TODOS`,
`ELEMENTAL_E2E_THEME`, `ELEMENTAL_E2E_USER_DATA_DIR`,
`ELEMENTAL_E2E_BROWSER_URL` y `ELEMENTAL_E2E_SANITIZAR_CAPTURAS`.

### Refresh visual Profesor 2026-08-16

- `docs/evidencia/profesor-refresh-20260816/`: contrato final, matriz de
  contraste, verificaciones de solo lectura y capturas 390×844 cuando el login
  manual local está disponible.
- Reutiliza `scripts/e2e/profesor_operacion.js`; no se creó un segundo runner ni
  un fixture alternativo. Por instrucción del entorno, no crea bases temporales:
  navega la base de desarrollo configurada y deja las mutaciones deshabilitadas.
- No conserva contraseñas, cookies, perfiles de Chrome ni datos personales en
  el resultado. El perfil local de navegador se elimina al cerrar la revisión.

### Ronda Profesor sobre desarrollo 2026-08-16

- `docs/evidencia/profesor-flujo-20260816/`: resultados sanitizados de dos
  profesores, dos organizaciones y viewport móvil sobre la base de desarrollo
  configurada; no se creó otra base.
- Conserva los recorridos de sesiones, alumnos, asistencias, pagos y autorización,
  además de una matriz de capacidades no disponibles para Profesor puro.
- No conserva capturas, cookies ni el perfil temporal de Chrome. El flujo Google
  manual no completó callback y se registra como no verificado.
- Reutilizar esta evidencia como línea base funcional, no como prueba OAuth ni
  como autorización para ejecutar mutaciones en producción.

### Evidencia Operación Profesor 2026-08-09

- Ocho capturas móviles y `RESULTADOS.md`: evidencia visual y resumen del flujo.
- `logs/suite-completa-ok.log`: resultado final de 404 tests.
- `logs/tests-focalizados-ok.log`: resultado focal previo al cierre.
- `logs/suite-inicial-fallos.log`: diagnóstico que permitió identificar tres
  regresiones antes de obtener la suite verde. Se conserva como evidencia
  histórica; no describe el estado final.

### Revisión de artefactos y migraciones 2026-08-10

- `docs/evidencia/revision-artefactos-migraciones-20260810/`: resultados de la
  validación de los artefactos nuevos y SQL generado por `sqlmigrate` para
  `asistencias.0004` y `finanzas.0012`.
- Puede reutilizarse para preparar el checklist de despliegue, estimar locks y
  contrastar una futura versión de esas migraciones.

### Ensayo de migraciones Operación Profesor

- `scripts/migraciones/ensayar_finanzas_0012.py`: runner seguro y parametrizado
  para una copia PostgreSQL no productiva. Registra preflight, tamaños,
  migraciones, duración, cotas por operación, locks, escritura con rollback e
  invariantes posteriores en JSON sanitizado.
- Exige la confirmación literal `COPIA_NO_PRODUCTIVA`, espacio disponible y el
  estado `finanzas.0011`; rechaza motores no PostgreSQL, `DJANGO_ENV` productivo,
  nombres con `prod` y una base donde `0012` ya esté aplicada.
- `asistencias/management/commands/reportar_relaciones_historicas.py`: reporte
  reutilizable de conteos para historia y transición operativa. Identifica
  asignaciones futuras pendientes y matrículas recientes para revisión sin
  activarlas. `--fallar-si-inseguro` lo convierte en gate; el detalle nominal
  opcional debe guardarse fuera del repo en almacenamiento protegido.
- `asistencias/management/commands/activar_relaciones_operativas.py`: activación
  administrativa por IDs para ventanas con el sitio en mantenimiento. Sin la
  confirmación literal solo previsualiza; al confirmar reutiliza los servicios
  atómicos, valida el actor por organización y audita cada relación.
- Evidencia: `docs/evidencia/migraciones-operacion-profesor-20260810/`; incluye
  SQL, medición sintética, reporte, resultado de backup/restauración y el estado
  bloqueado del ensayo QA representativo.
- Runbook: `docs/operacion/MIGRACIONES_OPERACION_PROFESOR.md`.
- Los clústeres, bases restauradas y dumps en `/tmp` no son durables,
  versionables ni respaldos operativos. Reutilizar primero los dos artefactos
  parametrizados y eliminarlos tras aprobar la evidencia conforme al runbook;
  no copiar dumps como fixtures.

### Release manual de Operación Profesor

- `scripts/release_operacion_profesor.sh`: coordinador por etapas para el tag
  inmutable `release/operacion-profesor-20260810.1`. Verifica que el tag apunte
  exactamente a `HEAD`, que el padre sea el commit funcional y que el worktree
  esté limpio; instala dependencias sin migrar, guarda cada
  `showmigrations --plan`, aplica
  solo `asistencias.0004`, genera el reporte, y aplica `finanzas.0012` únicamente
  después de gates de reporte y activación administrativa.
- El script no crea backups, no activa relaciones, no inicia servicios y no
  ejecuta `migrate` completo. Esas decisiones permanecen visibles en
  `docs/operacion/MIGRACIONES_OPERACION_PROFESOR.md`.
- Vive y se ejecuta dentro del checkout versionado del tag; no admite una ruta de
  aplicación externa ni depende de archivos copiados manualmente. Los reportes
  nominales deben ir a `RELEASE_OPS_DIR` protegido, nunca al repositorio.
- No generalizar este script a releases futuros cambiando silenciosamente el
  hash: crear una variante o convertirlo en herramienta genérica solo después de
  definir un manifiesto versionado de etapas y gates equivalentes.
- `docs/evidencia/release-manual-operacion-profesor-20260810/RESULTADOS.md`:
  evidencia sanitizada de sintaxis Bash/YAML, gates estructurales, documentación,
  lint y check local. No contiene secretos, datos de producción ni dumps.

### Gate CI y smoke de producción

- `scripts/validar_gate_ci.py`: valida la estructura de
  `.github/workflows/deploy.yml`: trigger de `main`, PostgreSQL efímero, comandos
  completos, `needs: test`, ausencia de `always()`, `success()` explícito y smoke
  posterior al deploy. Se ejecuta dentro de los workflows de test y deploy.
- `scripts/smoke_produccion.sh`: smoke de solo lectura posterior al reinicio.
  Comprueba los códigos HTTP públicos y delega la autorización Profesor al
  comando Django. Lee parámetros desde el `DEPLOY_ENV_FILE` local del servidor;
  no recibe contraseñas ni IDs productivos desde el repositorio.
- `asistencias/management/commands/verificar_smoke_profesor.py`: usa una cuenta
  existente y dos organizaciones parametrizadas para verificar `200` autorizado
  y `404` ajeno. Sustituye temporalmente el backend de sesión por cookies
  firmadas para no dejar una fila de sesión en producción.
- Uso posible: mantener estos tres artefactos como gate común para futuros
  releases. El smoke no sustituye el E2E Google ni una prueba de restauración.
- Evidencia sanitizada de esta revisión:
  `docs/evidencia/gate-ci-deploy-20260811/RESULTADOS.md`.

### Poblador mensual operativo

- `asistencias/management/commands/poblar_mes_pruebas.py`: genera un mes
  sintético para Lyra, LatinRengo y una disciplina circense parametrizable.
- Tiene preview por defecto, confirmación `--aplicar`, transacción atómica,
  protección `DEBUG=True`, marcador de datos de prueba e idempotencia.
- Reutiliza personas y organizaciones por ID; no guarda correos ni crea alumnos.
- `docs/evidencia/poblado-agosto-20260810/`: preview, aplicación, segunda
  ejecución y verificación del primer escenario cargado.
- Puede reutilizarse para poblar otro mes cambiando `--anio` y `--mes`, siempre
  sobre una base no productiva con suficientes estudiantes activos.

### Regresión de aprobación de solicitudes 2026-08-10

- `docs/evidencia/correccion-solicitudes-20260810/`: reproducción del GET 404
  desde el buscador, segundo hallazgo de búsqueda por nombre sin tilde y resultado
  final de la clase focalizada.
- El caso automatizado quedó en
  `personas.tests.ResolucionSolicitudAccesoTests.test_busqueda_desde_error_vuelve_al_detalle_y_no_combina_user_con_persona`.
- Puede reutilizarse para revisar cambios futuros en búsqueda, validación y rutas
  POST-only de solicitudes de acceso.

### Componentes reutilizables de búsqueda de personas

- `personas/search.py`: filtro ORM canónico para consultas por fragmentos sin
  sensibilidad a tildes. Recibe querysets ya autorizados y sirve a Personas,
  Asistencias y Finanzas sin importar helpers desde `views.py`.
- `templates/shared/_busqueda_texto_script.html`: normalización equivalente en
  navegador para selectores y DataTables que filtran datos ya renderizados.
- `docs/evidencia/busqueda-personas-20260810/RESULTADOS.md`: matriz de cajas
  cubiertas, comandos y resultados de la regresión PostgreSQL.
- Uso posible: cualquier nueva caja que busque identidades debe reutilizar uno
  de estos componentes según la búsqueda ocurra en servidor o navegador; no debe
  crear otra normalización local.

## Regla de reemplazo

Si una herramienta nueva reemplaza otra, no se borra silenciosamente la anterior.
Debe marcarse como `reemplazada`, indicar fecha y enlazar la versión canónica. Si
la versión anterior contenía un secreto o dato prohibido, no se copia: se conserva
solo una descripción sanitizada del motivo y se rota el secreto si correspondía.

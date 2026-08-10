# Ensayo QA representativo y transición de permisos

Fecha: 2026-08-10

## Veredicto

**Antecedente del gate original, reemplazado por una ventana productiva
controlada.** No existe en este workspace una copia
reciente y protegida de producción ni una configuración o credencial de
QA/staging. Solo existe configuración local de desarrollo; el workflow de
despliegue referencia el host productivo mediante secretos no disponibles. No se
usó ese host como sustituto de QA y producción permanece intacta.

La evidencia sintética previa sigue siendo útil para validar la mecánica, pero
no cumple el requisito de representatividad ni permite fijar una ventana de
mantenimiento productiva.

La persona responsable decidió posteriormente operar sin QA/staging separado,
con pocos usuarios, mantenimiento y ejecución manual. El runbook vigente está en
[MIGRACIONES_OPERACION_PROFESOR.md](../../operacion/MIGRACIONES_OPERACION_PROFESOR.md).
Este documento conserva la evidencia y limitación del ensayo; ya no es por sí
solo el gate de despliegue.

## Estado del ensayo solicitado

| Paso | Estado representativo | Evidencia disponible |
| --- | --- | --- |
| Preflight PostgreSQL, espacio, tamaños y conteos | Bloqueado: no hay copia QA accesible | El runner parametrizado captura esos datos cuando recibe una conexión autorizada |
| `pg_dump` y restauración de la copia | Bloqueado | Backup/restore sintético aprobado; no equivale a copia real |
| Aplicar `asistencias.0004` | Bloqueado | Migración desde cero y backfill inactivo aprobados en PostgreSQL local |
| Reportar relaciones históricas y transición | Bloqueado sobre datos reales | Comando ampliado y 12 pruebas focalizadas aprobadas |
| Ensayar `finanzas.0012` | Bloqueado | 2,335 s sobre 300.000 pagos sintéticos; no fija ventana productiva |
| Locks y escritura representativa | Bloqueado | Medición sintética: 27 escrituras, máximo 967,264 ms, cero errores |
| Autorización del profesor contra la copia | Bloqueado | Pruebas locales confirman que historia inactiva no concede acceso |

No se generó un reporte nominal ficticio: los profesores, alumnos y relaciones
que deben conservar acceso solo pueden determinarse sobre la copia protegida.

La regresión local integrada ejecutó 87 pruebas de relaciones históricas,
Operación Profesor y permisos financieros en PostgreSQL 18 UTF-8: **87 OK en
247,997 s**. Un intento anterior se invalidó porque el clúster temporal se había
inicializado como `SQL_ASCII`; 86 casos avanzaron y el caso que serializa
“electrónica” falló por encoding. Se recreó el runtime en UTF-8 y solo el segundo
resultado se considera válido.

La regresión focalizada final, incluida la desactivación reversible y auditada,
ejecutó **12 pruebas OK en 0,812 s**.

El runtime PostgreSQL sintético usado para estas validaciones se detuvo y su
ruta temporal se eliminó al finalizar. No contenía una copia de producción; no
se conserva como respaldo ni artefacto.

## Reporte reproducible de transición

Después de restaurar la copia y aplicar `asistencias.0004`, generar primero el
reporte sanitizado:

```bash
python manage.py reportar_relaciones_historicas \
  --fecha-corte 2026-08-10 \
  --dias-vigencia-alumno 90 \
  --formato=json \
  --fallar-si-inseguro
```

El reporte identifica, sin nombres ni IDs:

- profesores con sesiones no canceladas desde la fecha de corte;
- pares profesor-disciplina que conservan alcance operativo;
- asignaciones que deben ser activadas explícitamente antes de abrir tráfico;
- pares sin relación, persona activa o rol activo que requieren revisión;
- alumnos vigentes por matrícula operativa;
- matrículas operativas inconsistentes;
- matrículas no operativas con asistencia reciente, únicamente como candidatas
  a revisión manual.

Para trabajar el listado nominal, Operaciones debe ejecutar la variante
protegida con `--incluir-detalle-operativo`. Esa salida contiene nombres e
identificadores: se guarda con permisos restrictivos fuera del repositorio y del
directorio público de evidencias, y se destruye según la retención de QA.

Una sesión futura es señal suficiente para exigir revisión administrativa de la
asignación del profesor, pero no la activa. Una asistencia reciente tampoco
demuestra matrícula vigente: solo incorpora el caso al listado manual.

## Procedimiento administrativo auditable

1. Aplicar `asistencias.0004` en la copia y generar ambos reportes.
2. Contrastar cada profesor futuro con programación, contrato o asignación
   administrativa vigente. Resolver primero pares sin persona o rol activo.
3. En Django Admin, abrir “Asignaciones de profesores a disciplinas”, filtrar
   por organización, `origen=historica` y `activa=No`, y seleccionar solo los
   IDs aprobados en el listado protegido.
4. Ejecutar “Activar relaciones seleccionadas tras revisión”. La operación
   bloquea las filas, valida el permiso en cada organización, actualiza revisor y
   fecha, audita cada relación y revierte todo el lote si una fila falla.
5. Para alumnos, revisar evidencia de matrícula vigente. No activar el conjunto
   completo de asistencias recientes. Usar la misma acción únicamente sobre los
   casos confirmados.
6. Repetir el reporte. Antes de abrir tráfico deben quedar en cero las
   asignaciones futuras `activar_administrativamente` o existir una decisión
   nominal documentada para cada excepción.
7. Ejecutar las pruebas de autorización con al menos un profesor conservado, uno
   no aprobado y un recurso de otra organización.

La activación es reversible marcando `activa=False` en el mismo administrador;
el cambio de estado requiere permiso y queda auditado. No se elimina la relación
ni su origen histórico.

## Doce pruebas omitidas

Las 12 pertenecen a vistas HTML de `monitor`, app archivada sin rutas activas en
Elemental Apps. Comparten el motivo declarado: `monitor esta archivado y sus
rutas HTML no forman parte de Elemental Apps v1.0`.

`MonitorDashboardTests`:

1. `test_vistas_html_requieren_login`
2. `test_dashboard_autenticado_responde_ok_sin_sitios`
3. `test_dashboard_muestra_sitio_existente`

`MonitorSitioWorkflowTests`:

4. `test_crear_sitio_normaliza_url_y_ejecuta_discovery`
5. `test_crear_sitio_preserva_filtros_globales_en_redirect`
6. `test_crear_sitio_rechaza_url_invalida`
7. `test_crear_sitio_rechaza_duplicado_en_mismo_proyecto`
8. `test_detalle_muestra_discovery_y_configuracion`
9. `test_detalle_no_crea_configuracion_por_solo_ver`

`MonitorConfiguracionTests`:

10. `test_configuracion_global_puede_existir_sin_configuracion_por_sitio`
11. `test_configuracion_global_preserva_filtros_globales_en_redirect`
12. `test_configuracion_por_sitio_guarda_false_y_lo_muestra_seleccionado`

Riesgo residual: regresiones de autenticación, URL, discovery y configuración
en la interfaz archivada de `monitor` no se detectan. Estas pruebas no cubren
migraciones, relaciones profesor/alumno, aislamiento entre organizaciones,
pagos históricos, locks ni backup/restauración; por ello no omiten una garantía
crítica de esta entrega. Si `monitor` vuelve a publicarse, deben rehabilitarse y
actualizarse antes.

## Datos temporales y cierre de QA

El clúster, la base restaurada y el dump de QA son datos temporales, no respaldos
operativos ni artefactos durables. Una vez aprobado el informe:

1. conservar solo JSON/logs sanitizados y el acta de verificaciones;
2. confirmar que no se requieren reproducciones adicionales;
3. detener procesos y conexiones de la copia;
4. eliminar base restaurada, dump y clúster según el procedimiento de QA;
5. registrar responsable, fecha y targets eliminados, sin copiar datos reales al
   repositorio.

La evidencia aquí descrita no reemplaza los gates que infraestructura debe
ejecutar durante la ventana productiva manual.

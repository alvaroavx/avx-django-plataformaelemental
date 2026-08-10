# Evidencia — poblado operativo agosto 2026

Fecha: 2026-08-10
Entorno: PostgreSQL local de desarrollo autorizado.
Marcador: `[DATOS_PRUEBA_MES_OPERATIVO]`

## Identidades y alcance utilizados

| Profesor | Organización | Disciplina |
| --- | --- | --- |
| Evelyn Astorga | Espacio Elementos | Lyra |
| Laura Piña Mena | Latin Rengo | LatinRengo |
| Álvaro Vargas Quezada | Espacio Elementos | Tela Aérea, creada como dato sintético |

No se crearon personas ni organizaciones. Se reutilizaron estudiantes activos y
se crearon 12 matrículas operativas faltantes. La disciplina Tela Aérea y su
bloque del viernes quedaron identificados como parte del escenario de prueba.

## Resultado

- 14 sesiones creadas.
- 25 asistencias creadas.
- 12 matrículas creadas.
- 1 bloque horario creado.
- 0 conflictos con sesiones existentes.
- Segunda ejecución: 0 sesiones, asistencias, matrículas o bloques duplicados.
- 25 `AttendanceConsumption` creados por las señales reales; todos quedaron en
  deuda porque el escenario no inventa pagos.

Distribución:

| Disciplina | Cerradas | Abiertas parciales | Planificadas | Asistencias |
| --- | ---: | ---: | ---: | ---: |
| Lyra | 1 | 1 | 3 | 11 |
| LatinRengo | 1 | 0 | 4 | 10 |
| Tela Aérea | 0 | 1 | 3 | 4 |

Estados de asistencia: 19 presentes, 2 ausentes y 4 justificadas.

El caso incompleto deliberado más visible es LatinRengo del 8 de agosto:
permanece planificado y sin asistencias pese a ser una fecha pasada. Lyra del 10
y Tela Aérea del 7 permanecen abiertas con registros parciales.

## Validaciones

- `manage.py check`: sin issues.
- Ruff y `git diff --check`: aprobados.
- `asistencias.test_poblador_mes`: 2 tests aprobados en 1,048 s.
- Preview: 14 sesiones y 25 asistencias previstas; cero escrituras.
- Aplicación: transacción completada íntegramente.
- Reintento: IDs de sesiones conservados y cero duplicados.

Artefactos:

- [Preview](preview.json)
- [Primera aplicación](aplicacion.json)
- [Reintento idempotente](reintento.json)
- [Verificación agregada](verificacion.json)
- [Tests](tests.log)

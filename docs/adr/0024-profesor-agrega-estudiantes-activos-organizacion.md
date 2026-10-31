# ADR-0024: Profesor agrega estudiantes activos de su organización

**Fecha:** 2026-10-31 | **Decidió:** Álvaro | **Estado:** vigente

**Contexto:** La restricción de ADR-0019 exigía una matrícula operativa previa
en la disciplina. En la operación real esto impedía que una profesora agregara
alumnas activas de su propia organización, aunque administración sí pudiera
hacerlo, y convertía una relación interna en un bloqueo del registro diario.

**Alternativas descartadas:**

- Mantener la activación previa por administración — agrega una dependencia operativa innecesaria para cada taller.
- Eliminar `AlumnoDisciplina` — perdería la relación útil para roster, trazabilidad y otros procesos del dominio.
- Mostrar estudiantes de cualquier organización — rompería el aislamiento organizacional.

**Decisión:** Una profesora autorizada para una sesión puede buscar y agregar a
cualquier persona activa con rol `ESTUDIANTE` activo en la organización real de
la sesión. Al agregarla, el sistema crea o activa atómicamente su
`AlumnoDisciplina` para esa disciplina y registra auditoría. Esta decisión
reemplaza solamente la restricción de ADR-0019 que exigía matrícula previa.

**Consecuencias asumidas:** La profesora confirma la incorporación operativa a
la disciplina mediante el acto de agregar asistencia. No recibe permiso para
crear personas, operar otra organización, editar matrículas directamente ni
administrar sesiones o finanzas. Las matrículas históricas quedan revisadas con
el actor y fecha de esa incorporación.

**Condiciones de revisión:** Revisar si aparecen organizaciones donde el padrón
completo de estudiantes sea información restringida entre talleres, o si se
necesita separar la capacidad de matricular de la capacidad de registrar
asistencia.

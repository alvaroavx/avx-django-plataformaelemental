# ADR 0013: las vistas operativas comparten el lenguaje visual del Panel

- Estado: Aceptada
- Fecha: 2026-10-06
- Decidió: Álvaro

## Contexto

Panel ya estableció una jerarquía reconocible mediante encabezados compactos,
superficies con bordes suaves, radios consistentes, tipografía de alto contraste
y color reservado para estados o acciones. Calendario, Asistencias, Estudiantes
y Profesores conservaban composiciones y acabados distintos entre sí.

## Alternativas descartadas

- Rediseñar cada página de forma independiente: aumentaría variantes sin aportar
  una identidad operacional común.
- Convertir todos los bloques en tarjetas coloreadas: reduciría jerarquía y haría
  competir la decoración con los estados reales.
- Reproducir literalmente el Panel: estas páginas necesitan mayor densidad para
  calendarios, filtros y tablas.

## Decisión

Calendario, Asistencias, Estudiantes y Profesores reutilizan el lenguaje visual
del Panel sin cambiar sus flujos: eyebrow contextual, título y descripción;
superficies con borde de un píxel y radio de `1rem`; tablas con cabecera secundaria
y ritmo uniforme; tarjetas métricas claras con una franja cromática de estado.

El color sigue reservado para estado, disciplina o acción. Las tablas conservan
su densidad y desplazamiento horizontal cuando el volumen de columnas lo exige.
El botón `Gestionar sesiones` del Panel incorpora un icono de calendario y respeta
la anatomía global `[icono] [texto]`.

## Consecuencias asumidas

La capa visual añade clases compartidas, pero no modifica queries, permisos,
filtros ni reglas de negocio. El calendario conserva presentaciones distintas en
mobile y desktop. Las pantallas no quedan idénticas: comparten gramática mientras
cada una mantiene la forma necesaria para su tarea.

## Condiciones de revisión

Revisar si la inspección en dispositivos reales revela pérdida de densidad,
desbordes nuevos o contraste insuficiente en tema oscuro, o si se adopta un
sistema de componentes que reemplace estas clases compartidas.

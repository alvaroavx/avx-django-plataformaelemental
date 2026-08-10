# Evidencia — corrección de aprobación de solicitudes

Fecha: 2026-08-10

## Síntoma reproducido

Después de renderizar un error en `/personas/solicitudes-acceso/<uuid>/aprobar/`,
el formulario GET de búsqueda no tenía `action`. El navegador reutilizaba la URL
actual y enviaba `persona_q` a `/aprobar/`. Esa vista está correctamente limitada
a POST, por lo que respondía 404 aunque el patrón de URL existiera.

La búsqueda `alvaro vargas` tampoco encontraba una Persona almacenada como
`Álvaro Vargas`: comparaba la frase completa contra cada campo por separado y no
normalizaba tildes.

## Corrección

- El buscador GET apunta explícitamente al detalle de la solicitud.
- `/aprobar/` continúa rechazando GET; no se amplió la superficie sensible.
- User y Persona se buscan por fragmentos normalizados sin tildes.
- Las tres estrategias de resolución son mutuamente excluyentes.
- Seleccionar User y Persona simultáneamente devuelve HTTP 400 con explicación,
  conserva la solicitud pendiente y no crea ni enlaza identidades.

No se modificaron modelos, migraciones ni datos de la base de desarrollo.

## Pruebas

Primera ejecución: 5 casos existentes pasaron y la regresión nueva detectó la
búsqueda defectuosa por nombre completo sin tilde.

Después de corregirla:

```text
Ran 6 tests in 6.099s
OK
```

Detalle: [tests.log](tests.log).

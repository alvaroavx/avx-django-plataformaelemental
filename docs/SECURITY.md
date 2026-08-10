# Seguridad del repositorio

Fecha de actualizacion: 2026-08-09

## Regla base
No guardar credenciales reales en el repositorio.

Esto incluye:
- passwords
- tokens
- API keys
- llaves privadas
- secretos Django
- archivos `.env` reales
- dumps o backups con datos sensibles
- listados de personas, documentos tributarios o archivos reales usados como fixtures informales

## Tests
Los tests deben ser reproducibles localmente sin depender de variables de entorno secretas.

Reglas:
- no usar passwords que parezcan reales
- usar constantes dummy claramente no sensibles, por ejemplo `TEST_PASSWORD = "not-a-real-test-password"`
- no reutilizar usuarios o claves productivas en fixtures
- no guardar tokens reales en fixtures

## Archivos de entorno
- `.env`, `.env.*` y archivos runtime no deben versionarse.
- `.env.example` puede versionarse, pero solo con placeholders.
- Si un valor parece usable en produccion, no debe estar en `.env.example`.

## Si un secreto entra al repo
1. Rotar el secreto si pudo ser real o reutilizable.
2. Removerlo del HEAD.
3. Evaluar limpieza de historial si el secreto tuvo exposicion real.
4. Revisar logs, proveedores y sistemas donde el secreto pudo haberse usado.
5. Documentar la decision si se decide no limpiar historial porque era un valor dummy.

Quitar un secreto del HEAD no lo elimina del historial Git.

## Datos personales y tributarios

- `data/` y `public/` no son zonas autorizadas para datos reales por el solo hecho
  de estar fuera de `media/`.
- Una fixture versionada debe ser sintética y estar referenciada por tests.
- Antes de eliminar archivos ambiguos, confirmar retención y dueño; después,
  decidir si basta retirarlos del HEAD o si corresponde limpiar el historial.
- No copiar contenido personal a issues, logs, documentación ni reportes de auditoría.

## Secret scanning
Herramientas recomendadas:
- `gitleaks`
- `detect-secrets`
- `trufflehog`

Por ahora no existe un job obligatorio de secret scanning en CI. Antes de hacerlo obligatorio hay que calibrar falsos positivos en tests y documentacion.

# Hooks de Plataforma Elemental para scripts/release/release.sh.
# release.sh los carga desde la release nueva, con ENV_FILE ya cargado,
# RELEASE_PATH definido y la función `manage` disponible.
# Conservan las validaciones de scripts/deploy.sh.

pre_checks() {
  if [[ "${DJANGO_ENV:-}" != "prod" ]]; then
    die "DJANGO_ENV debe ser prod para un deploy productivo."
  fi
  [[ "${POSTGRES_DB:-}" == "plataforma_elemental_prod" ]] || die "POSTGRES_DB no es la base productiva esperada."
  [[ "${POSTGRES_USER:-}" == "elementos" ]] || die "POSTGRES_USER no es el usuario productivo esperado."
  [[ "${POSTGRES_HOST:-}" == "127.0.0.1" ]] || die "POSTGRES_HOST no es el host productivo esperado."
  [[ "${POSTGRES_PORT:-}" == "5432" ]] || die "POSTGRES_PORT no es el puerto productivo esperado."
}

pre_migrate() {
  # La reparación histórica de Operación Profesor tiene su propio runbook escalonado.
  if manage showmigrations asistencias --list \
    | grep -Eq '^\[ \].*(0004b_reparar_precondiciones_0005|0005_reparar_schema_0004_aplicada_precommit_v2|0006_merge_0004b_y_0005|0007_reconciliar_relaciones_activas)'; then
    die "La reparación histórica de Operación Profesor sigue pendiente; usar el runbook escalonado."
  fi
}

post_collectstatic() {
  local static_root="$RELEASE_PATH/plataformaelemental/staticfiles"
  # Nginx sirve STATIC_ROOT directamente desde current/.
  find "$static_root" -type d -exec chmod 755 {} +
  find "$static_root" -type f -exec chmod 644 {} +
  local required
  for required in "$static_root/admin/css/base.css" "$static_root/staticfiles.json"; do
    [[ -r "$required" ]] || die "Falta un estático obligatorio: $required"
  done
  # Nginx necesita atravesar la ruta hasta los estáticos.
  chmod 755 "$RELEASE_PATH" "$RELEASE_PATH/plataformaelemental"
}

post_deploy() {
  manage clearsessions
}

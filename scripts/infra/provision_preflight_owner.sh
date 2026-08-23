#!/usr/bin/env bash
set -euo pipefail

# Provisiona únicamente el owner de la función de preflight.
# Debe ejecutarse como root en el host PostgreSQL y nunca recibe SQL por stdin.
if [[ "${EUID}" -ne 0 ]]; then
  echo "debe ejecutarse como root" >&2
  exit 64
fi

database="plataforma_elemental_prod"
if [[ "$#" -gt 0 ]]; then
  [[ "$#" -eq 2 && "$1" == "--database" && "$2" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] || {
    echo "uso: $0 [--database NOMBRE]" >&2
    exit 64
  }
  database="$2"
fi

exec sudo -u postgres psql --no-psqlrc -X -v ON_ERROR_STOP=1 --dbname="$database" <<'SQL'
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'elemental_release_preflight_owner') THEN
    CREATE ROLE elemental_release_preflight_owner NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS;
  END IF;
END
$$;

ALTER ROLE elemental_release_preflight_owner
  NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS;

SELECT current_database() AS db \gset
REVOKE ALL ON DATABASE :"db" FROM elemental_release_preflight_owner;
GRANT CONNECT ON DATABASE :"db" TO elemental_release_preflight_owner;
REVOKE CREATE ON SCHEMA public FROM elemental_release_preflight_owner;
REVOKE TEMPORARY ON DATABASE :"db" FROM elemental_release_preflight_owner;
GRANT USAGE ON SCHEMA public TO elemental_release_preflight_owner;
GRANT SELECT ON TABLE django_migrations,
  asistencias_asignacionprofesordisciplina,
  asistencias_alumnodisciplina
  TO elemental_release_preflight_owner;

ALTER FUNCTION public.elemental_release_preflight() OWNER TO elemental_release_preflight_owner;
ALTER FUNCTION public.elemental_release_preflight() SECURITY DEFINER;
ALTER FUNCTION public.elemental_release_preflight() SET search_path TO pg_catalog, public;
REVOKE ALL ON FUNCTION public.elemental_release_preflight() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.elemental_release_preflight() TO elemental_release_ro;
SQL

echo "preflight owner provisionado en ${database}"

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

CREATE OR REPLACE FUNCTION public.elemental_release_preflight()
RETURNS jsonb
LANGUAGE sql
SECURITY DEFINER
SET search_path TO pg_catalog, public
AS $$
SELECT jsonb_build_object(
  'migrations', jsonb_build_object(
    'asistencias_0004', (SELECT count(*) FROM django_migrations WHERE app = 'asistencias' AND name = '0004_alter_sesionclase_estado_liberacionsesion_and_more'),
    'asistencias_0005', (SELECT count(*) FROM django_migrations WHERE app = 'asistencias' AND name IN ('0005_reparar_schema_0004_aplicada_precommit', '0005_reparar_schema_0004_aplicada_precommit_v2')),
    'asistencias_0007', (SELECT count(*) FROM django_migrations WHERE app = 'asistencias' AND name = '0007_reconciliar_relaciones_activas'),
    'finanzas_0012', (SELECT count(*) FROM django_migrations WHERE app = 'finanzas' AND name = '0012_payment_clave_idempotencia_payment_disciplina_and_more')
  ),
  'schema', (SELECT coalesce(jsonb_agg(jsonb_build_object('table', table_name, 'column', column_name, 'nullable', is_nullable, 'default', coalesce(column_default, '')) ORDER BY table_name), '[]'::jsonb)
             FROM information_schema.columns
             WHERE table_schema = 'public' AND table_name IN ('asistencias_asignacionprofesordisciplina', 'asistencias_alumnodisciplina') AND column_name = 'origen'),
  'counts', jsonb_build_object(
    'profesor', jsonb_build_object('total', (SELECT count(*) FROM asistencias_asignacionprofesordisciplina), 'active', (SELECT count(*) FROM asistencias_asignacionprofesordisciplina WHERE activa), 'active_historical', (SELECT count(*) FROM asistencias_asignacionprofesordisciplina WHERE activa AND origen = 'historica')),
    'alumno', jsonb_build_object('total', (SELECT count(*) FROM asistencias_alumnodisciplina), 'active', (SELECT count(*) FROM asistencias_alumnodisciplina WHERE activa), 'active_historical', (SELECT count(*) FROM asistencias_alumnodisciplina WHERE activa AND origen = 'historica'))
  )
);
$$;

ALTER FUNCTION public.elemental_release_preflight() OWNER TO elemental_release_preflight_owner;
ALTER FUNCTION public.elemental_release_preflight() SECURITY DEFINER;
ALTER FUNCTION public.elemental_release_preflight() SET search_path TO pg_catalog, public;
REVOKE ALL ON FUNCTION public.elemental_release_preflight() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.elemental_release_preflight() TO elemental_release_ro;
REVOKE SELECT ON TABLE django_migrations,
  asistencias_asignacionprofesordisciplina,
  asistencias_alumnodisciplina
  FROM elemental_release_ro;
SQL

echo "preflight owner provisionado en ${database}"

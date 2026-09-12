#!/usr/bin/env python3

from pathlib import Path

import yaml


WORKFLOW = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "deploy.yml"
DEPLOY_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "deploy.sh"


def exigir(condicion, mensaje):
    if not condicion:
        raise SystemExit(f"GATE CI INVÁLIDO: {mensaje}")


def comandos(job):
    return "\n".join(
        step.get("run", "")
        for step in job.get("steps", [])
        if isinstance(step, dict)
    )


def main():
    contenido = WORKFLOW.read_text(encoding="utf-8")
    workflow = yaml.load(contenido, Loader=yaml.BaseLoader)
    exigir(isinstance(workflow, dict), "deploy.yml no contiene un documento YAML válido.")

    triggers = workflow.get("on", {})
    ramas_push = triggers.get("push", {}).get("branches", [])
    exigir("main" in ramas_push, "el workflow no se ejecuta en push a main.")
    exigir("workflow_dispatch" not in triggers, "deploy no debe requerir despacho manual.")

    jobs = workflow.get("jobs", {})
    test = jobs.get("test")
    cambios_esquema = jobs.get("cambios_esquema")
    deploy = jobs.get("deploy")
    exigir(isinstance(test, dict), "falta el job test.")
    exigir(isinstance(cambios_esquema, dict), "falta el job cambios_esquema.")
    exigir(isinstance(deploy, dict), "falta el job deploy.")

    postgres = test.get("services", {}).get("postgres", {})
    exigir(
        str(postgres.get("image", "")).startswith("postgres:"),
        "test no declara un servicio PostgreSQL aislado.",
    )
    entorno_test = test.get("env", {})
    exigir(entorno_test.get("DJANGO_ENV") == "dev", "test debe usar DJANGO_ENV=dev.")
    exigir(
        entorno_test.get("POSTGRES_DB") == "plataforma_elemental_ci",
        "test debe usar la base efímera plataforma_elemental_ci.",
    )
    exigir(
        all("secrets." not in str(valor) for valor in entorno_test.values()),
        "el entorno del job test no puede consumir secrets de GitHub.",
    )
    exigir(
        postgres.get("env", {}).get("POSTGRES_DB") == entorno_test.get("POSTGRES_DB"),
        "Django y el servicio PostgreSQL deben usar la misma base CI.",
    )

    comandos_test = comandos(test)
    for comando_requerido in (
        "python manage.py check",
        "python manage.py makemigrations --check --dry-run",
        "ruff check .",
        "python manage.py test asistencias finanzas personas",
        "python manage.py test asistencias.test_profesor_ux asistencias.test_operacion_profesor",
    ):
        exigir(
            comando_requerido in comandos_test,
            f"falta el comando obligatorio: {comando_requerido}",
        )
    exigir("--keepdb" not in comandos_test, "CI no debe conservar su base de pruebas.")
    for referencia_prohibida in (".env.prod", "DEPLOY_ENV_FILE", "secrets.", "ssh "):
        exigir(
            referencia_prohibida not in comandos_test,
            f"el job test contiene una referencia prohibida: {referencia_prohibida}",
        )

    needs = deploy.get("needs")
    exigir(
        isinstance(needs, list) and {"test", "cambios_esquema"}.issubset(needs),
        "deploy debe depender de test y cambios_esquema.",
    )
    condicion_deploy = deploy.get("if", "")
    exigir("always()" not in condicion_deploy, "deploy no puede usar if: always().")
    exigir("success()" in condicion_deploy, "deploy debe exigir success() explícitamente.")
    exigir(
        "needs.cambios_esquema.outputs.hay_cambios_esquema == 'false'" not in condicion_deploy,
        "deploy no debe omitir automáticamente releases que contienen migraciones.",
    )
    exigir(
        "workflow_dispatch" not in condicion_deploy,
        "deploy no debe requerir despacho manual.",
    )
    exigir(
        "github.event_name" not in condicion_deploy,
        "deploy debe activarse por el push que aprobó CI.",
    )
    exigir(
        "environment" not in deploy,
        "deploy automático no debe requerir una aprobación de environment.",
    )

    comandos_esquema = comandos(cambios_esquema)
    exigir(
        "migrations/[^/]+\\.py" in comandos_esquema,
        "cambios_esquema debe detectar archivos de migración.",
    )

    deploy_script = DEPLOY_SCRIPT.read_text(encoding="utf-8")
    for contrato_deploy in (
        "python manage.py migrate --check",
        "backup_database",
        "pg_dump",
        "pg_restore --list",
        "systemctl stop",
        "python manage.py migrate --noinput",
        "python manage.py collectstatic --noinput",
        "ManifestStaticFilesStorage",
    ):
        origen = contenido if contrato_deploy == "ManifestStaticFilesStorage" else deploy_script
        if contrato_deploy == "ManifestStaticFilesStorage":
            origen = (DEPLOY_SCRIPT.parents[1] / "plataformaelemental/config/prod.py").read_text(
                encoding="utf-8"
            )
        exigir(
            contrato_deploy in origen,
            f"falta el contrato de release: {contrato_deploy}",
        )

    pasos_deploy = deploy.get("steps", [])
    nombres = [step.get("name", "") for step in pasos_deploy if isinstance(step, dict)]
    exigir("Deploy to production" in nombres, "falta el paso de deploy existente.")

    print(
        "Gate CI válido: push main -> test PostgreSQL completo -> respaldo si hay "
        "migraciones -> migrate, estáticos versionados y deploy automático"
    )


if __name__ == "__main__":
    main()

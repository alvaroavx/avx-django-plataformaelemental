#!/usr/bin/env python3

from pathlib import Path

import yaml


WORKFLOW = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "deploy.yml"


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
    confirmacion = (
        triggers.get("workflow_dispatch", {})
        .get("inputs", {})
        .get("confirmacion", {})
    )
    exigir(
        confirmacion.get("required") == "true",
        "workflow_dispatch debe exigir la confirmación manual.",
    )

    jobs = workflow.get("jobs", {})
    test = jobs.get("test")
    deploy = jobs.get("deploy")
    exigir(isinstance(test, dict), "falta el job test.")
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
        "ruff check .",
        "python manage.py test asistencias finanzas personas",
        "python manage.py test asistencias.test_operacion_profesor.ProfesorMultiOrganizacionTests",
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
        needs == "test" or (isinstance(needs, list) and "test" in needs),
        "deploy debe declarar needs: test.",
    )
    condicion_deploy = deploy.get("if", "")
    exigir("always()" not in condicion_deploy, "deploy no puede usar if: always().")
    exigir("success()" in condicion_deploy, "deploy debe exigir success() explícitamente.")
    exigir(
        "github.event_name == 'push'" not in condicion_deploy,
        "un push a main no puede habilitar deploy.",
    )
    exigir(
        "github.event_name == 'workflow_dispatch'" in condicion_deploy,
        "deploy debe requerir workflow_dispatch.",
    )
    exigir(
        "inputs.confirmacion == 'DESPLEGAR_PRODUCCION'" in condicion_deploy,
        "deploy debe requerir la confirmación DESPLEGAR_PRODUCCION.",
    )
    exigir(
        deploy.get("environment", {}).get("name") == "production",
        "deploy debe conservar la aprobación del environment production.",
    )

    pasos_deploy = deploy.get("steps", [])
    nombres = [step.get("name", "") for step in pasos_deploy if isinstance(step, dict)]
    exigir("Deploy to production" in nombres, "falta el paso de deploy existente.")
    exigir("Smoke test production" in nombres, "falta el smoke post-deploy separado.")
    exigir(
        nombres.index("Smoke test production") > nombres.index("Deploy to production"),
        "el smoke debe ejecutarse después del deploy.",
    )
    exigir(
        "bash scripts/smoke_produccion.sh" in comandos(deploy),
        "el job deploy no ejecuta el smoke versionado.",
    )

    print(
        "Gate CI válido: push main -> test PostgreSQL completo -> deploy omitido; "
        "workflow_dispatch confirmado -> deploy -> smoke post-deploy"
    )


if __name__ == "__main__":
    main()

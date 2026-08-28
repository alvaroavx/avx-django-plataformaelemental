import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "release_asistencias_escalonado.sh"
APPLY_ROOT = ROOT / "scripts" / "infra" / "elemental_release_apply_root.sh"
WORKFLOW = ROOT / ".github" / "workflows" / "release-asistencias-escalonado.yml"
PREFLIGHT_RUNNER = ROOT / "scripts" / "infra" / "elemental_release_preflight_runner.sh"
MIGRATION_0004B = ROOT / "asistencias" / "migrations" / "0004b_reparar_precondiciones_0005.py"
MIGRATION_0006 = ROOT / "asistencias" / "migrations" / "0006_merge_0004b_y_0005.py"
MIGRATION_0005V2 = ROOT / "asistencias" / "migrations" / "0005_reparar_schema_0004_aplicada_precommit_v2.py"
MIGRATION_0007 = ROOT / "asistencias" / "migrations" / "0007_reconciliar_relaciones_activas.py"


class ReleaseAsistenciasEscalonadoContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.script = SCRIPT.read_text(encoding="utf-8")
        cls.workflow = WORKFLOW.read_text(encoding="utf-8")

    def test_self_test_del_script_y_gates_explicitos(self):
        resultado = subprocess.run(
            ["bash", str(SCRIPT), "self-test"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(resultado.returncode, 0, resultado.stderr)
        self.assertIn("preflight seguro", resultado.stdout)

    def test_preflight_runtime_observa_systemctl_sin_stop(self):
        resultado = subprocess.run(
            ["bash", str(SCRIPT), "runtime-self-test"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(resultado.returncode, 0, resultado.stderr)
        self.assertIn("sin stop ni downtime", resultado.stdout)

    def test_apply_rechaza_marker_con_revision_pendiente(self):
        resultado = subprocess.run(
            ["bash", str(SCRIPT), "marker-self-test"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(resultado.returncode, 0, resultado.stderr)
        self.assertIn("review_required=true rechaza apply", resultado.stdout)

    def test_preflight_invalido_no_detiene_gunicorn(self):
        inicio = self.script.index("preflight_report() {\n")
        fin = self.script.index("valid_marker() {\n", inicio)
        bloque = self.script[inicio:fin]
        self.assertIn('systemctl is-active "$SERVICE"', bloque)
        self.assertNotIn("systemctl stop", bloque)
        self.assertIn('"review_required": False', self.script)
        self.assertIn("PREFLIGHT_REPORT_OK", self.script)

    def test_apply_solo_migra_0004b_y_0005_y_no_global(self):
        bloque = self.script[self.script.index("apply_release() {") :]
        self.assertLess(bloque.index("valid_marker"), bloque.index('systemctl stop "$SERVICE"'))
        self.assertIn("migrate asistencias 0004b_reparar_precondiciones_0005", bloque)
        self.assertIn("migrate asistencias 0005_reparar_schema_0004_aplicada_precommit_v2", bloque)
        self.assertIn("migrate asistencias 0007_reconciliar_relaciones_activas", bloque)
        self.assertNotIn("manage.py migrate --noinput", bloque)
        self.assertIn("migration_started=1", bloque)
        self.assertIn("recover_before_migration", bloque)
        self.assertIn('sha256sum "$BACKUP_FILE"', self.script)
        self.assertIn("snapshot_reference", self.script)
        self.assertIn("snapshot_sha256", self.script)

    def test_apply_transfiere_entorno_real_al_smoke(self):
        self.assertIn('DEPLOY_ENV_FILE="$ENV_FILE" bash "$APP_DIR/scripts/smoke_produccion.sh"', self.script)

    def test_workflow_solo_dispatch_tag_y_environments_protegidos(self):
        self.assertIn("push:", self.workflow)
        self.assertIn('"release/asistencias-*"', self.workflow)
        self.assertNotIn("workflow_dispatch:", self.workflow)
        self.assertNotIn("ssh-keyscan", self.workflow)
        self.assertIn("DEPLOY_KNOWN_HOSTS", self.workflow)
        self.assertIn("name: production-readonly", self.workflow)
        self.assertIn("name: production", self.workflow)
        self.assertIn('"${GITHUB_REF_TYPE}" = tag', self.workflow)
        self.assertIn("cat-file -t", self.workflow)
        self.assertIn("refs/tags/${RELEASE_TAG}^{commit}", self.workflow)
        self.assertIn("release-asistencias-production", self.workflow)
        preflight = self.workflow[self.workflow.index("Preflight remoto sin downtime") : self.workflow.index("  apply:")]
        self.assertNotIn("git fetch --no-tags origin", preflight)
        self.assertIn('"preflight --tag ${RELEASE_TAG} --sha ${RELEASE_SHA} --parent ${RELEASE_PARENT}"', preflight)

    def test_runner_readonly_falla_cerrado_y_omite_venv(self):
        runner = PREFLIGHT_RUNNER.read_text(encoding="utf-8")
        self.assertIn("preflight-report.json", runner)
        self.assertIn("PREFLIGHT_OK", runner)
        self.assertIn(":(exclude).venv", runner)
        self.assertIn('rm -f "$state_dir/preflight.json"', runner)
        self.assertIn('marker="$state_dir/preflight.json"', runner)
        self.assertNotIn("FROM django_migrations", runner)
        self.assertNotIn("FROM asistencias_asignacionprofesordisciplina", runner)
        self.assertNotIn("FROM asistencias_alumnodisciplina", runner)
        self.assertIn("elemental_release_preflight()", runner)

    def test_runner_no_concede_lectura_directa_al_rol_readonly(self):
        runner = PREFLIGHT_RUNNER.read_text(encoding="utf-8")
        for tabla in ("django_migrations", "asistencias_asignacionprofesordisciplina", "asistencias_alumnodisciplina"):
            self.assertNotIn(f"FROM {tabla}", runner)
        self.assertEqual(runner.count("elemental_release_preflight()"), 1)

    def test_launcher_ejecuta_script_del_tag_sin_bootstrap_inexistente(self):
        launcher = APPLY_ROOT.read_text(encoding="utf-8")
        self.assertIn('git show "$tag:scripts/release_asistencias_escalonado.sh"', launcher)
        self.assertIn('mktemp /run/elemental-release-asistencias.', launcher)
        self.assertIn('bash -n "$release_script"', launcher)
        self.assertIn('RELEASE_APP_DIR=/srv/elementos', launcher)
        self.assertNotIn('/srv/elementos/scripts/release_asistencias_escalonado.sh apply', launcher)

    def test_grafo_0006_une_las_dos_ramas(self):
        migration = MIGRATION_0006.read_text(encoding="utf-8")
        self.assertIn('("asistencias", "0004b_reparar_precondiciones_0005")', migration)
        self.assertIn('("asistencias", "0005_reparar_schema_0004_aplicada_precommit_v2")', migration)
        self.assertIn("operations = []", migration)
        repair = MIGRATION_0004B.read_text(encoding="utf-8")
        self.assertIn("atomic = False", repair)
        self.assertIn("SET DEFAULT 'explicita'", repair)
        self.assertIn("SET NOT NULL", repair)
        self.assertIn("replaces =", MIGRATION_0005V2.read_text(encoding="utf-8"))

    def test_0007_preserva_activas_y_reconcilia_origen(self):
        migration = MIGRATION_0007.read_text(encoding="utf-8")
        self.assertIn('dependencies = [("asistencias", "0006_merge_0004b_y_0005")]', migration)
        self.assertIn("WHERE {quote('activa')} AND {quote('origen')} = 'historica'", migration)
        self.assertIn('"reconciliada", "Reconciliada técnicamente"', migration)
        self.assertNotIn("SET {quote('activa')} = false", migration)


if __name__ == "__main__":
    unittest.main()

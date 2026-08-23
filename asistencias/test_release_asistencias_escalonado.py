import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "release_asistencias_escalonado.sh"
WORKFLOW = ROOT / ".github" / "workflows" / "release-asistencias-escalonado.yml"
MIGRATION_0004B = ROOT / "asistencias" / "migrations" / "0004b_reparar_precondiciones_0005.py"
MIGRATION_0006 = ROOT / "asistencias" / "migrations" / "0006_merge_0004b_y_0005.py"
MIGRATION_0005V2 = ROOT / "asistencias" / "migrations" / "0005_reparar_schema_0004_aplicada_precommit_v2.py"


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

    def test_preflight_invalido_no_detiene_gunicorn(self):
        inicio = self.script.index("preflight() {\n")
        fin = self.script.index("valid_marker() {\n", inicio)
        bloque = self.script[inicio:fin]
        self.assertIn('systemctl is-active "$SERVICE"', bloque)
        self.assertNotIn("systemctl stop", bloque)
        self.assertIn("origen no presenta la condición parcial esperada", bloque)
        self.assertIn("PREFLIGHT_OK", bloque)

    def test_apply_solo_migra_0004b_y_0005_y_no_global(self):
        bloque = self.script[self.script.index("apply_release() {") :]
        self.assertLess(bloque.index("preflight"), bloque.index('systemctl stop "$SERVICE"'))
        self.assertIn("migrate asistencias 0004b_reparar_precondiciones_0005", bloque)
        self.assertIn("migrate asistencias 0005_reparar_schema_0004_aplicada_precommit_v2", bloque)
        self.assertNotIn("manage.py migrate --noinput", bloque)
        self.assertIn("migration_started=1", bloque)
        self.assertIn("recover_before_migration", bloque)

    def test_workflow_solo_dispatch_tag_y_environments_protegidos(self):
        self.assertIn("workflow_dispatch:", self.workflow)
        self.assertNotIn("push:", self.workflow)
        self.assertIn("name: production-readonly", self.workflow)
        self.assertIn("name: production", self.workflow)
        self.assertIn('"${GITHUB_REF_TYPE}" = tag', self.workflow)
        self.assertIn("cat-file -t", self.workflow)
        self.assertIn("refs/tags/${RELEASE_TAG}^{commit}", self.workflow)
        self.assertIn("release-asistencias-production", self.workflow)
        preflight = self.workflow[self.workflow.index("Preflight remoto sin mantenimiento") : self.workflow.index("  apply:")]
        self.assertNotIn("git fetch --no-tags origin", preflight)
        self.assertIn('"preflight --tag ${RELEASE_TAG} --sha ${RELEASE_SHA} --parent ${RELEASE_PARENT}"', preflight)

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


if __name__ == "__main__":
    unittest.main()

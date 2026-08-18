import subprocess
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "release_asistencias_0005.sh"
RUNBOOK = REPO_ROOT / "docs" / "operacion" / "MIGRACIONES_OPERACION_PROFESOR.md"
DEPLOY_DOC = REPO_ROOT / "docs" / "operacion" / "DEPLOY.md"


class ReleaseAsistencias0005ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contenido = SCRIPT.read_text(encoding="utf-8")

    def bloque(self, inicio, fin):
        desde = self.contenido.index(inicio)
        hasta = self.contenido.index(fin, desde)
        return self.contenido[desde:hasta]

    def test_self_test_cubre_las_dos_rutas_sin_base_de_datos(self):
        resultado = subprocess.run(
            ["bash", str(SCRIPT), "self-test"],
            cwd=REPO_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(resultado.returncode, 0, resultado.stderr)
        self.assertIn("rutas y migraciones explícitas OK", resultado.stdout)

    def test_script_no_contiene_migrate_global_y_conserva_release_anterior(self):
        script_anterior = (
            REPO_ROOT / "scripts" / "release_operacion_profesor.sh"
        ).read_text(encoding="utf-8")

        self.assertIn(
            'EXPECTED_RELEASE_TAG="release/asistencias-0005-20260818.1"',
            self.contenido,
        )
        self.assertIn(
            'EXPECTED_RELEASE_TAG="release/operacion-profesor-20260810.1"',
            script_anterior,
        )
        self.assertIn("route-a-migrate-0005", self.contenido)
        self.assertIn("route-b-migrate-0004", self.contenido)
        self.assertIn("route-b-migrate-0005", self.contenido)
        self.assertIn("route-b-migrate-finanzas", self.contenido)
        self.assertNotIn('"${DJANGO[@]}" migrate --noinput', self.contenido)
        self.assertNotIn("python manage.py migrate --noinput", self.contenido)

    def test_install_exige_mantenimiento_y_respaldos_antes_de_pip(self):
        bloque = self.bloque("  install)\n", "  preflight)\n")

        self.assertLess(bloque.index("require_maintenance"), bloque.index("pip install"))
        self.assertLess(bloque.index("validate_backup"), bloque.index("pip install"))
        self.assertLess(bloque.index("validate_snapshot"), bloque.index("pip install"))

    def test_ruta_a_solo_aplica_0005(self):
        bloque = self.bloque("  route-a-migrate-0005)\n", "  route-b-migrate-0004)\n")

        self.assertIn("run_timed_migration asistencias-0005 asistencias 0005", bloque)
        self.assertNotIn("asistencias-0004", bloque)
        self.assertNotIn("finanzas-0012", bloque)

    def test_ruta_b_no_permite_finanzas_antes_de_0005_y_revision(self):
        bloque = self.bloque("  route-b-migrate-finanzas)\n", "  diagnose-0005)\n")

        self.assertLess(bloque.index("require_review_gate"), bloque.index("run_timed_migration"))
        self.assertIn("require_state ROUTE_B_REVIEW", bloque)
        self.assertIn("require_success_marker 0005", bloque)

    def test_ruta_desconocida_y_revision_condicional_fallan_cerrado(self):
        self.assertIn('*) printf \'%s\\n\' "UNKNOWN"', self.contenido)
        self.assertIn("Preflight inicial rechazado", self.contenido)
        self.assertIn('review_mode_from_count 0)" == "NONE"', self.contenido)
        self.assertIn('review_mode_from_count 3)" == "REQUIRED"', self.contenido)

        gate = self.bloque("require_review_gate() {", 'case "$ACTION" in')
        self.assertIn("review_required=no", gate)
        self.assertIn("sin activaciones requeridas", gate)
        self.assertIn("review_required=yes", gate)
        self.assertIn("actor_user_id=", gate)

    def test_relaciones_pendientes_exigen_actor_id_y_permiso_real(self):
        validacion = self.bloque("validate_admin_actor() {", "require_review_gate() {")

        self.assertIn("RELEASE_ACTIVATION_USER_ID", validacion)
        self.assertIn("is_active=True", validacion)
        self.assertIn("ACCION_ADMINISTRAR_SESIONES", validacion)
        self.assertIn("ACCION_ADMINISTRAR_PERSONAS", validacion)
        self.assertIn("permitir_staff_global=False", validacion)

        inicio = validacion.index("shell -c '") + len("shell -c '")
        fin = validacion.index("\n'\n}", inicio)
        compile(validacion[inicio:fin], "validate_admin_actor", "exec")

    def test_documentacion_declara_gate_manual_y_fallo_forward_only(self):
        runbook = RUNBOOK.read_text(encoding="utf-8")
        deploy = DEPLOY_DOC.read_text(encoding="utf-8")

        self.assertIn("Ruta A", runbook)
        self.assertIn("Ruta B", runbook)
        self.assertIn("asistencias.0005", runbook)
        self.assertIn("forward-only", runbook)
        self.assertIn("push a `main`", deploy)
        self.assertIn("deploy` queda `skipped`", deploy)


if __name__ == "__main__":
    unittest.main()
